import json

from ffadv4manager import cli, profiles


def test_profiles_subcommands_manage_named_connection(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    assert cli.main(["profiles", "add", "workshop", "--host", "printer.local", "--port", "8899"]) == 0
    assert "Profile added: workshop" in capsys.readouterr().out

    assert cli.main(["profiles", "show", "workshop"]) == 0
    assert json.loads(capsys.readouterr().out) == {"host": "printer.local", "port": 8899}

    assert cli.main(["profiles", "list"]) == 0
    assert json.loads(capsys.readouterr().out) == ["workshop"]

    assert cli.main(["profiles", "delete", "workshop"]) == 0
    capsys.readouterr()
    assert profiles.list_profiles() == []
