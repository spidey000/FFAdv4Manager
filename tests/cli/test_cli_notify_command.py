from ffadv4manager import cli
from ffadv4manager.core.models import PrinterStatus


def test_notify_dispatches_requested_desktop_event(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("FFADV4MANAGER_CONFIG", str(tmp_path / "config.ini"))
    monkeypatch.setattr(cli.shutil, "which", lambda _name: "/usr/bin/notify-send")
    calls = []
    monkeypatch.setattr(cli.subprocess, "run", lambda args, **_kwargs: calls.append(args))

    class Client:
        def __init__(self, *_args, **_kwargs):
            pass

        def status(self):
            return PrinterStatus(raw="", machine_status="PAUSED")

    monkeypatch.setattr(cli, "FlashForgeClient", Client)
    assert cli.main(["--host", "printer", "notify", "--events", "paused", "--count", "1"]) == 0
    assert calls == [["/usr/bin/notify-send", "FFADV4Manager", "Printer state: paused"]]
    capsys.readouterr()
