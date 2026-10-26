import json
from contextlib import nullcontext

from ffadv4manager import cli
from ffadv4manager.core.models import PrinterStatus


def test_doctor_reports_printer_and_camera_checks(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("FFADV4MANAGER_CONFIG", str(tmp_path / "config.ini"))

    class Client:
        def __init__(self, *_args, **_kwargs):
            pass

        def status(self):
            return PrinterStatus(raw="", machine_status="READY")

    monkeypatch.setattr(cli, "FlashForgeClient", Client)
    monkeypatch.setattr(cli.urllib.request, "urlopen", lambda *_a, **_kw: nullcontext(type("Response", (), {"read": lambda self, _size: b"x"})()))
    assert cli.main(["--host", "printer", "doctor"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["host"] == "printer"
    assert {check["name"] for check in report["checks"]} == {"printer_status", "camera_http"}
    assert all(check["ok"] for check in report["checks"])
