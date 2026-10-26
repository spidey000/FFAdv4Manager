"""Local inspection helpers for G-code and FlashForge GX files."""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from pathlib import Path

_METADATA_PATTERNS = (
    ("slicer", re.compile(r"^generated\s+by\s+(.+?)\s*$", re.IGNORECASE)),
    ("layer_height", re.compile(r"^layer_height\s*=\s*(\S+)\s*$", re.IGNORECASE)),
    ("nozzle_diameter", re.compile(r"^nozzle_diameter\s*=\s*(\S+)\s*$", re.IGNORECASE)),
    ("filament_type", re.compile(r"^filament_type\s*=\s*(\S+)\s*$", re.IGNORECASE)),
    ("estimated_print_time", re.compile(
        r"^(?:estimated printing time \(normal mode\)|print time)\s*=\s*(.+?)\s*$",
        re.IGNORECASE,
    )),
)
_METADATA_SCAN_LIMIT = 1024 * 1024
_GCODE_SUFFIXES = {".gcode", ".gco", ".g"}


@dataclass(frozen=True)
class FileInspection:
    """A local-only summary of a file, with metadata only when safely recognized."""

    path: Path
    size_bytes: int
    sha256: str
    format: str
    metadata: dict[str, str]


def inspect_file(path: str | os.PathLike[str]) -> FileInspection:
    """Return file size, SHA-256, and narrowly recognized G-code comment metadata.

    GX files are treated as binary containers: their contents are never decoded or
    searched for text, so unsupported GX metadata is reported as an empty mapping.
    """
    file_path = Path(path)
    digest = hashlib.sha256()
    size = 0
    with file_path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
            size += len(chunk)

    suffix = file_path.suffix.lower()
    if suffix == ".gx":
        file_format = "gx"
        metadata: dict[str, str] = {}
    elif suffix in _GCODE_SUFFIXES:
        file_format = "gcode"
        metadata = _read_gcode_metadata(file_path)
    else:
        file_format = "unknown"
        metadata = {}

    return FileInspection(file_path, size, digest.hexdigest(), file_format, metadata)


def _read_gcode_metadata(path: Path) -> dict[str, str]:
    with path.open("rb") as stream:
        prefix = stream.read(_METADATA_SCAN_LIMIT)
    # G-code comments are text. Avoid interpreting binary or malformed files as text.
    if b"\x00" in prefix:
        return {}
    try:
        text = prefix.decode("utf-8")
    except UnicodeDecodeError:
        return {}

    metadata: dict[str, str] = {}
    for line in text.splitlines():
        comment = line.strip()
        if not comment.startswith(";"):
            continue
        comment = comment[1:].strip()
        for key, pattern in _METADATA_PATTERNS:
            match = pattern.fullmatch(comment)
            if match:
                metadata.setdefault(key, match.group(1).strip())
                break
    return metadata
