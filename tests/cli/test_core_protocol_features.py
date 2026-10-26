import socket

import pytest

from ffadv4manager.core.client import FlashForgeClient, ProtocolError
from ffadv4manager.core.parser import parse_info, parse_position


class FakeSocket:
    def __init__(self, responses):
        self.responses = list(responses)
        self.sent = []
        self.timeout = None

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def settimeout(self, timeout):
        self.timeout = timeout

    def sendall(self, payload):
        self.sent.append(payload)

    def recv(self, _size):
        response = self.responses.pop(0) if self.responses else socket.timeout()
        if isinstance(response, BaseException):
            raise response
        return response


def test_m115_and_m114_helpers_parse_available_values():
    assert parse_info("FIRMWARE_NAME:FlashForge\nEXTRUDER_COUNT:1\nok\n") == {
        "FIRMWARE_NAME": "FlashForge",
        "EXTRUDER_COUNT": "1",
    }
    assert parse_position("X:1.25 Y:-2 Z:0.000 E:9\nok\n") == {
        "X": 1.25, "Y": -2.0, "Z": 0.0, "E": 9.0,
    }


def test_info_position_and_fan_commands(monkeypatch):
    sockets = [
        FakeSocket([b"FIRMWARE_NAME:AD4\nok\n"]),
        FakeSocket([b"X:1 Y:2 Z:3\nok\n"]),
        FakeSocket([b"ok\n"]),
        FakeSocket([b"ok\n"]),
    ]
    created = list(sockets)
    monkeypatch.setattr(socket, "create_connection", lambda *_a, **_kw: sockets.pop(0))
    client = FlashForgeClient("printer")

    assert client.info() == {"FIRMWARE_NAME": "AD4"}
    assert client.position() == {"X": 1.0, "Y": 2.0, "Z": 3.0}
    client.set_fan(128)
    client.fan_off()
    assert [sock.sent for sock in created] == [
        [b"~M115\r\n"], [b"~M114\r\n"], [b"~M106 S128\r\n"], [b"~M107\r\n"],
    ]


def test_rename_validates_before_sending_and_requires_ack(monkeypatch):
    fake = FakeSocket([b"ok\n"])
    monkeypatch.setattr(socket, "create_connection", lambda *_a, **_kw: fake)
    assert FlashForgeClient("printer").rename("New_Printer") == "ok\n"
    assert fake.sent == [b"~M610 New_Printer\r\n"]

    def no_connect(*_args, **_kwargs):
        pytest.fail("unsafe rename must not connect")
    monkeypatch.setattr(socket, "create_connection", no_connect)
    with pytest.raises(ValueError):
        FlashForgeClient("printer").rename("new;M107")


@pytest.mark.parametrize("speed", [-1, 256, True, 1.5])
def test_fan_speed_rejects_invalid_values_before_sending(monkeypatch, speed):
    monkeypatch.setattr(socket, "create_connection", lambda *_a, **_kw: pytest.fail("must not connect"))
    with pytest.raises(ValueError):
        FlashForgeClient("printer").set_fan(speed)


def test_m662_reads_acknowledged_bmp_completely_across_chunks(monkeypatch):
    bmp = b"BM" + (18).to_bytes(4, "little") + b"\x00" * 12
    fake = FakeSocket([b"CMD M662 Received.\r\nok\r\nBM\x12", bmp[3:10], bmp[10:]])
    monkeypatch.setattr(socket, "create_connection", lambda *_a, **_kw: fake)

    assert FlashForgeClient("printer").preview_bmp("part.gx") == bmp
    assert fake.sent == [b"~M662 /data/part.gx\r\n"]


def test_m662_rejects_incomplete_bmp(monkeypatch):
    fake = FakeSocket([b"ok\r\nBM\x12\x00\x00\x00short", socket.timeout()])
    monkeypatch.setattr(socket, "create_connection", lambda *_a, **_kw: fake)
    with pytest.raises(ProtocolError, match="complete M662 BMP"):
        FlashForgeClient("printer").preview_bmp("part.gx")


def test_m662_rejects_gcode_injection_in_remote_filename(monkeypatch):
    monkeypatch.setattr(socket, "create_connection", lambda *_a, **_kw: pytest.fail("must not connect"))
    with pytest.raises(ValueError, match="semicolons"):
        FlashForgeClient("printer").preview_bmp("part;M107.gx")
