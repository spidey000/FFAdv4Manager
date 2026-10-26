"""Reusable, read-only layer estimation from a local G-code/GX toolpath and M114 Z.

The firmware's M27 Layer field may stay at 0/0 on Adventurer 4 v2.2.4.
Layer numbers derived here are estimates, never firmware-reported facts.
"""
from __future__ import annotations

from bisect import bisect_left
from dataclasses import dataclass
import json
import math
from pathlib import Path
import re

GX_GCODE_OFFSET = 14512
_COMMAND = re.compile(r"^\s*(?:N\d+\s+)?(G0?0|G0?1|G90|G91|G92|M82|M83)\b", re.I)
_AXIS = re.compile(r"([XYZE])\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))", re.I)
MAX_LAYERS = 20000


@dataclass(frozen=True)
class LayerIndex:
    """Sorted physical extrusion heights (millimetres), 1-indexed to the user."""

    heights: tuple[float, ...]

    def __post_init__(self) -> None:
        if (not self.heights or len(self.heights) > MAX_LAYERS or
                any(not isinstance(h, (int, float)) or not math.isfinite(h) or
                    h <= 0 or h > 500 for h in self.heights) or
                any(b <= a for a, b in zip(self.heights, self.heights[1:]))):
            raise ValueError("invalid layer height index")

    @classmethod
    def from_file(cls, filename: str | Path) -> "LayerIndex":
        path = Path(filename)
        if path.suffix.lower() not in (".g", ".gco", ".gcode", ".gx"):
            raise ValueError("expected a G-code or GX file")
        heights: set[float] = set()
        relative_xyz = False
        relative_e = False
        x = y = z = e = 0.0

        with path.open("rb") as stream:
            magic = stream.read(12)
            if path.suffix.lower() == ".gx":
                if magic != b"xgcode 1.0\n\x00":
                    raise ValueError("GX file does not have a supported xgcode header")
                if path.stat().st_size <= GX_GCODE_OFFSET:
                    raise ValueError("GX file contains no G-code")
                stream.seek(GX_GCODE_OFFSET)
            else:
                stream.seek(0)

            for raw in stream:
                line = raw.decode("latin-1").split(";", 1)[0].strip()
                match = _COMMAND.match(line)
                if not match:
                    continue
                cmd = match.group(1).upper()
                if cmd == "G90":
                    relative_xyz = False
                    continue
                if cmd == "G91":
                    relative_xyz = True
                    continue
                if cmd == "M82":
                    relative_e = False
                    continue
                if cmd == "M83":
                    relative_e = True
                    continue
                coords = {}
                for axis, value in _AXIS.findall(line[match.end():]):
                    coords[axis.upper()] = float(value)
                if cmd == "G92":
                    x = coords.get("X", x)
                    y = coords.get("Y", y)
                    z = coords.get("Z", z)
                    e = coords.get("E", e)
                    continue
                nx = x + coords["X"] if relative_xyz and "X" in coords else coords.get("X", x)
                ny = y + coords["Y"] if relative_xyz and "Y" in coords else coords.get("Y", y)
                nz = z + coords["Z"] if relative_xyz and "Z" in coords else coords.get("Z", z)
                ne = e + coords["E"] if relative_e and "E" in coords else coords.get("E", e)
                # Only extrusion along an XY segment counts. Z-hops and E-only
                # priming/retractions must not add fictitious layers.
                if ("E" in coords and ne > e + 0.0001 and
                        (abs(nx - x) > 0.0001 or abs(ny - y) > 0.0001) and
                        0 < nz <= 500 and math.isfinite(nz)):
                    heights.add(round(nz, 3))
                    if len(heights) > MAX_LAYERS:
                        raise ValueError("too many distinct extrusion heights")
                x, y, z, e = nx, ny, nz, ne

        ordered = sorted(heights)
        # Merge tiny floating-point variations, but preserve variable-height
        # layers whose separation is at least 0.02 mm.
        merged = []
        for height in ordered:
            if not merged or height - merged[-1] >= 0.02:
                merged.append(height)
        if not merged:
            raise ValueError("no printable layers found in G-code")
        return cls(tuple(merged))

    @classmethod
    def from_json_file(cls, path: str | Path) -> "LayerIndex":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if payload.get("version") != 1 or not isinstance(payload.get("heights"), list):
            raise ValueError("unsupported layer index")
        return cls(tuple(payload["heights"]))

    def as_dict(self) -> dict:
        return {"version": 1, "heights": list(self.heights), "layer_total": len(self.heights)}

    def candidate_at_z(self, z_mm: float | None, *, tolerance: float = 0.06) -> int | None:
        """Return a 1-based index only when Z is near a known extrusion plane.

        This avoids treating most Z-hop/inter-layer travel heights as a new layer.
        A hop landing exactly on another known plane is still ambiguous; callers
        must debounce readings and label the result as an estimate.
        """
        if z_mm is None or not isinstance(z_mm, (float, int)) or not math.isfinite(z_mm):
            return None
        pos = bisect_left(self.heights, z_mm)
        nearest = [i for i in (pos - 1, pos) if 0 <= i < len(self.heights)]
        if not nearest:
            return None
        i = min(nearest, key=lambda item: abs(self.heights[item] - z_mm))
        return i + 1 if abs(self.heights[i] - z_mm) <= tolerance else None


class LayerTracker:
    """Monotonic, debounced layer observations for status and timelapse events."""

    def __init__(self, index: LayerIndex, *, stable_samples: int = 2):
        if stable_samples < 1:
            raise ValueError("stable_samples must be positive")
        self.index = index
        self.stable_samples = stable_samples
        self.layer: int | None = None
        self._candidate: int | None = None
        self._seen = 0

    def observe(self, z_mm: float | None) -> bool:
        """Return True exactly when a new higher layer becomes established."""
        candidate = self.index.candidate_at_z(z_mm)
        if candidate is None or (self.layer is not None and candidate <= self.layer):
            self._candidate = None
            self._seen = 0
            return False
        if candidate != self._candidate:
            self._candidate = candidate
            self._seen = 1
        else:
            self._seen += 1
        if self._seen < self.stable_samples:
            return False
        self.layer = candidate
        self._candidate = None
        self._seen = 0
        return True
