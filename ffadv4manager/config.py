"""Stored connection defaults for ffadv4manager.

Values are read from an INI file so the user does not have to pass --host,
camera port, and other defaults on every invocation. Resolution order used by
the CLI is:

    command-line flag  >  config file  >  built-in default
"""

from __future__ import annotations

import configparser
import os
from pathlib import Path

APP_NAME = "ffadv4manager"
LEGACY_APP_NAME = "ad4connect"
SECTION = "connection"
KEYS = ("host", "port", "timeout", "camera_port", "camera_path")


def _override_path() -> Path | None:
    """Configured file override, preferring the new variable over its legacy name."""
    override = os.environ.get("FFADV4MANAGER_CONFIG") or os.environ.get("AD4CONNECT_CONFIG")
    if override:
        return Path(override).expanduser()


def config_path() -> Path:
    """Writable config location; honors the new and legacy file overrides."""
    override = _override_path()
    if override is not None:
        return override
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg).expanduser() if xdg else Path.home() / ".config"
    return base / APP_NAME / "config.ini"


def _legacy_default_path() -> Path:
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg).expanduser() if xdg else Path.home() / ".config"
    return base / LEGACY_APP_NAME / "config.ini"


def _read_path() -> Path:
    path = config_path()
    if _override_path() is None and not path.exists():
        legacy_path = _legacy_default_path()
        if legacy_path.exists():
            return legacy_path
    return path


def _parser() -> configparser.ConfigParser:
    # interpolation=None so values like passwords or odd hostnames with '%' are literal.
    return configparser.ConfigParser(interpolation=None)


def load_config() -> dict[str, str]:
    """Return the stored [connection] values, or an empty dict if none."""
    path = _read_path()
    parser = _parser()
    if path.exists():
        parser.read(path)
    if parser.has_section(SECTION):
        return {k: v for k, v in parser[SECTION].items() if k in KEYS}
    return {}


def save_config(values: dict[str, object]) -> Path:
    """Merge ``values`` into the stored config and write it, returning the path."""
    path = config_path()
    parser = _parser()
    source = path if path.exists() else _read_path()
    if source.exists():
        parser.read(source)
    if not parser.has_section(SECTION):
        parser.add_section(SECTION)
    for key, value in values.items():
        parser.set(SECTION, key, str(value))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as fh:
        parser.write(fh)
    return path


def unset_config(keys: list[str]) -> list[str]:
    """Remove the given keys from the stored config; return the ones that existed."""
    path = config_path()
    source = path if path.exists() else _read_path()
    if not source.exists():
        return []
    parser = _parser()
    parser.read(source)
    if not parser.has_section(SECTION):
        return []
    removed = [k for k in keys if parser.remove_option(SECTION, k)]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as fh:
        parser.write(fh)
    return removed
