from ffadv4manager import cli


def test_printer_rename_verifies_reported_name_with_m115(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("FFADV4MANAGER_CONFIG", str(tmp_path / "config.ini"))

    class Client:
        def __init__(self, *_args, **_kwargs):
            self.name = None

        def rename(self, name):
            self.name = name
            return "M610 acknowledged\nok"

        def info(self):
            return {"Machine Name": self.name}

    monkeypatch.setattr(cli, "FlashForgeClient", Client)
    assert cli.main(["--host", "printer", "printer", "rename", "workshop-ad4"]) == 0
    assert capsys.readouterr().out.strip() == "M610 acknowledged\nok"
