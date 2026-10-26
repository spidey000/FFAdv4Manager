"""Persistent named printer connection profiles.

Profiles are kept separately from the application's global connection config.
"""

from __future__ import annotations

import json
import math
import os
import re
import tempfile
from pathlib import Path
from typing import Any

APP_NAME = "ffadv4manager"
PROFILE_KEYS = ("host", "port", "timeout", "camera_port", "camera_path")
_PROFILE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_. -]{0,63}\Z")


def profiles_path() -> Path:
    """Return the local persistent store path (independent of config.py)."""
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg).expanduser() if xdg else Path.home() / ".config"
    return base / APP_NAME / "profiles.json"


def _validate_name(name: str) -> str:
    if not isinstance(name, str) or not _PROFILE_NAME.fullmatch(name) or name in {".", ".."}:
        raise ValueError("profile name must be 1-64 safe letters, digits, spaces, '.', '_' or '-'")
    return name


def _validate_values(values: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(values, dict):
        raise ValueError("profile values must be a mapping")
    unknown = set(values) - set(PROFILE_KEYS)
    if unknown:
        raise ValueError(f"unsupported profile field(s): {', '.join(sorted(map(str, unknown)))}")
    checked: dict[str, Any] = {}
    for key, value in values.items():
        if key in ("port", "camera_port"):
            if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 65535:
                raise ValueError(f"{key} must be an integer between 1 and 65535")
        elif key == "timeout":
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                raise ValueError("timeout must be a positive finite number")
        elif key == "host":
            if not isinstance(value, str) or not value.strip() or "\x00" in value:
                raise ValueError("host must be a non-empty string")
        elif key == "camera_path":
            if not isinstance(value, str) or not value.startswith("/") or "\x00" in value:
                raise ValueError("camera_path must be an absolute URL path")
            if any(part in {".", ".."} for part in value.split("?", 1)[0].split("#", 1)[0].split("/")):
                raise ValueError("camera_path must not contain path traversal segments")
        checked[key] = value
    return checked


def _read() -> dict[str, dict[str, Any]]:
    path = profiles_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"could not read profiles store: {path}") from exc
    if not isinstance(data, dict):
        raise ValueError("profiles store must contain a JSON object")
    profiles: dict[str, dict[str, Any]] = {}
    for name, values in data.items():
        _validate_name(name)
        profiles[name] = _validate_values(values)
    return profiles


def _write(profiles: dict[str, dict[str, Any]]) -> None:
    path = profiles_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, prefix=".profiles-", delete=False) as stream:
            temp_name = stream.name
            json.dump(profiles, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, path)
    finally:
        if temp_name and os.path.exists(temp_name):
            os.unlink(temp_name)


def list_profiles() -> list[str]:
    """Return profile names in sorted order."""
    return sorted(_read())


def get_profile(name: str) -> dict[str, Any]:
    """Get a profile by name, raising KeyError when it does not exist."""
    name = _validate_name(name)
    try:
        return _read()[name]
    except KeyError:
        raise KeyError(name) from None


def add_profile(name: str, values: dict[str, Any]) -> None:
    """Create a named profile; duplicate names raise ValueError."""
    name = _validate_name(name)
    checked = _validate_values(values)
    profiles = _read()
    if name in profiles:
        raise ValueError(f"profile already exists: {name}")
    profiles[name] = checked
    _write(profiles)


def update_profile(name: str, values: dict[str, Any]) -> None:
    """Merge supported values into an existing profile."""
    name = _validate_name(name)
    checked = _validate_values(values)
    profiles = _read()
    if name not in profiles:
        raise KeyError(name)
    profiles[name].update(checked)
    _write(profiles)


def delete_profile(name: str) -> None:
    """Delete a profile; missing names raise KeyError."""
    name = _validate_name(name)
    profiles = _read()
    if name not in profiles:
        raise KeyError(name)
    del profiles[name]
    _write(profiles)
