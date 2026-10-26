import importlib

import pytest


@pytest.fixture()
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("FFADV4MANAGER_CONFIG", str(tmp_path / "config.ini"))
    monkeypatch.delenv("AD4CONNECT_CONFIG", raising=False)
    from ffadv4manager import config as config_store

    importlib.reload(config_store)
    return config_store


def test_load_empty_when_no_file(store):
    assert store.load_config() == {}


def test_save_then_load_roundtrip(store):
    store.save_config({"host": "192.168.1.50", "port": 8899})
    loaded = store.load_config()
    assert loaded["host"] == "192.168.1.50"
    assert loaded["port"] == "8899"


def test_save_merges_without_dropping_keys(store):
    store.save_config({"host": "10.0.0.5"})
    store.save_config({"port": 9999})
    loaded = store.load_config()
    assert loaded == {"host": "10.0.0.5", "port": "9999"}


def test_unset_removes_only_requested_keys(store):
    store.save_config({"host": "10.0.0.5", "port": 8899})
    removed = store.unset_config(["port"])
    assert removed == ["port"]
    assert store.load_config() == {"host": "10.0.0.5"}


def test_unset_missing_key_is_noop(store):
    store.save_config({"host": "10.0.0.5"})
    assert store.unset_config(["timeout"]) == []


def test_config_path_honours_override(store, tmp_path):
    assert store.config_path() == tmp_path / "config.ini"


def test_legacy_env_is_used_when_new_env_is_absent(tmp_path, monkeypatch):
    legacy_override = tmp_path / "legacy-override.ini"
    monkeypatch.delenv("FFADV4MANAGER_CONFIG", raising=False)
    monkeypatch.setenv("AD4CONNECT_CONFIG", str(legacy_override))
    from ffadv4manager import config as config_store

    assert config_store.config_path() == legacy_override


def test_new_env_takes_precedence_over_legacy_env(tmp_path, monkeypatch):
    new_override = tmp_path / "new.ini"
    monkeypatch.setenv("FFADV4MANAGER_CONFIG", str(new_override))
    monkeypatch.setenv("AD4CONNECT_CONFIG", str(tmp_path / "legacy.ini"))
    from ffadv4manager import config as config_store

    assert config_store.config_path() == new_override


def test_reads_legacy_default_but_writes_new_default_without_changing_legacy(
    tmp_path, monkeypatch
):
    monkeypatch.delenv("FFADV4MANAGER_CONFIG", raising=False)
    monkeypatch.delenv("AD4CONNECT_CONFIG", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    from ffadv4manager import config as config_store

    legacy_path = tmp_path / "ad4connect" / "config.ini"
    new_path = tmp_path / "ffadv4manager" / "config.ini"
    legacy_path.parent.mkdir()
    legacy_contents = "[connection]\nhost = 192.168.1.50\nport = 8899\n"
    legacy_path.write_text(legacy_contents)

    assert config_store.config_path() == new_path
    assert config_store.load_config() == {"host": "192.168.1.50", "port": "8899"}
    config_store.save_config({"timeout": 12})

    assert config_store.load_config() == {
        "host": "192.168.1.50",
        "port": "8899",
        "timeout": "12",
    }
    assert legacy_path.read_text() == legacy_contents
    assert new_path.exists()


def test_unset_migrates_legacy_values_to_new_path(tmp_path, monkeypatch):
    monkeypatch.delenv("FFADV4MANAGER_CONFIG", raising=False)
    monkeypatch.delenv("AD4CONNECT_CONFIG", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    from ffadv4manager import config as config_store

    legacy_path = tmp_path / "ad4connect" / "config.ini"
    new_path = tmp_path / "ffadv4manager" / "config.ini"
    legacy_path.parent.mkdir()
    legacy_path.write_text("[connection]\nhost = 192.168.1.50\nport = 8899\n")

    assert config_store.unset_config(["port"]) == ["port"]
    assert config_store.load_config() == {"host": "192.168.1.50"}
    assert "port = 8899" in legacy_path.read_text()
    assert new_path.exists()
