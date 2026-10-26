import socket

import pytest

from ffadv4manager.core import client as client_module
from ffadv4manager.core.client import FlashForgeClient, ProtocolError


@pytest.fixture(autouse=True)
def skip_upload_flush_wait(monkeypatch):
    monkeypatch.setattr(client_module.time, "sleep", lambda _seconds: None)


class FakeSocket:
    def __init__(self, responses):
        self.responses = list(responses)
        self.sent = []
        self.events = []
        self.timeout = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def settimeout(self, timeout):
        self.timeout = timeout

    def gettimeout(self):
        return self.timeout

    def sendall(self, payload):
        self.sent.append(payload)
        self.events.append(("sendall", payload))

    def recv(self, _size):
        response = self.responses.pop(0) if self.responses else socket.timeout()
        if isinstance(response, BaseException):
            raise response
        return response


def test_upload_preamble_order_and_size_path_with_fragmented_acknowledgements(monkeypatch, tmp_path):
    gcode = tmp_path / "part.gcode"
    gcode.write_bytes(b"G1 X1\n")
    console = FakeSocket([b"prefix\r\n", b"o", b"k\r\n", b"ok\n", b"ok\n", b"ok\n"])
    upload = FakeSocket([b"CMD M28 Received.\r\no", b"k\r\n", b"o", b"k\n"])
    sockets = [console, upload]
    monkeypatch.setattr(socket, "create_connection", lambda *_args, **_kwargs: sockets.pop(0))
    client = FlashForgeClient("printer")

    assert client.upload(gcode) == "0:/user/part.gcode"
    assert console.sent == [b"~M601 S1\r\n", b"~M115\r\n", b"~M650\r\n", b"~M119\r\n"]
    assert upload.sent == [b"~M28 6 0:/user/part.gcode\r\n", b"G1 X1\n", b"~M29\r\n"]


def test_upload_flushes_payload_for_three_seconds_before_m29(monkeypatch, tmp_path):
    gcode = tmp_path / "part.gcode"
    gcode.write_bytes(b"abcdef")
    console = FakeSocket([b"ok\n"] * 4)
    upload = FakeSocket([b"ok\n", b"ok\n"])
    sockets = [console, upload]
    monkeypatch.setattr(socket, "create_connection", lambda *_args, **_kwargs: sockets.pop(0))
    monkeypatch.setattr(
        client_module.time,
        "sleep",
        lambda seconds: upload.events.append(("sleep", seconds)),
    )

    assert FlashForgeClient("printer").upload(gcode, chunk_size=2) == "0:/user/part.gcode"

    assert upload.events == [
        ("sendall", b"~M28 6 0:/user/part.gcode\r\n"),
        ("sendall", b"ab"),
        ("sendall", b"cd"),
        ("sendall", b"ef"),
        ("sleep", 3.0),
        ("sendall", b"~M29\r\n"),
    ]


def test_upload_rejects_empty_file_before_connect(monkeypatch, tmp_path):
    empty_file = tmp_path / "empty.gcode"
    empty_file.write_bytes(b"")
    monkeypatch.setattr(
        socket,
        "create_connection",
        lambda *_args, **_kwargs: pytest.fail("empty file must not open a socket"),
    )

    with pytest.raises(ValueError, match="local file must not be empty"):
        FlashForgeClient("printer").upload(empty_file)


def test_upload_rejects_file_that_grows_during_transfer(monkeypatch, tmp_path):
    gcode = tmp_path / "part.gcode"
    gcode.write_bytes(b"G1 X1\n")
    fake = FakeSocket([b"ok\n"] * 4 + [b"ok\n", b"ok\n"])
    sendall = fake.sendall

    def send_and_grow(payload):
        sendall(payload)
        if payload == b"G1 X1\n":
            gcode.write_bytes(b"G1 X1\nG1 X2\n")

    fake.sendall = send_and_grow
    monkeypatch.setattr(socket, "create_connection", lambda *_args, **_kwargs: fake)

    with pytest.raises(ValueError, match="local file changed during upload"):
        FlashForgeClient("printer").upload(gcode)


def test_files_collects_chunks_after_m661_ack(monkeypatch):
    fake = FakeSocket(
        [
            b"CMD M661 Received.\r\nOK\r\n",
            b"/data/first.gcode:\x01metadata\n/data/second.",
            b"gcode:\x01metadata\n/data/third.gcode:\x01metadata\n",
        ]
    )
    monkeypatch.setattr(socket, "create_connection", lambda *_args, **_kwargs: fake)

    client = FlashForgeClient("printer")
    raw = client.files_raw()

    assert fake.sent == [b"~M661\r\n"]
    assert "/data/first.gcode" in raw
    assert "/data/second.gcode" in raw
    assert "/data/third.gcode" in raw

    fake.responses = [
        b"CMD M661 Received.\r\nOK\r\n",
        b"/data/first.gcode:\x01metadata\n/data/second.",
        b"gcode:\x01metadata\n/data/third.gcode:\x01metadata\n",
    ]
    fake.sent.clear()
    assert client.files() == [
        "/data/first.gcode",
        "/data/second.gcode",
        "/data/third.gcode",
    ]
    assert fake.sent == [b"~M661\r\n"]


def test_status_sends_m119_m105_m27_in_order_and_parses_response(monkeypatch):
    sockets = [
        FakeSocket([b"MachineStatus: READY\r\nMoveMode: READY\r\nCurrentFile: \r\nok\r\n"]),
        FakeSocket([b"T0:205/210 B:60/60\r\nok\r\n"]),
        FakeSocket([b"SD printing byte 125/500\r\nLayer: 2/4\r\nok\r\n"]),
    ]
    created_sockets = list(sockets)
    monkeypatch.setattr(socket, "create_connection", lambda *_args, **_kwargs: sockets.pop(0))

    status = FlashForgeClient("printer").status()

    assert [sock.sent for sock in created_sockets] == [
        [b"~M119\r\n"], [b"~M105\r\n"], [b"~M27\r\n"],
    ]
    assert status.machine_status == "READY"
    assert status.nozzle_current == 205
    assert status.nozzle_target == 210
    assert status.bed_current == 60
    assert status.bed_target == 60
    assert status.sd_current == 125
    assert status.sd_total == 500
    assert status.layer_current == 2
    assert status.layer_total == 4


@pytest.mark.parametrize(
    ("method_name", "command"),
    [("pause", "M25"), ("resume", "M24"), ("cancel", "M26")],
)
def test_pause_resume_cancel_serialize_expected_commands(monkeypatch, method_name, command):
    fake = FakeSocket([b"ok\n"])
    monkeypatch.setattr(socket, "create_connection", lambda *_args, **_kwargs: fake)

    assert getattr(FlashForgeClient("printer"), method_name)() == "ok\n"
    assert fake.sent == [f"~{command}\r\n".encode()]


def test_m28_command_receipt_without_exact_ok_aborts_before_payload_or_m29(monkeypatch, tmp_path):
    gcode = tmp_path / "part.gcode"
    gcode.write_bytes(b"G1 X1\n")
    console = FakeSocket([b"ok\n"] * 4)
    upload = FakeSocket([b"CMD M28 Received.\r\n"])
    sockets = [console, upload]
    monkeypatch.setattr(socket, "create_connection", lambda *_args, **_kwargs: sockets.pop(0))

    with pytest.raises(ProtocolError, match="M28 upload start"):
        FlashForgeClient("printer").upload(gcode)
    assert upload.sent == [b"~M28 6 0:/user/part.gcode\r\n"]


def test_m28_error_with_ok_aborts_before_payload_or_m29(monkeypatch, tmp_path):
    gcode = tmp_path / "part.gcode"
    gcode.write_bytes(b"G1 X1\n")
    console = FakeSocket([b"ok\n"] * 4)
    upload = FakeSocket([b"Error: cannot open file\r\nok\r\n"])
    sockets = [console, upload]
    monkeypatch.setattr(socket, "create_connection", lambda *_args, **_kwargs: sockets.pop(0))

    with pytest.raises(ProtocolError, match="rejected M28 upload start: Error: cannot open file"):
        FlashForgeClient("printer").upload(gcode)
    assert upload.sent == [b"~M28 6 0:/user/part.gcode\r\n"]


def test_upload_missing_preamble_ack_fails_before_upload_connection(monkeypatch, tmp_path):
    gcode = tmp_path / "part.gcode"
    gcode.write_bytes(b"G1 X1")
    console = FakeSocket([b"ok\n", b"not ready\n"])
    sockets = [console]
    monkeypatch.setattr(socket, "create_connection", lambda *_args, **_kwargs: sockets.pop(0))
    with pytest.raises(ProtocolError, match="M115 preamble"):
        FlashForgeClient("printer").upload(gcode)
    assert console.sent == [b"~M601 S1\r\n", b"~M115\r\n"]
    assert sockets == []


def test_upload_preamble_timeout_fails_closed(monkeypatch, tmp_path):
    gcode = tmp_path / "part.gcode"
    gcode.write_bytes(b"G1 X1")
    console = FakeSocket([socket.timeout()])
    sockets = [console]
    monkeypatch.setattr(socket, "create_connection", lambda *_args, **_kwargs: sockets.pop(0))
    with pytest.raises(ProtocolError, match="M601 S1 preamble"):
        FlashForgeClient("printer").upload(gcode)
    assert console.sent == [b"~M601 S1\r\n"]
    assert sockets == []

def test_upload_missing_m29_ack_fails_closed(monkeypatch, tmp_path):
    gcode = tmp_path / "part.gcode"
    gcode.write_bytes(b"G1 X1")
    console = FakeSocket([b"ok\n"] * 4)
    upload = FakeSocket([b"ok\n", socket.timeout()])
    sockets = [console, upload]
    monkeypatch.setattr(socket, "create_connection", lambda *_args, **_kwargs: sockets.pop(0))
    with pytest.raises(ProtocolError, match="M29 upload completion"):
        FlashForgeClient("printer").upload(gcode)


def test_m29_save_error_with_ok_fails_completion(monkeypatch, tmp_path):
    gcode = tmp_path / "part.gcode"
    gcode.write_bytes(b"G1 X1")
    console = FakeSocket([b"ok\n"] * 4)
    upload = FakeSocket([b"ok\n", b"Error: failed to save file\r\nok\r\n"])
    sockets = [console, upload]
    monkeypatch.setattr(socket, "create_connection", lambda *_args, **_kwargs: sockets.pop(0))

    with pytest.raises(ProtocolError, match="rejected M29 upload completion: Error: failed to save file"):
        FlashForgeClient("printer").upload(gcode)


def _listed_client(monkeypatch, listing):
    responses = [[b"ok\n"] * 4, [b"ok\n", b"ok\n"], [listing, socket.timeout()]]
    sockets = [FakeSocket(batch) for batch in responses]
    created_sockets = list(sockets)
    monkeypatch.setattr(socket, "create_connection", lambda *_args, **_kwargs: sockets.pop(0))
    return created_sockets


@pytest.mark.parametrize("listing", [b"/data/part.gcode:\n", b"0:/user/part.gcode:\n"])
def test_upload_confirms_m661_basename_without_selection_or_start(monkeypatch, tmp_path, listing):
    gcode = tmp_path / "part.gcode"
    gcode.write_bytes(b"G1 X1\n")
    sockets = _listed_client(monkeypatch, listing)
    assert FlashForgeClient("printer").upload_and_confirm_listed(gcode) == "0:/user/part.gcode"
    sent_commands = [payload for sock in sockets for payload in sock.sent if payload.startswith(b"~")]
    assert sent_commands == [
        b"~M601 S1\r\n", b"~M115\r\n", b"~M650\r\n", b"~M119\r\n",
        b"~M28 6 0:/user/part.gcode\r\n", b"~M29\r\n", b"~M661\r\n",
    ]


def test_upload_fails_when_m661_omits_file_without_selection(monkeypatch, tmp_path):
    gcode = tmp_path / "part.gcode"
    gcode.write_bytes(b"G1 X1\n")
    sockets = _listed_client(monkeypatch, b"/data/other.gcode:\n")

    with pytest.raises(ProtocolError, match="M661 did not list 'part.gcode'"):
        FlashForgeClient("printer").upload_and_confirm_listed(gcode)

    sent_commands = [payload for sock in sockets for payload in sock.sent if payload.startswith(b"~")]
    assert b"~M23 0:/user/part.gcode\r\n" not in sent_commands
    assert b"~M24\r\n" not in sent_commands


def test_print_file_requires_selection_and_start_ack(monkeypatch):
    sockets = [FakeSocket([b"ok\n"]), FakeSocket([b"ok\n"])]
    monkeypatch.setattr(socket, "create_connection", lambda *_args, **_kwargs: sockets.pop(0))
    client = FlashForgeClient("printer")

    assert client.print_file("/data/part.gcode") == "ok\n\nok\n"

    sockets = [FakeSocket([b"Error: file not found\n"])]
    monkeypatch.setattr(socket, "create_connection", lambda *_args, **_kwargs: sockets.pop(0))
    with pytest.raises(ProtocolError, match="M23"):
        client.print_file("part.gcode")
    assert sockets == []

    sockets = [FakeSocket([b"ok\n"]), FakeSocket([socket.timeout()])]
    monkeypatch.setattr(socket, "create_connection", lambda *_args, **_kwargs: sockets.pop(0))
    with pytest.raises(ProtocolError, match="M24"):
        client.print_file("part.gcode")


def test_print_file_accepts_uploaded_user_namespace(monkeypatch):
    fake = FakeSocket([b"ok\n"])
    start = FakeSocket([b"ok\n"])
    sockets = [fake, start]
    monkeypatch.setattr(socket, "create_connection", lambda *_args, **_kwargs: sockets.pop(0))
    assert FlashForgeClient("printer").print_file("0:/user/part.gcode") == "ok\n\nok\n"
    assert fake.sent == [b"~M23 0:/user/part.gcode\r\n"]
    assert start.sent == [b"~M24\r\n"]


@pytest.mark.parametrize(
    "name",
    ["", "../part.gcode", "folder/part.gcode", "/tmp/part.gcode", "/data/nested/part.gcode", "bad\rname", "bad\nname", "bad\x00name", "bad\\name"],
)
def test_upload_and_print_reject_unsafe_remote_names_before_connect(monkeypatch, tmp_path, name):
    gcode = tmp_path / "local.gcode"
    gcode.write_text("G1 X1")
    monkeypatch.setattr(
        socket,
        "create_connection",
        lambda *_args, **_kwargs: pytest.fail("invalid name must not open a socket"),
    )
    client = FlashForgeClient("printer")

    with pytest.raises(ValueError):
        client.upload(gcode, remote_name=name)
    with pytest.raises(ValueError):
        client.print_file(name)


def test_remote_names_allow_simple_unicode_spaces_and_explicit_data_path(monkeypatch, tmp_path):
    gcode = tmp_path / "source.gcode"
    gcode.write_text("G1")
    sockets = [FakeSocket([b"ok\n"] * 4), FakeSocket([b"ok\n", b"ok\n"])]
    monkeypatch.setattr(socket, "create_connection", lambda *_args, **_kwargs: sockets.pop(0))
    assert FlashForgeClient("printer").upload(gcode, "my part – café.gcode") == "0:/user/my part – café.gcode"

    sockets = [FakeSocket([b"ok\n"]), FakeSocket([b"ok\n"])]
    monkeypatch.setattr(socket, "create_connection", lambda *_args, **_kwargs: sockets.pop(0))
    FlashForgeClient("printer").print_file("/data/my part – café.gcode")
