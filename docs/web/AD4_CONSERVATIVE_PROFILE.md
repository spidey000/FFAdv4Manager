# Conservative speed and acceleration defaults — Flashforge Adventurer 4

This project defaults to **`0.20mm Quality (Conservative) @Flashforge AD4 0.4 Nozzle`**, a local quality-oriented *process* based on the stock OrcaSlicer `0.20mm Standard @Flashforge AD4 0.4 Nozzle`. It is selected on startup for the **standard 0.4 mm nozzle**, even if high-speed firmware is installed.

All bundled process presets compatible with the fixed Adventurer 4 use the **same cautious speed/acceleration overlay** when selected. The original OrcaSlicer entries remain available by name, but their motion settings are intentionally normalized; other parameters such as layer height are preserved. **Named custom processes** are the exception: they restore exactly the process values that you saved, including deliberate speed changes. No upstream npm package or printer firmware is modified.

## Why this deliberately slower profile?

- Flashforge's original Adventurer 4 manual states a **10–150 mm/s construction speed**, not a quality recommendation or an acceleration guarantee.
- The standard FlashPrint configuration reviewed by Tom's Hardware uses **60 mm/s print speed**. FlashPrint documentation shows **60 mm/s print** and **80 mm/s travel** as an example.
- Flashforge Japan specifically recommends **60 mm/s or less for small Adventurer 4 prints**.
- Flashforge's high-speed upgrade is marketed as **up to 200 mm/s and 10,000 mm/s²**, but its installation guide includes **a matching HS nozzle, firmware and slicer profile**. A high-speed firmware installation alone does not certify the standard nozzle or mechanics for these numbers.
- Community reports describe layer shifts on some Adventurer 4 units with the high-speed update. This is anecdotal, not proof of the cause for any particular unit.

### Process speeds (mm/s)

| Feature | Orca standard | Conservative default |
| --- | ---: | ---: |
| First layer | 35 | **20** |
| First-layer infill | 50 | **25** |
| First-layer travel | 150 | **70** |
| Outer wall | 50 | **35** |
| Inner wall | 100 | **50** |
| Sparse infill | 60 | **55** |
| Solid infill | 50 | **45** |
| Top surface | 35 | **30** |
| Gap fill | 50 | **30** |
| Support | 100 | **50** |
| Support interface | 80 | **40** |
| Travel | 80 | **80** |
| Ironing | 15 | **15** |
| Small perimeter | 50% | **50% of outer wall** |
| Bridge | 25 | **25** |
| Skirt | 20 | **20** |

### Process accelerations (mm/s²)

| Feature | Orca standard | Conservative default |
| --- | ---: | ---: |
| Default | 5000 | **800** |
| First layer | 50 | **300** |
| Outer wall | 1000 | **450** |
| Inner wall | 1000 | **700** |
| Sparse infill | inherited | **800** |
| Solid infill | 1000 | **650** |
| Top surface | 50 | **400** |
| Travel | 5000 | **1000** |
| First-layer travel | inherited | **500** |
| Bridge | inherited | **500** |

**These acceleration values are intentionally conservative engineering starting points, not manufacturer-certified quality limits.** We did not find a reliable official low-speed/normal-firmware AD4 quality acceleration table. Verify behavior with a first-layer test, calibration cube and a small print while observing the actual machine.

### Machine profile ceilings used by the web slicer

| Setting | Conservative value |
| --- | ---: |
| Machine max X/Y speed | 90 mm/s |
| Machine max X/Y acceleration | 1200 mm/s² |
| Machine max extrusion acceleration | 1200 mm/s² |
| Machine max travel acceleration | 1200 mm/s² |
| Machine max retract acceleration | 1500 mm/s² |
| Machine max X/Y jerk | 7 mm/s (used for estimates; firmware jerk is not forcibly changed) |

The original machine's end G-code included `G0 X50 Y50 F9000` (**150 mm/s** parking). The conservative machine settings keep the manufacturer's Flashforge commands but reduce this to `F4800` (**80 mm/s**) and the end retraction from `F3600` (**60 mm/s**) to `F2400` (**40 mm/s**). Do not edit the machine's homing procedures without validation.

**Important:** A machine-limit value in a slicer is *not* necessarily a firmware-level hard stop. Process feedrates are written into generated G-code and the web engine writes acceleration commands for supported flavors, but a particular proprietary Adventurer 4 firmware may interpret those commands differently. Some machine ceilings are used by the print-time estimator. To check true behavior, export the G-code, inspect `F` values (mm/min) and motion commands (e.g. `M204`), then test physically at low risk. The safe profile does not install/downgrade firmware and cannot guarantee prevention of layer shifts.

The conservative speed values apply regardless of material. Material temperature, cooling, retraction and volumetric flow presets remain separately selectable. Use appropriately calibrated settings for PLA, PETG, ABS or other supported materials.

## How it works

- The app loads the standard AD4 0.4 mm machine profile from `three-slicer@0.4.0` and applies the conservative machine overlay in `src/ad4SafeProfile.js`.
- After the process and filament catalogs finish loading, it merges the conservative values into the original **0.20 mm Standard** process and sets a distinct conservative process name.
- Selecting any bundled AD4 process resets its process-specific keys, then overlays the **same conservative motion values**, while retaining profile-specific layer height, geometry and other non-motion settings.
- Selecting a custom saved process instead restores precisely the saved process-key snapshot, without forcibly replacing the user's chosen velocities.
- The app **selects `Artillery PLA Basic @Flashforge AD4` by default when the filament catalog loads**, instead of taking the first vendor-recommended material (which may have ABS-class temperatures). The profile is based on Generic PLA: 205°C nozzle (210°C initial layer), 55°C bed, 1.75 mm diameter, flow ratio 1.0, maximum volumetric speed 10 mm³/s, and pressure advance disabled until calibration. When this PLA is selected, generated G-code is checked for unexpected heater commands and recognized temperature metadata above 220°C nozzle or 65°C bed. This is not a firmware safeguard; supervise your printer. Artillery states a 190–220°C nozzle range; 55°C bed and 10 mm³/s are cautious setup choices, not a certified optimum.
- A user can select **Save current settings as new profile…** from Process or Material, name it, and save it in localStorage. Saved presets remain selectable across page reloads on the *same browser and same site origin*; they do not automatically synchronize between GitHub Pages and localhost. The UI also offers Update saved and Delete.
- Regression tests run with `node --test tests/*.test.mjs` before the GitHub Pages production build.

## Sources

1. [Flashforge Adventurer 4 official user manual — original 10–150 mm/s specification](https://en.fss.flashforge.com/10000/software/b2cce96c456223987cc1be7204e37939.pdf)
2. [Flashforge Japan — Adventurer 4 FAQ; no more than 60 mm/s for small prints](https://flashforge.jp/faq/adventurer4-only-print-filament-injection/)
3. [Flashforge high-speed upgrade guide — HS nozzle, firmware and profile](https://en.fss.flashforge.com/10000/software/a65fd6130674525105021124d3ed9430.pdf)
4. [Flashforge's high-speed upgrade demonstration — advertised 200 mm/s and 10,000 mm/s²](https://www.youtube.com/watch?v=YjvXrNKgJh8)
5. [Tom's Hardware — AD4 FlashPrint Standard at 60 mm/s](https://www.tomshardware.com/reviews/flashforge-adventurer-4-3d-printer-review)
6. [OrcaSlicer official 0.20 mm Standard AD4 0.4 nozzle process](https://github.com/OrcaSlicer/OrcaSlicer/blob/main/resources/profiles/Flashforge/process/0.20mm%20Standard%20%40Flashforge%20AD4%200.4%20Nozzle.json)
7. [Community report: firmware-update-related layer shifts (anecdotal)](https://www.reddit.com/r/FlashForge/comments/15v83ok/how_to_restore_your_adventurer_4_to_an_older/)

8. [Artillery official PLA Basic (190–220°C nozzle range)](https://es.store.artillery3d.com/products/pla-basic-1)
9. [Open Filament Database via SimplyPrint (Artillery Basic PLA bed range)](https://simplyprint.io/filaments/artillery/pla-basic)
