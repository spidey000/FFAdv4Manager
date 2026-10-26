import json
from pathlib import Path

from ffadv4manager import cli
from ffadv4manager.core.models import PrinterStatus


class FakeClient:
    constructed = []

    def __init__(self, *_args, **_kwargs):
        self.constructed.append(_args)
        self.renamed_to = None

    def status(self):
        return PrinterStatus(raw="", machine_status="READY", bed_current=35, bed_target=0)

    def files(self):
        return ["/data/part.gx"]

    def info(self):
        return {"Machine Name": self.renamed_to or "printer", "Firmware": "v2.2.4"}

    def position(self):
        return {"X": 1.5, "Y": -2.0}

    def preview_bmp(self, _name):
        return b"BMpreview"

    def rename(self, name):
        self.renamed_to = name
        return "ok"

    def fan_off(self):
        return "ok"

    def set_fan(self, _speed):
        return "ok"


def test_status_files_info_and_position_json(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("FFADV4MANAGER_CONFIG", str(tmp_path / "config.ini"))
    monkeypatch.setattr(cli, "FlashForgeClient", FakeClient)

    assert cli.main(["--host", "printer", "status", "--json"]) == 0
    status = json.loads(capsys.readouterr().out)
    assert status["machine_status"] == "READY"
    assert status["progress_percent"] is None
    assert "raw" not in status

    assert cli.main(["--host", "printer", "files", "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == ["/data/part.gx"]
    assert cli.main(["--host", "printer", "info", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["Firmware"] == "v2.2.4"
    assert cli.main(["--host", "printer", "position", "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == {"X": 1.5, "Y": -2.0}


def test_watch_jsonl_is_bounded_and_one_record_per_line(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("FFADV4MANAGER_CONFIG", str(tmp_path / "config.ini"))
    monkeypatch.setattr(cli, "FlashForgeClient", FakeClient)
    monkeypatch.setattr(cli.time, "sleep", lambda _seconds: None)

    assert cli.main(["--host", "printer", "watch", "--jsonl", "--count", "2", "--interval", "0.1"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 2
    assert all(json.loads(line)["machine_status"] == "READY" for line in lines)


def test_files_preview_writes_bmp_and_prints_output(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("FFADV4MANAGER_CONFIG", str(tmp_path / "config.ini"))
    monkeypatch.setattr(cli, "FlashForgeClient", FakeClient)
    output = tmp_path / "preview.bmp"

    assert cli.main(["--host", "printer", "files", "preview", "part.gx", "--output", str(output)]) == 0
    assert output.read_bytes() == b"BMpreview"
    assert capsys.readouterr().out.strip() == str(output)


def test_wait_returns_when_condition_matches(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("FFADV4MANAGER_CONFIG", str(tmp_path / "config.ini"))
    monkeypatch.setattr(cli, "FlashForgeClient", FakeClient)

    assert cli.main(["--host", "printer", "wait", "--state", "READY", "--timeout", "1"]) == 0
    assert json.loads(capsys.readouterr().out)["matched"] is True


def test_named_profile_is_used_for_connection(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("FFADV4MANAGER_CONFIG", str(tmp_path / "config.ini"))
    monkeypatch.setattr(cli, "FlashForgeClient", FakeClient)
    FakeClient.constructed.clear()
    monkeypatch.setattr(cli.profile_store, "get_profile", lambda _name: {"host": "profile-printer", "port": 8890})

    assert cli.main(["--profile", "workshop", "status", "--json"]) == 0
    assert FakeClient.constructed[-1][:2] == ("profile-printer", 8890)
    capsys.readouterr()


def test_timelapse_writes_frames_and_manifest(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("FFADV4MANAGER_CONFIG", str(tmp_path / "config.ini"))
    monkeypatch.setattr(cli, "FlashForgeClient", FakeClient)
    monkeypatch.setattr(cli.time, "sleep", lambda _seconds: None)

    def fake_capture(_url, output):
        Path(output).write_bytes(b"\xff\xd8\xff\xd9")
        return Path(output)

    monkeypatch.setattr(cli, "capture_first_frame", fake_capture)
    directory = tmp_path / "frames"
    assert cli.main(["--host", "printer", "camera", "timelapse", str(directory), "--count", "2"]) == 0
    assert len(list(directory.glob("frame-*.jpg"))) == 2
    records = [json.loads(line) for line in (directory / "timelapse.jsonl").read_text().splitlines()]
    assert len(records) == 2 and records[0]["machine_status"] == "READY"
    capsys.readouterr()


def test_monitor_appends_status_record(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("FFADV4MANAGER_CONFIG", str(tmp_path / "config.ini"))
    monkeypatch.setattr(cli, "FlashForgeClient", FakeClient)
    output = tmp_path / "monitor.jsonl"

    assert cli.main(["--host", "printer", "monitor", "--output", str(output), "--count", "1"]) == 0
    assert json.loads(output.read_text().splitlines()[0])["event"] == "state_change"
    capsys.readouterr()


def test_notify_calls_notify_send_for_requested_state(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("FFADV4MANAGER_CONFIG", str(tmp_path / "config.ini"))
    monkeypatch.setattr(cli, "FlashForgeClient", FakeClient)
    monkeypatch.setattr(cli.shutil, "which", lambda _name: "/usr/bin/notify-send")
    calls = []
    monkeypatch.setattr(cli.subprocess, "run", lambda args, **kwargs: calls.append((args, kwargs)))

    assert cli.main(["--host", "printer", "notify", "--events", "ready", "--count", "1"]) == 0
    assert calls[0][0] == ["/usr/bin/notify-send", "FFADV4Manager", "Printer state: ready"]
    capsys.readouterr()


def test_printer_rename_and_fan_commands_dispatch(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("FFADV4MANAGER_CONFIG", str(tmp_path / "config.ini"))
    monkeypatch.setattr(cli, "FlashForgeClient", FakeClient)
    assert cli.main(["--host", "printer", "printer", "rename", "printer-new"]) == 0
    assert "ok" in capsys.readouterr().out
    assert cli.main(["--host", "printer", "fan", "off"]) == 0
    assert capsys.readouterr().out.strip() == "ok"
