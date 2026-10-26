"""Adapted from HellEvro/FF_Gcode_to_GX 1.1.0, commit b44b576.
Copyright (C) 2026 Gcode_to_Gx contributors. Modified 2026-10-19 by FFADV4Manager
contributors. GPL-3.0-or-later; see LICENSE.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class PrinterProfile:
    id: str
    name: str
    dual: bool
    multi_extruder_type: int


_PROFILES = {
    "adventurer3": PrinterProfile("adventurer3", "Flashforge Adventurer 3", False, 0),
    "adventurer4": PrinterProfile("adventurer4", "Flashforge Adventurer 4", False, 0),
    "adventurer5m": PrinterProfile("adventurer5m", "Flashforge Adventurer 5M", False, 0),
    "creator3pro": PrinterProfile("creator3pro", "Flashforge Creator 3 Pro", True, 1),
    "generic_single": PrinterProfile("generic_single", "Generic Flashforge (single extruder)", False, 0),
    "generic_dual": PrinterProfile("generic_dual", "Generic Flashforge (dual extruder)", True, 1),
}


def get_profile(printer_id: str) -> PrinterProfile:
    key = printer_id.strip().lower()
    try:
        return _PROFILES[key]
    except KeyError as exc:
        raise ValueError(f"Unknown printer {printer_id!r}. Known IDs: {', '.join(_PROFILES)}") from exc


def detect_dual_from_gcode(lines: list[str]) -> bool:
    filament_vals: list[float] = []
    nozzle_vals: list[float] = []
    has_t1 = False
    for line in lines:
        stripped = line.strip()
        if re.match(r"^T1\b", stripped, flags=re.IGNORECASE):
            has_t1 = True
        if stripped.startswith(";") and "=" in stripped:
            key, _, value = stripped[1:].strip().partition("=")
            key, value = key.strip().lower(), value.strip()
            if key.startswith("filament used [mm]"):
                filament_vals = _float_list(value)
            elif key in ("nozzle_temperature", "first_layer_temperature"):
                nozzle_vals = _float_list(value)
    return (len(filament_vals) >= 2 and filament_vals[1] > 0) or len(nozzle_vals) >= 2 or has_t1


def _float_list(value: str) -> list[float]:
    out = []
    for part in value.split(","):
        try:
            out.append(float(part.strip().replace(",", ".")))
        except ValueError:
            continue
    return out


def resolve_profile(printer_id: str | None = None, *, lines: list[str] | None = None) -> PrinterProfile:
    if printer_id:
        return get_profile(printer_id)
    dual = detect_dual_from_gcode(lines or [])
    return get_profile("generic_dual" if dual else "generic_single")
