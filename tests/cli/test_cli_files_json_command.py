import json

from ffadv4manager import cli


def test_files_json_emits_remote_paths_as_array(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("FFADV4MANAGER_CONFIG", str(tmp_path / "config.ini"))

    class Client:
        def __init__(self, *_args, **_kwargs):
            pass

        def files(self):
            return ["/data/first.gcode", "0:/user/second.gx"]

    monkeypatch.setattr(cli, "FlashForgeClient", Client)
    assert cli.main(["--host", "printer", "files", "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == ["/data/first.gcode", "0:/user/second.gx"]
