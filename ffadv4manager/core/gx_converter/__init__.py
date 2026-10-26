"""Bundled GX format code adapted from HellEvro/FF_Gcode_to_GX 1.1.0.

Copyright (C) 2026 Gcode_to_Gx contributors. Modified 2026-10-19 by FFADV4Manager
contributors. Source commit: b44b5760671594e4c0a0234131adc7f398338349.
Distributed under GPL-3.0-or-later; see the repository LICENSE. Relative
imports below keep the adaptation vendored.
"""

GX_HEADER_SIZE = 58
GX_BMP_OFFSET = 58
GX_GCODE_OFFSET = 14512
GX_BMP_SIZE = GX_GCODE_OFFSET - GX_BMP_OFFSET
BMP_WIDTH = 80
BMP_HEIGHT = 60
