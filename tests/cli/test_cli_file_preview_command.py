from ffadv4manager import cli


def test_files_preview_writes_bmp_output(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("FFADV4MANAGER_CONFIG", str(tmp_path / "config.ini"))

    class Client:
        def __init__(self, *_args, **_kwargs):
            pass

        def preview_bmp(self, remote_name):
            assert remote_name == "part.gx"
            return b"BMcomplete-bitmap"

    monkeypatch.setattr(cli, "FlashForgeClient", Client)
    output = tmp_path / "preview.bmp"
    assert cli.main(["--host", "printer", "files", "preview", "part.gx", "--output", str(output)]) == 0
    assert output.read_bytes() == b"BMcomplete-bitmap"
    assert capsys.readouterr().out.strip() == str(output)
