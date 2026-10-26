import json

from ffadv4manager import cli


def test_position_json_reports_m114_coordinates(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("FFADV4MANAGER_CONFIG", str(tmp_path / "config.ini"))

    class Client:
        def __init__(self, *_args, **_kwargs):
            pass

        def position(self):
            return {"X": 22.5, "Y": 10.0, "Z": 3.25}

    monkeypatch.setattr(cli, "FlashForgeClient", Client)
    assert cli.main(["--host", "printer", "position", "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == {"X": 22.5, "Y": 10.0, "Z": 3.25}
