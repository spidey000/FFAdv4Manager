import json

from ffadv4manager import cli
from ffadv4manager.core.models import PrinterStatus


def test_status_json_emits_parsed_fields_and_nulls(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("FFADV4MANAGER_CONFIG", str(tmp_path / "config.ini"))

    class Client:
        def __init__(self, *_args, **_kwargs):
            pass

        def status(self):
            return PrinterStatus(raw="sensitive raw data", machine_status="READY", bed_current=24)

    monkeypatch.setattr(cli, "FlashForgeClient", Client)
    assert cli.main(["--host", "printer", "status", "--json"]) == 0
    record = json.loads(capsys.readouterr().out)
    assert record["machine_status"] == "READY"
    assert record["bed_current"] == 24
    assert record["bed_target"] is None
    assert "raw" not in record
