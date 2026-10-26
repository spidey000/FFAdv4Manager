import json

import pytest

from ffadv4manager import profiles


@pytest.fixture
def isolated_store(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    return profiles.profiles_path()


def test_profiles_crud_and_persistence(isolated_store):
    values = {"host": "printer.local", "port": 8899, "timeout": 3.5,
              "camera_port": 8080, "camera_path": "/webcam/?action=stream"}
    assert profiles.list_profiles() == []
    profiles.add_profile("Workshop Printer", values)
    assert profiles.list_profiles() == ["Workshop Printer"]
    assert profiles.get_profile("Workshop Printer") == values
    profiles.update_profile("Workshop Printer", {"host": "192.0.2.10"})
    assert profiles.get_profile("Workshop Printer")["host"] == "192.0.2.10"
    assert profiles.get_profile("Workshop Printer")["port"] == 8899
    assert json.loads(isolated_store.read_text())["Workshop Printer"]["host"] == "192.0.2.10"
    profiles.delete_profile("Workshop Printer")
    assert profiles.list_profiles() == []


@pytest.mark.parametrize("name", ["../escape", "a/b", "a\\b", "", ".", "bad\x00name"])
def test_rejects_unsafe_profile_names(isolated_store, name):
    with pytest.raises(ValueError):
        profiles.add_profile(name, {"host": "printer"})
    assert not isolated_store.exists()


@pytest.mark.parametrize("values", [
    {"unknown": "value"}, {"port": 0}, {"port": True}, {"timeout": float("inf")},
    {"camera_path": "/../../etc/passwd"}, {"camera_path": "relative/path"},
])
def test_rejects_invalid_values(isolated_store, values):
    with pytest.raises(ValueError):
        profiles.add_profile("printer", values)
    assert not isolated_store.exists()


def test_missing_and_duplicate_profile_errors(isolated_store):
    with pytest.raises(KeyError):
        profiles.get_profile("absent")
    profiles.add_profile("printer", {"host": "printer"})
    with pytest.raises(ValueError):
        profiles.add_profile("printer", {})
    with pytest.raises(KeyError):
        profiles.update_profile("absent", {})
    with pytest.raises(KeyError):
        profiles.delete_profile("absent")


def test_uses_home_when_xdg_not_set(tmp_path, monkeypatch):
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    assert profiles.profiles_path() == tmp_path / ".config" / "ffadv4manager" / "profiles.json"
