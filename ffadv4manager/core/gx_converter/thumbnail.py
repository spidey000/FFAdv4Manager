"""Thumbnail conversion adapted from HellEvro/FF_Gcode_to_GX 1.1.0.
Copyright (C) 2026 Gcode_to_Gx contributors. Modified 2026-10-19 by FFADV4Manager
contributors. GPL-3.0-or-later; see LICENSE.
"""
from __future__ import annotations

import base64
import struct
from io import BytesIO

from PIL import Image

from . import BMP_HEIGHT, BMP_WIDTH, GX_BMP_SIZE


def _raw_bmp_rgb(image: Image.Image) -> bytes:
    rgba = image.convert("RGBA").resize((BMP_WIDTH, BMP_HEIGHT), Image.Resampling.LANCZOS)
    background = Image.new("RGBA", (BMP_WIDTH, BMP_HEIGHT), (0, 0, 0, 255))
    background.alpha_composite(rgba)
    img = background.convert("L")
    pixels = bytearray()
    for y in range(BMP_HEIGHT - 1, -1, -1):
        for x in range(BMP_WIDTH):
            gray = img.getpixel((x, y))
            pixels.extend((gray, gray, gray))
    file_header = struct.pack("<2sIHHI", b"BM", GX_BMP_SIZE, 0, 0, 54)
    info_header = struct.pack("<IIIHHIIIIII", 40, BMP_WIDTH, BMP_HEIGHT, 1, 24, 0, len(pixels), 4724, 4724, 0, 0)
    data = file_header + info_header + bytes(pixels)
    if len(data) != GX_BMP_SIZE:
        raise RuntimeError(f"BMP size {len(data)} != {GX_BMP_SIZE}")
    return data


def blank_bmp() -> bytes:
    return _raw_bmp_rgb(Image.new("RGB", (BMP_WIDTH, BMP_HEIGHT), color=(0, 0, 0)))


def extract_thumbnail_bmp(lines: list[str]) -> bytes:
    chunks: list[str] = []
    inside = False
    for line in lines:
        if "thumbnail begin" in line:
            inside = True
            continue
        if "thumbnail end" in line:
            break
        if inside:
            chunks.append(line.strip().lstrip(";").strip())
    if not chunks:
        return blank_bmp()
    try:
        image = Image.open(BytesIO(base64.b64decode("".join(chunks), validate=False)))
        return _raw_bmp_rgb(image)
    except Exception:
        return blank_bmp()
