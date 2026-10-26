from ffadv4manager import cli


def test_root_help_is_comprehensive_and_does_not_connect(monkeypatch, capsys):
    def unexpected_client(*args, **kwargs):
        raise AssertionError("help must not construct a printer client")

    monkeypatch.setattr(cli, "FlashForgeClient", unexpected_client)

    assert cli.main(["help"]) == 0
    output = capsys.readouterr().out
    normalized_output = " ".join(output.split())
    assert "SUPPORTED COMMANDS" in output
    assert "FFADV4MANAGER_CONFIG" in output
    assert "not an encrypted or authenticated channel" in normalized_output
    assert "--force" in output
    assert "130" in output


def test_command_help_is_specific_and_does_not_resolve_host(monkeypatch, capsys):
    def unexpected_client(*args, **kwargs):
        raise AssertionError("help must not construct a printer client")

    monkeypatch.setattr(cli, "FlashForgeClient", unexpected_client)

    assert cli.main(["help", "upload"]) == 0
    assert "Upload a local G-code/GX file" in capsys.readouterr().out


def test_discover_help_documents_interactive_save_safeguards(capsys):
    assert cli.main(["help", "discover"]) == 0
    output = capsys.readouterr().out
    assert "port 8899" in output
    assert "not a TCP port scan" in output
    assert "JSON and non-interactive runs never prompt or save config" in output


def test_unknown_help_topic_returns_usage_error(capsys):
    assert cli.main(["help", "not-a-command"]) == 2
    assert "Unknown help topic" in capsys.readouterr().err
