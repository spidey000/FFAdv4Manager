import json

from ffadv4manager import cli


def test_info_json_reports_fields_returned_by_m115(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("FFADV4MANAGER_CONFIG", str(tmp_path / "config.ini"))

    class Client:
        def __init__(self, *_args, **_kwargs):
            pass

        def info(self):
            return {"Machine Type": "Flashforge Adventurer 4", "Firmware": "v2.2.4"}

    monkeypatch.setattr(cli, "FlashForgeClient", Client)
    assert cli.main(["--host", "printer", "info", "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == {
        "Machine Type": "Flashforge Adventurer 4", "Firmware": "v2.2.4"
    }
