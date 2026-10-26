"""Printer profiles adapted from HellEvro/FF_Gcode_to_GX 1.1.0 (GPL-3.0-or-later).
Copyright (C) 2026 Gcode_to_Gx contributors. Modified 2026-10-19 by FFADV4Manager
contributors. See LICENSE.
"""

from .registry import PrinterProfile, get_profile, resolve_profile

__all__ = ["PrinterProfile", "get_profile", "resolve_profile"]
