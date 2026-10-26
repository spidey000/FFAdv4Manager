# Adventurer 4 GX thumbnail and print metadata

The AD4 CLI accepts plain `.gcode` (`.g`/`.gco`) and transparently converts
it into a FlashForge xgcode 1.0 `.gx` file at upload time. Already-converted GX
files pass through without double-wrapping.

## Format

The legacy GX container is a 58-byte header followed by an 80×60 24-bit BMP
(14,454 bytes), then the unchanged machine G-code from byte offset 14,512.

Header metadata: estimated print time (seconds), right/left filament lengths
(mm), single/dual-extruder type, layer height (micrometres), perimeter count,
print speed (mm/s), platform/nozzle temperatures (°C). The legacy touch screen
is chiefly known to use the **thumbnail and time estimate**. Other fields
inform metadata viewers; heater commands still come from executable G-code.

`ffadv4manager convert part.gcode --output part.gx` converts locally.
`ffadv4manager upload part.gcode` also converts before uploading.

## G-code annotations

Put optional slicer-produced comments at the beginning of G-code:

```gcode
; estimated printing time (normal mode) = 1h 2m 3s
; filament used [mm] = 1234.50
; layer_height = 0.20
; wall_loops = 3
; print_speed = 45
; bed_temperature = 60
; nozzle_temperature = 205
; thumbnail begin 80x60 1234
; <base64-encoded PNG image, wrapped to multiple commented lines>
; thumbnail end
```

The numeric value following `thumbnail begin` must equal the actual Base64
payload length (1234 above is illustrative). Supported time formats include
`1h 2m 3s`, `HH:MM:SS`, numeric seconds and Cura-style `;TIME:<seconds>`.
Material usage is measured in millimetres; the optional `; filament used [m]`
form is also recognized. The converter composites transparent thumbnail pixels
onto black, rescales to 80×60 and emits a grayscale BMP as widely documented
for legacy FlashForge touchscreen firmware.

When no valid estimate is provided, the GX header holds **zero** to indicate
unknown rather than claiming a one-second print. The CLI does not try to
recalculate the entire print from raw G-code moves. ThreeSlicer supplies the
kernel's actual estimated time whenever available.

## Limitations and testing

Compatibility is based on community reverse engineering of xgcode 1.0 and
requires confirmation against a FlashPrint-generated Adventurer 4 GX and
your own printer firmware. A syntactically valid GX does not prove the
touchscreen displays it. Check thumbnails, estimated durations, and filament
usage on the printer **before** relying on those values. Never change nozzle
or bed heater commands just to match metadata comments.

Sources:
- https://github.com/slic3r/Slic3r/issues/4869
- https://github.com/HellEvro/FF_Gcode_to_GX
