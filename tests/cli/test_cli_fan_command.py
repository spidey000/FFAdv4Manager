from ffadv4manager import cli


def test_fan_on_and_off_dispatch_to_part_cooling_controls(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("FFADV4MANAGER_CONFIG", str(tmp_path / "config.ini"))

    class Client:
        calls = []

        def __init__(self, *_args, **_kwargs):
            pass

        def set_fan(self, speed):
            self.calls.append(("M106", speed))
            return "ok"

        def fan_off(self):
            self.calls.append(("M107",))
            return "ok"

    monkeypatch.setattr(cli, "FlashForgeClient", Client)
    Client.calls.clear()
    assert cli.main(["--host", "printer", "fan", "on"]) == 0
    capsys.readouterr()
    assert cli.main(["--host", "printer", "fan", "off"]) == 0
    capsys.readouterr()
    assert Client.calls == [("M106", 255), ("M107",)]
