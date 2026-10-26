"""Parse slicer comments into FlashForge GX xgcode 1.0 metadata.

The binary header stores duration, filament length, layer height, shell count,
print speed and heater temperatures. Missing duration is UNKNOWN (0), not an
invented one-second print. This module never modifies executable G-code.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .printers.registry import PrinterProfile


@dataclass
class PrintMetadata:
    print_time: int = 0
    filament_right_mm: int = 0
    filament_left_mm: int = 0
    layer_height_um: int = 0
    print_speed: int = 60
    bed_temp: int = 0
    nozzle_right: int = 0
    nozzle_left: int = 0
    multi_extruder_type: int = 1
    perimeter_shells: int = 2


def _parse_int_list(value: str) -> list[int]:
    parsed = []
    for part in value.split(","):
        try:
            number = float(part.strip())
            if 0 <= number <= 2147483647:
                parsed.append(round(number))
        except ValueError:
            pass
    return parsed


def _parse_print_time(value: str) -> int:
    """Accept Prusa/Orca '1h 2m 3s', HH:MM:SS, MM:SS and numeric seconds."""
    value = value.strip().lower()
    try:
        if re.fullmatch(r"\d+(?:\.\d+)?(?:\s*(?:s|sec|seconds))?", value):
            return max(0, round(float(re.match(r"\d+(?:\.\d+)?", value).group())))
        if re.fullmatch(r"\d{1,3}:\d{1,2}(?::\d{1,2})?", value):
            parts = [int(part) for part in value.split(":")]
            if len(parts) == 2:
                return parts[0] * 60 + parts[1]
            return parts[0] * 3600 + parts[1] * 60 + parts[2]
        matches = list(re.finditer(r"(\d+(?:\.\d+)?)\s*(h|m|s)\b", value))
        if matches:
            seconds = sum(float(m.group(1)) * {"h": 3600, "m": 60, "s": 1}[m.group(2)] for m in matches)
            return max(0, round(seconds))
    except (ValueError, OverflowError):
        pass
    return 0


def extract_metadata(lines: list[str], profile: PrinterProfile | None = None) -> PrintMetadata:
    meta = PrintMetadata()
    speed_priority = -1
    time_keys = {
        "estimated printing time (normal mode)", "estimated printing time",
        "print time", "print_time", "estimated_print_time", "estimated_time", "time",
    }
    speed_keys = {
        "machine_max_speed_x": 0, "sparse_infill_speed": 1,
        "default_print_speed": 2, "perimeter_speed": 3,
        "outer_wall_speed": 3, "print_speed": 4,
    }
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith(";"):
            continue
        comment = stripped[1:].strip()
        if "=" in comment:
            key, value = comment.split("=", 1)
        elif ":" in comment:
            key, value = comment.split(":", 1)
        else:
            continue
        key, value = key.strip().lower(), value.strip()
        if key in time_keys:
            parsed = _parse_print_time(value)
            if parsed > 0:
                meta.print_time = min(parsed, 2147483647)
        elif key in ("filament used [mm]", "filament_mm", "filament used [m]"):
            if key == "filament used [m]":
                vals = []
                for part in value.split(","):
                    try:
                        metres = float(part.strip())
                        if 0 <= metres <= 2147483:
                            vals.append(round(metres * 1000))
                    except ValueError:
                        continue
            else:
                vals = _parse_int_list(value)
            if vals:
                meta.filament_right_mm = vals[0]
            if len(vals) > 1:
                meta.filament_left_mm = vals[1]
        elif key in ("layer_height", "layer height"):
            try:
                height = float(value.split()[0])
                if 0 <= height < 32:
                    meta.layer_height_um = round(height * 1000)
            except (ValueError, IndexError):
                pass
        elif key in speed_keys and speed_keys[key] >= speed_priority:
            vals = _parse_int_list(value)
            if vals and 0 <= vals[0] <= 32767:
                meta.print_speed = vals[0]
                speed_priority = speed_keys[key]
        elif key in ("first_layer_bed_temperature", "bed_temperature", "platform_temperature"):
            vals = _parse_int_list(value)
            if vals and vals[0] <= 32767:
                meta.bed_temp = vals[0]
        elif key in ("nozzle_temperature", "first_layer_temperature", "temperature", "right_extruder_temperature"):
            vals = _parse_int_list(value)
            if vals and vals[0] <= 32767:
                meta.nozzle_right = vals[0]
            if len(vals) > 1 and vals[1] <= 32767:
                meta.nozzle_left = vals[1]
        elif key in ("wall_loops", "wall_line_count", "perimeters", "perimeter_shells"):
            vals = _parse_int_list(value)
            if vals and vals[0] <= 32767:
                meta.perimeter_shells = vals[0]
    if profile:
        meta.multi_extruder_type = profile.multi_extruder_type
        if not profile.dual:
            meta.filament_left_mm = 0
            meta.nozzle_left = 0
    return meta
