import json

from ffadv4manager import cli
from ffadv4manager.core.models import PrinterStatus


def test_wait_returns_when_bed_is_below_threshold(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("FFADV4MANAGER_CONFIG", str(tmp_path / "config.ini"))

    class Client:
        def __init__(self, *_args, **_kwargs):
            pass

        def status(self):
            return PrinterStatus(raw="", machine_status="READY", bed_current=35)

    monkeypatch.setattr(cli, "FlashForgeClient", Client)
    assert cli.main(["--host", "printer", "wait", "--bed-below", "40", "--timeout", "1"]) == 0
    assert json.loads(capsys.readouterr().out)["matched"] is True
