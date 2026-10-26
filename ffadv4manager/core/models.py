from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PrinterStatus:
    raw: str
    machine_status: str | None = None
    move_mode: str | None = None
    current_file: str | None = None
    nozzle_current: int | None = None
    nozzle_target: int | None = None
    bed_current: int | None = None
    bed_target: int | None = None
    sd_current: int | None = None
    sd_total: int | None = None
    layer_current: int | None = None
    layer_total: int | None = None

    @property
    def is_printing(self) -> bool:
        return self.machine_status in {"BUILDING_FROM_SD", "BUILDING", "PRINTING"}

    @property
    def progress_percent(self) -> float | None:
        if self.sd_total and self.sd_total > 0 and self.sd_current is not None:
            return min(100.0, max(0.0, (self.sd_current / self.sd_total) * 100.0))
        return None
