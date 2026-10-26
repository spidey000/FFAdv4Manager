import json
from pathlib import Path

from ffadv4manager import cli
from ffadv4manager.core.models import PrinterStatus


def test_timelapse_saves_interval_frames_and_manifest(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("FFADV4MANAGER_CONFIG", str(tmp_path / "config.ini"))
    monkeypatch.setattr(cli.time, "sleep", lambda _seconds: None)

    class Client:
        def __init__(self, *_args, **_kwargs):
            pass

        def status(self):
            return PrinterStatus(raw="", machine_status="BUILDING", current_file="part.gx", sd_current=5, sd_total=10)

    def capture(_url, destination):
        Path(destination).write_bytes(b"\xff\xd8\xff\xd9")
        return Path(destination)

    monkeypatch.setattr(cli, "FlashForgeClient", Client)
    monkeypatch.setattr(cli, "capture_first_frame", capture)
    folder = tmp_path / "timelapse"
    assert cli.main(["--host", "printer", "camera", "timelapse", str(folder), "--count", "2"]) == 0
    assert len(list(folder.glob("frame-*.jpg"))) == 2
    records = [json.loads(line) for line in (folder / "timelapse.jsonl").read_text().splitlines()]
    assert len(records) == 2
    assert records[0]["current_file"] == "part.gx"
    assert records[0]["progress_percent"] == 50
    capsys.readouterr()
