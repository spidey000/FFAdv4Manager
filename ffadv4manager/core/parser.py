from __future__ import annotations

import re
from .models import PrinterStatus

_TEMP_RE = re.compile(r"T0:(-?\d+)/(\d+)\s+B:(-?\d+)/(\d+)")
_SD_RE = re.compile(r"SD printing byte\s+(\d+)/(\d+)")
_LAYER_RE = re.compile(r"Layer:\s*(\d+)/(\d+)")
_POSITION_RE = re.compile(r"\b([XYZABCE]):\s*(-?\d+(?:\.\d+)?)", re.IGNORECASE)


def parse_status(*responses: str) -> PrinterStatus:
    raw = "\n".join(r for r in responses if r)
    machine_status = _value_after(raw, "MachineStatus:")
    move_mode = _value_after(raw, "MoveMode:")
    current_file = _value_after(raw, "CurrentFile:")

    nozzle_current = nozzle_target = bed_current = bed_target = None
    temp = _TEMP_RE.search(raw)
    if temp:
        nozzle_current, nozzle_target, bed_current, bed_target = map(int, temp.groups())

    sd_current = sd_total = None
    sd = _SD_RE.search(raw)
    if sd:
        sd_current, sd_total = map(int, sd.groups())

    layer_current = layer_total = None
    layer = _LAYER_RE.search(raw)
    if layer:
        layer_current, layer_total = map(int, layer.groups())

    return PrinterStatus(
        raw=raw,
        machine_status=machine_status,
        move_mode=move_mode,
        current_file=current_file,
        nozzle_current=nozzle_current,
        nozzle_target=nozzle_target,
        bed_current=bed_current,
        bed_target=bed_target,
        sd_current=sd_current,
        sd_total=sd_total,
        layer_current=layer_current,
        layer_total=layer_total,
    )


def parse_file_list(response: str) -> list[str]:
    # The printer returns binary-ish separators around /data/file.ext entries.
    names = re.findall(r"/data/[^:\x00\r\n]+", response)
    cleaned: list[str] = []
    for name in names:
        name = name.strip()
        if name and name not in cleaned:
            cleaned.append(name)
    return cleaned


def parse_info(response: str) -> dict[str, str]:
    """Parse the key/value lines commonly returned by M115 without assuming fields."""
    result: dict[str, str] = {}
    for line in response.splitlines():
        line = line.strip()
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key, value = key.strip(), value.strip()
        if key and value:
            result[key] = value
    return result


def parse_position(response: str) -> dict[str, float]:
    """Parse reported axes from M114; axes absent from the response stay absent."""
    return {axis.upper(): float(value) for axis, value in _POSITION_RE.findall(response)}


def _value_after(text: str, prefix: str) -> str | None:
    for line in text.splitlines():
        line = line.strip()
        if line.startswith(prefix):
            return line[len(prefix):].strip() or None
    return None
