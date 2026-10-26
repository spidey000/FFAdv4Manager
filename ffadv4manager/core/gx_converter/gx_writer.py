"""GX serialization adapted from HellEvro/FF_Gcode_to_GX 1.1.0.
Copyright (C) 2026 Gcode_to_Gx contributors. Modified 2026-10-19 by FFADV4Manager
contributors. GPL-3.0-or-later; see LICENSE.
"""
from __future__ import annotations

import struct

from . import GX_BMP_OFFSET, GX_BMP_SIZE, GX_GCODE_OFFSET, GX_HEADER_SIZE
from .metadata import PrintMetadata

MAGIC = b"xgcode 1.0\n\0"


def build_header(meta: PrintMetadata) -> bytes:
    buff = MAGIC + struct.pack("<4i", 0, GX_BMP_OFFSET, GX_GCODE_OFFSET, GX_GCODE_OFFSET)
    buff += struct.pack("<iiih", max(meta.print_time, 1), meta.filament_right_mm,
                        meta.filament_left_mm, meta.multi_extruder_type)
    buff += struct.pack("<8h", meta.layer_height_um, 0, meta.perimeter_shells,
                        meta.print_speed, meta.bed_temp, meta.nozzle_right, meta.nozzle_left, 1)
    if len(buff) != GX_HEADER_SIZE:
        raise RuntimeError(f"Header size {len(buff)} != {GX_HEADER_SIZE}")
    return buff


def encode_gx(meta: PrintMetadata, bmp: bytes, gcode_text: str) -> bytes:
    if len(bmp) != GX_BMP_SIZE:
        raise ValueError(f"BMP must be {GX_BMP_SIZE} bytes, got {len(bmp)}")
    return build_header(meta) + bmp + gcode_text.encode("latin-1", errors="replace")
