"""Safe, informative remote GX filenames using the actual GX binary metadata."""
from __future__ import annotations

import re
import struct
import unicodedata
from pathlib import Path

from .gcode_to_gx import GX_MAGIC


# A model already bearing our prefix should not gain a duplicate prefix.
_OLD_PREFIX = re.compile(r"^(?:[0-9]{2,}_[0-9]{2}|--_--)_(?:[0-9]+\.[0-9]{2}|unknown)m_")


def gx_remote_filename(gx_path: str | Path, source_filename: str) -> str:
    """Return HH_mm_X.XXm_original.gx, with explicit unknown markers if absent.

    Read the actual GX header, not a rounded UI estimate or the temporary
    conversion filename. ASCII and length limits keep the M28 printer token safe.
    """
    path = Path(gx_path)
    with path.open("rb") as stream:
        header = stream.read(40)
    if len(header) < 40 or not header.startswith(GX_MAGIC):
        raise ValueError("Cannot name a non-GX upload from GX metadata")

    seconds, right_mm, left_mm = struct.unpack_from("<iii", header, 28)
    if seconds > 0:
        hours, minutes = divmod(seconds // 60, 60)
        duration = f"{hours:02d}_{minutes:02d}"
    else:
        duration = "--_--"

    filament_mm = max(0, right_mm) + max(0, left_mm)
    filament = f"{filament_mm / 1000:.2f}" if filament_mm else "unknown"

    original = Path(source_filename).stem
    original = _OLD_PREFIX.sub("", original)
    ascii_name = unicodedata.normalize("NFKD", original).encode("ascii", "ignore").decode("ascii")
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", ascii_name).strip("._-") or "unnamed"
    prefix = f"{duration}_{filament}m_"
    # Reserve room for .gx. Older printer firmware may reject long path tokens.
    max_stem = max(1, 100 - len(prefix) - len(".gx"))
    stem = stem[:max_stem].rstrip("._-") or "part"
    return f"{prefix}{stem}.gx"
