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
    img = image.convert("RGB").resize((BMP_WIDTH, BMP_HEIGHT), Image.Resampling.LANCZOS)
    pixels = bytearray()
    for y in range(BMP_HEIGHT - 1, -1, -1):
        for x in range(BMP_WIDTH):
            r, g, b = img.getpixel((x, y))
            pixels.extend((b, g, r))
    file_header = struct.pack("<2sIHHI", b"BM", GX_BMP_SIZE, 0, 0, 54)
    info_header = struct.pack("<IIIHHIIIIII", 40, BMP_WIDTH, BMP_HEIGHT, 1, 24, 0, len(pixels), 2835, 2835, 0, 0)
    data = file_header + info_header + bytes(pixels)
    if len(data) != GX_BMP_SIZE:
        raise RuntimeError(f"BMP size {len(data)} != {GX_BMP_SIZE}")
    return data


def blank_bmp() -> bytes:
    return _raw_bmp_rgb(Image.new("RGB", (BMP_WIDTH, BMP_HEIGHT), color=(255, 255, 255)))


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
