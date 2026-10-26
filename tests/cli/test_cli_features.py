import json
from pathlib import Path

import pytest

from ffadv4manager.core.models import PrinterStatus
from ffadv4manager.core.discovery import DiscoveredPrinter
from ffadv4manager import cli
from ffadv4manager import config as config_store


def _forbid_printer_client(*_args, **_kwargs):
    raise AssertionError("this command must not create a printer TCP client")


def test_discover_human_and_json_output_without_host(monkeypatch, capsys):
    calls = []

    def fake_discover_printers(**kwargs):
        calls.append(kwargs)
        return [DiscoveredPrinter("AD4", "192.168.1.50", 8899)]

    monkeypatch.setattr(cli, "FlashForgeClient", _forbid_printer_client)
    monkeypatch.setattr(cli, "discover_printers", fake_discover_printers)

    assert cli.main(["discover", "--timeout", "1.25"]) == 0
    human = capsys.readouterr().out
    assert "AD4" in human and "192.168.1.50" in human and "8899" in human

    assert cli.main(["discover", "--json"]) == 0
    parsed = json.loads(capsys.readouterr().out)
    assert parsed == [{"name": "AD4", "ip": "192.168.1.50", "port": 8899}]
    assert calls == [{"timeout": 1.25}, {"timeout": 3.0}]


def test_discover_empty_json_and_human(monkeypatch, capsys):
    monkeypatch.setattr(cli, "FlashForgeClient", _forbid_printer_client)
    monkeypatch.setattr(cli, "discover_printers", lambda **_kwargs: [])

    assert cli.main(["discover", "--json"]) == 0
    assert capsys.readouterr().out.strip() == "[]"
    assert cli.main(["discover"]) == 0
    assert "No printers discovered" in capsys.readouterr().out


def test_camera_url_uses_config_and_overrides_without_tcp(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("FFADV4MANAGER_CONFIG", str(tmp_path / "config.ini"))
    config_store.save_config({"host": "printer.local", "camera_path": "/stream?x=one"})
    monkeypatch.setattr(cli, "FlashForgeClient", _forbid_printer_client)

    assert cli.main(["camera", "url"]) == 0
    assert capsys.readouterr().out.strip() == "http://printer.local:8080/stream?x=one"
    assert cli.main(
        ["--host", "192.168.1.9", "camera", "url", "--camera-port", "8081", "--camera-path", "/?action=stream&x=two"]
    ) == 0
    assert capsys.readouterr().out.strip() == "http://192.168.1.9:8081/?action=stream&x=two"


def test_camera_snapshot_prints_only_saved_path(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("FFADV4MANAGER_CONFIG", str(tmp_path / "config.ini"))
    config_store.save_config({"host": "192.168.1.50"})
    monkeypatch.setattr(cli, "FlashForgeClient", _forbid_printer_client)
    calls = []

    def fake_capture(url, output):
        calls.append((url, output))
        return Path(output)

    monkeypatch.setattr(cli, "capture_first_frame", fake_capture)
    output = tmp_path / "frame.jpg"

    assert cli.main(["camera", "snapshot", str(output)]) == 0
    assert capsys.readouterr().out.strip() == str(output)
    assert calls == [("http://192.168.1.50:8080/?action=stream", str(output))]


def test_camera_open_reports_headless_browser(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("FFADV4MANAGER_CONFIG", str(tmp_path / "config.ini"))
    config_store.save_config({"host": "192.168.1.50"})
    monkeypatch.setattr(cli, "FlashForgeClient", _forbid_printer_client)
    opened = []
    monkeypatch.setattr(cli.webbrowser, "open", lambda url: opened.append(url) or False)

    assert cli.main(["camera", "open"]) == 1
    assert opened == ["http://192.168.1.50:8080/?action=stream"]
    err = capsys.readouterr().err
    assert "headless" in err
    assert opened[0] in err


def test_camera_requires_host_and_rejects_bad_stored_port(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("FFADV4MANAGER_CONFIG", str(tmp_path / "config.ini"))
    monkeypatch.setattr(cli, "FlashForgeClient", _forbid_printer_client)

    assert cli.main(["camera", "url"]) == 1
    assert "no printer host" in capsys.readouterr().err

    config_store.save_config({"host": "192.168.1.50", "camera_port": 99999})
    assert cli.main(["camera", "url"]) == 1
    assert "invalid camera port" in capsys.readouterr().err


def test_camera_config_set_show_and_unset_persists(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("FFADV4MANAGER_CONFIG", str(tmp_path / "config.ini"))

    assert cli.main(
        ["config", "set", "--host", "192.168.1.50", "--camera-port", "8082", "--camera-path", "/video?mode=low"]
    ) == 0
    assert config_store.load_config() == {
        "host": "192.168.1.50",
        "camera_port": "8082",
        "camera_path": "/video?mode=low",
    }
    assert cli.main(["config", "show"]) == 0
    shown = capsys.readouterr().out
    assert "camera_port = 8082" in shown
    assert "camera_path = /video?mode=low" in shown

    assert cli.main(["config", "unset", "camera_port", "camera_path"]) == 0
    assert config_store.load_config() == {"host": "192.168.1.50"}


def test_config_set_rejects_out_of_range_camera_port(monkeypatch, capsys):
    with pytest.raises(SystemExit) as exit_info:
        cli.main(["config", "set", "--camera-port", "0"])
    assert exit_info.value.code == 2
    assert "camera port" in capsys.readouterr().err.lower()


def test_upload_start_is_not_invoked_when_verification_fails(monkeypatch, tmp_path, capsys):
    class FakeClient:
        def __init__(self, *_args, **_kwargs):
            self.started = False

        def status(self):
            return type("Status", (), {"is_printing": False})()

        def upload_and_confirm_listed(self, *_args, **_kwargs):
            raise RuntimeError("uploaded file not listed")

        def print_file(self, *_args, **_kwargs):
            self.started = True
            raise AssertionError("must not start without verification")

    monkeypatch.setenv("FFADV4MANAGER_CONFIG", str(tmp_path / "config.ini"))
    client = FakeClient()
    monkeypatch.setattr(cli, "FlashForgeClient", lambda *_args, **_kwargs: client)
    file = tmp_path / "part.gcode"
    file.write_text("G1 X1\n")

    assert cli.main(["--host", "printer", "upload", str(file), "--no-convert", "--start"]) == 1
    assert "uploaded file not listed" in capsys.readouterr().err
    assert not client.started


def test_successful_upload_without_start_never_calls_print_file(monkeypatch, tmp_path, capsys):
    class FakeClient:
        def __init__(self, *_args, **_kwargs):
            self.calls = []

        def status(self):
            self.calls.append("status")
            return type("Status", (), {"is_printing": False})()

        def upload_and_confirm_listed(self, *_args, **_kwargs):
            self.calls.append("upload_and_confirm_listed")
            return "0:/user/part.gcode"

        def print_file(self, *_args, **_kwargs):
            self.calls.append("print_file")
            raise AssertionError("upload without --start must not start a print")

    monkeypatch.setenv("FFADV4MANAGER_CONFIG", str(tmp_path / "config.ini"))
    client = FakeClient()
    monkeypatch.setattr(cli, "FlashForgeClient", lambda *_args, **_kwargs: client)
    file = tmp_path / "part.gcode"
    file.write_text("G1 X1\n")

    assert cli.main(["--host", "printer", "upload", str(file), "--no-convert"]) == 0
    assert client.calls == ["status", "upload_and_confirm_listed"]
    assert "Uploaded and listed: 0:/user/part.gcode" in capsys.readouterr().out


def test_explicit_start_calls_print_only_after_upload_verification(monkeypatch, tmp_path):
    class FakeClient:
        def __init__(self, *_args, **_kwargs):
            self.calls = []

        def status(self):
            self.calls.append("status")
            return type("Status", (), {"is_printing": False})()

        def upload_and_confirm_listed(self, *_args, **_kwargs):
            self.calls.append("upload_and_confirm_listed")
            return "0:/user/part.gcode"

        def print_file(self, remote, **_kwargs):
            assert self.calls == ["status", "upload_and_confirm_listed"]
            self.calls.append(("print_file", remote))
            return "started"

    monkeypatch.setenv("FFADV4MANAGER_CONFIG", str(tmp_path / "config.ini"))
    client = FakeClient()
    monkeypatch.setattr(cli, "FlashForgeClient", lambda *_args, **_kwargs: client)
    file = tmp_path / "part.gcode"
    file.write_text("G1 X1\n")

    assert cli.main(["--host", "printer", "upload", str(file), "--no-convert", "--start"]) == 0
    assert client.calls == ["status", "upload_and_confirm_listed", ("print_file", "0:/user/part.gcode")]


@pytest.mark.parametrize(
    ("command_args", "expected_calls"),
    [
        (["status"], ["status"]),
        (["files"], ["files"]),
        (["files-raw"], ["files_raw"]),
        (["print", "part.gcode"], ["status", ("print_file", "part.gcode")]),
        (["pause"], ["pause"]),
        (["resume"], ["resume"]),
        (["cancel"], ["cancel"]),
    ],
)
def test_cli_dispatches_printer_commands_to_intended_client_methods(
    monkeypatch, tmp_path, capsys, command_args, expected_calls
):
    class FakeClient:
        def __init__(self, *_args, **_kwargs):
            self.calls = []

        def status(self):
            self.calls.append("status")
            return PrinterStatus(raw="", machine_status="READY")

        def files(self):
            self.calls.append("files")
            return ["/data/part.gcode"]

        def files_raw(self):
            self.calls.append("files_raw")
            return "/data/part.gcode:\n"

        def print_file(self, remote):
            self.calls.append(("print_file", remote))
            return "print started"

        def pause(self):
            self.calls.append("pause")
            return "pause reply"

        def resume(self):
            self.calls.append("resume")
            return "resume reply"

        def cancel(self):
            self.calls.append("cancel")
            return "cancel reply"

    monkeypatch.setenv("FFADV4MANAGER_CONFIG", str(tmp_path / "config.ini"))
    client = FakeClient()
    monkeypatch.setattr(cli, "FlashForgeClient", lambda *_args, **_kwargs: client)

    assert cli.main(["--host", "printer", *command_args]) == 0
    assert client.calls == expected_calls
    capsys.readouterr()
