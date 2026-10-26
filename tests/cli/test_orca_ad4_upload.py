from ffadv4manager.core.models import PrinterStatus
from ffadv4manager import config as config_store
from scripts import orca_ad4_upload as hook


def _status(machine_status="READY"):
    return PrinterStatus(raw="", machine_status=machine_status)


class FakeClient:
    instances = []
    statuses = []
    upload_error = None

    def __init__(self, host, port, timeout):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.uploaded = []
        self.uploaded_data = []
        self.printed = []
        self.status_calls = 0
        self.__class__.instances.append(self)

    def status(self):
        self.status_calls += 1
        result = self.__class__.statuses.pop(0)
        if isinstance(result, BaseException):
            raise result
        return result

    def upload_and_confirm_listed(self, path, remote_name=None):
        if self.__class__.upload_error:
            raise self.__class__.upload_error
        self.uploaded.append(path)
        self.uploaded_data.append(path.read_bytes() if path.exists() else b"")
        return "/data/" + (remote_name or path.name)

    def print_file(self, remote):
        self.printed.append(remote)
        return "started"


def _setup(monkeypatch, tmp_path, config=None):
    monkeypatch.setenv("FFADV4MANAGER_CONFIG", str(tmp_path / "config.ini"))
    if config:
        config_store.save_config(config)
    FakeClient.instances = []
    FakeClient.statuses = []
    FakeClient.upload_error = None
    monkeypatch.setattr(hook, "FlashForgeClient", FakeClient)


def test_hook_uses_config_defaults_and_preserves_final_space_path(monkeypatch, tmp_path, capsys):
    _setup(monkeypatch, tmp_path, {"host": "configured-printer", "port": 9000, "timeout": 3.5})
    FakeClient.statuses = [_status(), _status()]
    gcode = tmp_path / "generated part.gcode"

    assert hook.main(["--no-convert", "--start", str(gcode)]) == 0
    client = FakeClient.instances[0]
    assert (client.host, client.port, client.timeout) == ("configured-printer", 9000, 3.5)
    assert client.uploaded == [gcode]
    assert client.printed == ["/data/generated part.gcode"]
    assert client.status_calls == 2
    assert "Uploaded and listed /data/generated part.gcode" in capsys.readouterr().out


def test_hook_without_start_only_uploads_and_confirms_listing(monkeypatch, tmp_path, capsys):
    _setup(monkeypatch, tmp_path, {"host": "stored", "port": 9000, "timeout": 5})
    FakeClient.statuses = [_status()]
    gcode = tmp_path / "option path.gcode"

    assert hook.main(["--no-convert", "--host", "explicit", "--port", "8899", "--timeout", "1.5", "--gcode", str(gcode)]) == 0
    client = FakeClient.instances[0]
    assert (client.host, client.port, client.timeout) == ("explicit", 8899, 1.5)
    assert client.uploaded == [gcode]
    assert client.printed == []
    assert "Uploaded and listed /data/option path.gcode" in capsys.readouterr().out


def test_busy_printer_refuses_before_upload_unless_force(monkeypatch, tmp_path, capsys):
    _setup(monkeypatch, tmp_path, {"host": "printer"})
    FakeClient.statuses = [_status("PRINTING")]
    gcode = tmp_path / "part.gcode"

    assert hook.main(["--start", str(gcode)]) == 1
    client = FakeClient.instances[-1]
    assert client.uploaded == []
    assert client.printed == []
    error = capsys.readouterr().err
    assert "active print" in error
    assert "Traceback" not in error

    assert hook.main(["--no-convert", "--start", "--force", str(gcode)]) == 0
    forced = FakeClient.instances[-1]
    assert forced.uploaded == [gcode]
    assert forced.printed == ["/data/part.gcode"]
    assert forced.status_calls == 0


def test_status_errors_and_unparseable_state_fail_closed_before_upload(monkeypatch, tmp_path, capsys):
    _setup(monkeypatch, tmp_path, {"host": "printer"})
    gcode = tmp_path / "part.gcode"
    for result in (OSError("offline"), _status(None)):
        FakeClient.statuses = [result]
        assert hook.main([str(gcode)]) == 1
        assert FakeClient.instances[-1].uploaded == []
        assert "refusing" in capsys.readouterr().err


def test_rechecks_status_immediately_before_start(monkeypatch, tmp_path, capsys):
    _setup(monkeypatch, tmp_path, {"host": "printer"})
    FakeClient.statuses = [_status("READY"), _status("PRINTING")]
    gcode = tmp_path / "part.gcode"
    gcode.write_text("G1 X1\n")

    assert hook.main(["--no-convert", "--start", str(gcode)]) == 1
    client = FakeClient.instances[-1]
    assert client.uploaded == [gcode]
    assert client.printed == []
    assert client.status_calls == 2
    assert "immediately before print start" in capsys.readouterr().err


def test_upload_error_is_concise_and_nonzero(monkeypatch, tmp_path, capsys):
    _setup(monkeypatch, tmp_path, {"host": "printer"})
    FakeClient.statuses = [_status()]
    FakeClient.upload_error = RuntimeError("upload rejected")

    path = tmp_path / "part.gcode"
    path.write_text("G1 X1\n")
    assert hook.main(["--no-convert", str(path)]) == 1
    err = capsys.readouterr().err
    assert "Error: upload rejected" in err
    assert "Traceback" not in err


def test_missing_host_uses_shared_config_error_without_traceback(monkeypatch, tmp_path, capsys):
    _setup(monkeypatch, tmp_path)

    assert hook.main([str(tmp_path / "part.gcode")]) == 2
    err = capsys.readouterr().err
    assert "no printer host configured" in err
    assert "Traceback" not in err


def test_hook_converts_before_upload_and_preserves_original(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path, {"host": "printer"})
    FakeClient.statuses = [_status()]
    gcode = tmp_path / "part.gcode"
    original = b"; layer_height = 0.2\nG1 X4\n"
    gcode.write_bytes(original)

    assert hook.main([str(gcode)]) == 0
    uploaded = FakeClient.instances[-1].uploaded[0]
    assert uploaded.name == "part.gx"
    assert FakeClient.instances[-1].uploaded_data[0].endswith(original)
    assert gcode.read_bytes() == original
