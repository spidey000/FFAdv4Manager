import json

from ffadv4manager import cli
from ffadv4manager.core.models import PrinterStatus


def test_watch_jsonl_emits_bounded_single_line_samples(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("FFADV4MANAGER_CONFIG", str(tmp_path / "config.ini"))
    monkeypatch.setattr(cli.time, "sleep", lambda _seconds: None)

    class Client:
        def __init__(self, *_args, **_kwargs):
            pass

        def status(self):
            return PrinterStatus(raw="", machine_status="READY")

    monkeypatch.setattr(cli, "FlashForgeClient", Client)
    assert cli.main(["--host", "printer", "watch", "--jsonl", "--count", "2"]) == 0
    records = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert len(records) == 2
    assert all(record["machine_status"] == "READY" for record in records)
    assert all("timestamp" in record for record in records)
