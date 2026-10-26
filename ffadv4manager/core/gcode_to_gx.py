"""Safe wrapper around the bundled HellEvro/FF_Gcode_to_GX-derived converter."""
from __future__ import annotations

import shutil
import struct
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .gx_converter.gx_writer import encode_gx
from .gx_converter.metadata import extract_metadata
from .gx_converter.printers.registry import resolve_profile
from .gx_converter.thumbnail import extract_thumbnail_bmp

GX_MAGIC = b"xgcode 1.0\n\0"
HEADER_SIZE = 58
BMP_SIZE = 14454
GCODE_OFFSET = HEADER_SIZE + BMP_SIZE
GCODE_SUFFIXES = {".gcode", ".gco", ".g"}


def is_gx(path: str | Path) -> bool:
    try:
        with Path(path).open("rb") as stream:
            return stream.read(len(GX_MAGIC)) == GX_MAGIC
    except OSError:
        return False


def validate_gx(path: str | Path) -> None:
    gx_path = Path(path)
    if gx_path.stat().st_size < GCODE_OFFSET:
        raise ValueError("converter output is not a valid GX file (bad magic or truncated layout)")
    with gx_path.open("rb") as stream:
        header = stream.read(HEADER_SIZE)
        if header[:len(GX_MAGIC)] != GX_MAGIC:
            raise ValueError("converter output is not a valid GX file (bad magic or truncated layout)")
        _reserved, bmp_offset, gcode_offset, duplicate_gcode_offset = struct.unpack_from(
            "<4I", header, len(GX_MAGIC)
        )
        stream.seek(HEADER_SIZE)
        bmp_signature = stream.read(2)
    if bmp_offset != HEADER_SIZE:
        raise ValueError("converter output has invalid BMP offset in its GX header")
    if gcode_offset != GCODE_OFFSET or duplicate_gcode_offset != GCODE_OFFSET:
        raise ValueError("converter output has invalid G-code offset in its GX header")
    if bmp_signature != b"BM":
        raise ValueError("converter output has no BMP signature at offset 58")


def convert_gcode_to_gx(source: str | Path, output: str | Path) -> Path:
    source_path, output_path = Path(source), Path(output)
    if source_path.suffix.casefold() not in GCODE_SUFFIXES:
        suffixes = ", ".join(sorted(GCODE_SUFFIXES))
        raise ValueError(f"automatic GX conversion supports only G-code suffixes: {suffixes}")
    if not source_path.is_file():
        raise FileNotFoundError(source_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ffadv4-gx-") as work:
        copy = Path(work) / source_path.name
        shutil.copyfile(source_path, copy)
        lines = copy.read_text(encoding="utf-8", errors="ignore").splitlines(keepends=True)
        if not lines:
            raise ValueError(f"Empty or unreadable file: {source_path}")
        profile = resolve_profile("adventurer4", lines=lines)
        metadata = extract_metadata(lines, profile=profile)
        gx_data = encode_gx(metadata, extract_thumbnail_bmp(lines), "".join(lines))
        copy.write_bytes(gx_data)
        validate_gx(copy)
        shutil.copyfile(copy, output_path)
    return output_path


@contextmanager
def upload_file(source: str | Path, *, no_convert: bool = False) -> Iterator[tuple[Path, str | None]]:
    """Yield upload file and remote name adjustment, cleaning converted temp output."""
    path = Path(source)
    if no_convert:
        yield path, None
        return
    if is_gx(path):
        remote_name = (
            path.name
            if path.suffix.casefold() == ".gx"
            else path.with_suffix(".gx").name
        )
        yield path, remote_name if remote_name != path.name else None
        return
    if path.suffix.casefold() not in GCODE_SUFFIXES:
        raise ValueError(f"cannot automatically convert {path.name!r}: expected .gcode, .gco, or .g")
    with tempfile.TemporaryDirectory(prefix="ffadv4-upload-gx-") as directory:
        converted = convert_gcode_to_gx(path, Path(directory) / (path.stem + ".gx"))
        yield converted, converted.name
