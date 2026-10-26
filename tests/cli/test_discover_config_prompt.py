import io
import json
import sys

import pytest

from ffadv4manager import cli
from ffadv4manager import config as config_store
from ffadv4manager.core.discovery import DiscoveredPrinter


def _set_config(tmp_path, monkeypatch, values):
    path = tmp_path / "ffadv4manager.ini"
    monkeypatch.setenv("FFADV4MANAGER_CONFIG", str(path))
    monkeypatch.delenv("AD4CONNECT_CONFIG", raising=False)
    config_store.save_config(values)
    return path


def _mock_discovery(monkeypatch, printers):
    monkeypatch.setattr(cli, "discover_printers", lambda **_kwargs: printers)


def _fake_tty(monkeypatch):
    real_stdout = sys.stdout

    class TTYInput(io.StringIO):
        def isatty(self):
            return True

    class TTYOutput:
        def isatty(self):
            return True

        def write(self, value):
            return real_stdout.write(value)

        def flush(self):
            return real_stdout.flush()

    monkeypatch.setattr(cli.sys, "stdin", TTYInput())
    monkeypatch.setattr(cli.sys, "stdout", TTYOutput())


def test_single_eligible_printer_accepted_saves_host_and_preserves_other_settings(
    tmp_path, monkeypatch, capsys
):
    _set_config(tmp_path, monkeypatch, {"host": "old-host", "port": 9000, "timeout": 12})
    _mock_discovery(
        monkeypatch,
        [DiscoveredPrinter("Candidate", "192.168.1.42", 8899)],
    )
    _fake_tty(monkeypatch)
    answers = iter(["s"])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(answers))

    assert cli.main(["discover"]) == 0

    output = capsys.readouterr().out
    assert "192.168.1.42" in output
    assert "Puerto de comandos anunciado" in output
    assert "no se realizó un escaneo TCP" in output
    assert "Host predeterminado guardado" in output
    assert config_store.load_config() == {
        "host": "192.168.1.42",
        "port": "8899",
        "timeout": "12",
    }


def test_single_eligible_printer_rejected_does_not_change_config(
    tmp_path, monkeypatch, capsys
):
    _set_config(tmp_path, monkeypatch, {"host": "old-host", "port": 9000})
    _mock_discovery(
        monkeypatch,
        [DiscoveredPrinter("Candidate", "192.168.1.42", 8899)],
    )
    _fake_tty(monkeypatch)
    monkeypatch.setattr("builtins.input", lambda _prompt: "n")

    assert cli.main(["discover"]) == 0

    assert "configuración sin cambios" in capsys.readouterr().out
    assert config_store.load_config() == {"host": "old-host", "port": "9000"}


def test_multiple_eligible_printers_require_selection_and_confirmation(
    tmp_path, monkeypatch, capsys
):
    _set_config(
        tmp_path,
        monkeypatch,
        {"port": 9001, "timeout": 7, "camera_path": "/camera"},
    )
    _mock_discovery(
        monkeypatch,
        [
            DiscoveredPrinter("First", "192.168.1.41", 8899),
            DiscoveredPrinter("Second", "192.168.1.42", 8899),
        ],
    )
    _fake_tty(monkeypatch)
    answers = iter(["2", "sí"])
    prompts = []

    def answer(prompt):
        prompts.append(prompt)
        return next(answers)

    monkeypatch.setattr("builtins.input", answer)

    assert cli.main(["discover"]) == 0

    output = capsys.readouterr().out
    assert "1) First" in output and "2) Second" in output
    assert len(prompts) == 2
    assert config_store.load_config() == {
        "host": "192.168.1.42",
        "port": "8899",
        "timeout": "7",
        "camera_path": "/camera",
    }


def test_no_printer_advertises_8899_does_not_prompt_or_save(
    tmp_path, monkeypatch, capsys
):
    _set_config(tmp_path, monkeypatch, {"host": "old-host"})
    _mock_discovery(monkeypatch, [DiscoveredPrinter("Other", "192.168.1.43", 9021)])
    _fake_tty(monkeypatch)
    monkeypatch.setattr("builtins.input", lambda _prompt: pytest.fail("must not prompt"))
    monkeypatch.setattr(config_store, "save_config", lambda _values: pytest.fail("must not save"))

    assert cli.main(["discover"]) == 0

    assert "Ninguna impresora anuncia" in capsys.readouterr().out
    assert config_store.load_config() == {"host": "old-host"}


@pytest.mark.parametrize("json_output", [False, True], ids=["non-tty", "json-tty"])
def test_noninteractive_and_json_runs_never_prompt_or_save(
    tmp_path, monkeypatch, capsys, json_output
):
    _set_config(tmp_path, monkeypatch, {"host": "old-host", "port": 9000})
    _mock_discovery(
        monkeypatch,
        [DiscoveredPrinter("Candidate", "192.168.1.42", 8899)],
    )
    if json_output:
        _fake_tty(monkeypatch)
    else:
        monkeypatch.setattr(cli.sys, "stdin", io.StringIO())
    monkeypatch.setattr("builtins.input", lambda _prompt: pytest.fail("must not prompt"))
    monkeypatch.setattr(config_store, "save_config", lambda _values: pytest.fail("must not save"))

    argv = ["discover", "--json"] if json_output else ["discover"]
    assert cli.main(argv) == 0

    output = capsys.readouterr().out
    if json_output:
        assert json.loads(output) == [{"name": "Candidate", "ip": "192.168.1.42", "port": 8899}]
    else:
        assert "Candidate" in output
    assert config_store.load_config() == {"host": "old-host", "port": "9000"}
