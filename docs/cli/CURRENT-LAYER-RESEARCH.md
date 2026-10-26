# Adventurer 4 current-layer and timelapse research

Research note for the FlashForge Adventurer 4 tested in this project. It brings
together public GitHub material and direct observations from a supervised print.
The public repositories are community projects, not official FlashForge
specifications. This note does not authorize installing hacks, sending
undocumented G-code, or repeating a physical print.

## Executive result

- On the tested Adventurer 4, identified by the CLI as firmware `v2.2.4`, the
  reported M27 layer field was **not usable** during the supervised print: it
  remained `Layer: 0/0` while the user observed multiple physical layers and the
  progress field advanced from `0/100` to `100/100`.
- Repeated HTTP camera snapshots **did work during the active print**. This
  establishes availability of repeated still-image capture, not continuous
  video recording or exact synchronization with layer changes.
- No source reviewed establishes another current-layer interface for this
  Adventurer 4 firmware. In particular, the HTTP `printLayer` fields and
  `timeLapseVideo` option described for newer FlashForge models must not be
  assumed to exist on the Adventurer 4.
- The practical timelapse mode currently supported by evidence is interval
  capture over the camera HTTP stream. Per-layer triggering needs further
  firmware/FlashPrint analysis or a separately verified synchronization method.

## Direct hardware evidence

The user authorized a supervised print of an existing short bearing GX file and
confirmed the build plate was clear. The CLI identified the printer as an
Adventurer 4 running firmware `v2.2.4`. M23 selected the 547,871-byte file and
M24 was acknowledged. The user physically observed several layers.

During the job, status samples showed:

| Observation | Device status / physical observation |
|---|---|
| Beginning | `BUILDING_FROM_SD` / `MOVING`; progress `0/100`; `Layer: 0/0`. |
| During the print | Progress advanced through `6`, `13`, `23`, `33`, `43`, `52`, `61`, `71`, `79`, and `95` out of `100`; every sampled layer pair remained `0/0`. The user reported several layers visible in the physical print. |
| At the end of progress | Progress reached `100/100`, while status still reported `BUILDING_FROM_SD` / `MOVING` and `Layer: 0/0`. Subsequent samples, taken before the user asked to stop polling, showed heater targets at zero and temperatures cooling; no final transition to `READY` was established. No pause/cancel was sent. |

The current project obtains layer values from the `Layer: current/total` text in
M27 and parses them separately from the progress pair; see
[`core/parser.py`](../ffadv4manager/core/parser.py) and
[`core/client.py`](../ffadv4manager/core/client.py). This test indicates a
firmware/job telemetry limitation, not a parser failure for a valid nonzero
response. The synthetic parser test for `Layer: 2/4` establishes parsing only,
not that this firmware produces such a response.

### Camera during the print

The CLI repeatedly saved JPEGs from the printer's HTTP/MJPEG endpoint at spaced
intervals from job start through progress `100/100`. The sampled files were
`640×480`; comparing selected images showed pixel-content differences. This
confirms the endpoint can serve repeated snapshots while this printer reports
an active job. It does **not** prove continuous recording, 30 FPS capture,
unique frame timing, or per-layer synchronization. The camera endpoint is
separate from printer TCP/G-code and has no authentication; use it only on a
trusted network.

## Audit of the requested GitHub repositories

### [SumolX/FlashForge-Hacks](https://github.com/SumolX/FlashForge-Hacks)

Audited tree revision:
[`eee5e3277705fe9f54c2c61de3605cecb55dbdd8`](https://github.com/SumolX/FlashForge-Hacks/tree/eee5e3277705fe9f54c2c61de3605cecb55dbdd8).

- The README says it was tested against
  `Adventurer4-2.2.4-2.3-20230216`. Treat this as the project's compatibility
  claim, not proof that every package/build named `v2.2.4` is identical to the
  printer used here.
- [`Installer/www/cgi-bin/printer`](https://github.com/SumolX/FlashForge-Hacks/blob/eee5e3277705fe9f54c2c61de3605cecb55dbdd8/Installer/www/cgi-bin/printer)
  exposes a `?status` CGI that sends `~M27` to the local TCP service and relays
  the response. It does not parse or calculate a current layer.
- [`Installer/www/script/global.js`](https://github.com/SumolX/FlashForge-Hacks/blob/eee5e3277705fe9f54c2c61de3605cecb55dbdd8/Installer/www/script/global.js)
  handles dashboard actions and camera display; no layer-change hook or
  timelapse capture path was found in the reviewed dashboard code.
- The repository contains files under
  [`Firmware/Adventurer4-2.2.4-2.3-20230216/`](https://github.com/SumolX/FlashForge-Hacks/tree/eee5e3277705fe9f54c2c61de3605cecb55dbdd8/Firmware/Adventurer4-2.2.4-2.3-20230216),
  including an original `flashforge_init.sh`. These may help static analysis;
  the reviewed scripts do not explain how M27 generates `Layer`.
- The hack installs SSH/web services and modifies startup/root access. **Do not
  install it solely to investigate layers**; it changes the printer and may
  render it unusable.

### [SumolX/FlashForge](https://github.com/SumolX/FlashForge)

- The repository is mainly slicer profiles and conversion tools for GX files.
- [`OrcaSlicer/Scripts/FlashForgeAdapter.py`](https://github.com/SumolX/FlashForge/blob/main/OrcaSlicer/Scripts/FlashForgeAdapter.py)
  and [`gx.py`](https://github.com/SumolX/FlashForge/blob/main/OrcaSlicer/Scripts/gx.py)
  process static file metadata such as layer height/count. They do not query
  live printer state or expose a current layer during execution.
- It contains
  [`Firmware/FlashForge-Adventurer-4-Firmware-V2.2.4-2.3.zip`](https://github.com/SumolX/FlashForge/blob/main/Firmware/FlashForge-Adventurer-4-Firmware-V2.2.4-2.3.zip).
  This is a candidate for offline static inspection after verifying provenance
  and checksum. Its presence does not establish that it contains source code or
  that its internal format has been analyzed.
- The repository's G-code layer metadata and GX previews describe the file/job,
  not the device's currently executing layer.

### [Parallel-7/flashforge-api-docs](https://github.com/Parallel-7/flashforge-api-docs)

Audited repository revision:
[`f080a1110318a1818461800acb84d89049509761`](https://github.com/Parallel-7/flashforge-api-docs/commit/f080a1110318a1818461800acb84d89049509761).
The repository describes itself as unofficial.

- The [TCP M27 reference](https://github.com/Parallel-7/flashforge-api-docs/wiki/TCP-Protocol#m27---get-print-status)
  shows responses containing `Layer: current/total`, including `0/0` and
  `23/100`. The examples do not identify an Adventurer 4 v2.2.4 device or
  explain precisely whether `current` means the layer in progress or the last
  completed layer.
- The [Adventurer 4 Series page](https://github.com/Parallel-7/flashforge-api-docs/wiki/Adventurer-4-Series)
  describes A4 Pro/Lite as TCP-only and lists M27 as a status/progress command.
  It cites other firmware versions (A4 Pro `1.2.1`, A4 Lite `2.0.5`), not the
  regular A4 `v2.2.4` used in this test.
- The community YAML
  [`endpoints/networkserver_commands_adventurer4.yaml`](https://github.com/Parallel-7/flashforge-api-docs/blob/main/endpoints/networkserver_commands_adventurer4.yaml)
  also covers A4 Pro firmware `1.2.1-3.22`; it names M27 but does not define a
  layer response for v2.2.4.
- The HTTP [`/detail`](https://github.com/Parallel-7/flashforge-api-docs/wiki/HTTP-REST-API#detail---get-printer-details)
  fields `printLayer` and `targetPrintLayer` are documented for 5M/5M Pro/AD5X,
  and the capability matrix says this API is not available on A4.
- Snapshots documented for 5M Pro and the `timeLapseVideo` option documented
  for AD5X are model-specific; neither is evidence of an A4 timelapse API.
- A3 YAML explains `SD printing byte x/100` as percentage, while other legacy
  examples use a byte-sized denominator. Do not transfer that A3 interpretation
  to A4 v2.2.4 without evidence.

## Official information and FlashPrint

No official FlashForge manual, FlashPrint reference, or v2.2.4 release note was
found that explains M27's layer field or an alternative A4 current-layer API.
The [FlashForge Download Center](https://www.flashforge.com/pages/download-center)
was checked, but no relevant AD4 protocol specification was exposed there. This
is a limit of the sources found, not proof that no archived/regional vendor
document exists.

FlashPrint itself is proprietary; the public
[Flathub packaging repository](https://github.com/flathub/com.flashforge.FlashPrint)
points to a binary Debian package, not FlashPrint source. The package has not
been downloaded or statically analyzed as part of this research. Static
inspection could reveal whether FlashPrint parses M27 or derives layer progress
from a file, but would not by itself prove the firmware's behavior.

## Verified CLI commands

These command forms were run successfully against the tested printer; `<HOST>`
and output paths are placeholders. They are evidence for this device/session,
not a general guarantee for other models or firmware.

```sh
# Reads M119/M105/M27 and displays parsed state/progress.
PYTHONDONTWRITEBYTECODE=1 python3 -m ffadv4manager.cli --host <HOST> status

# Saves the first complete JPEG frame from the camera HTTP/MJPEG endpoint.
PYTHONDONTWRITEBYTECODE=1 python3 -m ffadv4manager.cli --host <HOST> camera snapshot /tmp/ad4-frame.jpg
```

`status` was polled during the supervised print and reported byte progress while
`Layer` stayed `0/0`. `camera snapshot` was run repeatedly during that same job
and saved JPEGs. The physical start command `print <REMOTE_NAME>` was also
hardware-tested with explicit authorization; do **not** use a print command as a
layer diagnostic or repeat it without inspecting the printer, file, and bed and
obtaining authorization. Exact commands and outcomes are in
[`TEST_LOG.md`](../TEST_LOG.md); M27/camera behavior is summarized in
[`PRINTER-COMMANDS.md`](PRINTER-COMMANDS.md).

## Safe next investigation

1. Download the SumolX firmware ZIP to an isolated analysis directory, record
   source URL, archive hash and extracted file hashes; identify its format and
   inspect it **offline and read-only**. Search scripts/binaries for `M27`,
   `Layer:`, `SD printing byte`, and the TCP response implementation. Do not
   install, flash, or execute printer firmware.
2. If needed, obtain the exact FlashPrint binary referenced by the Flathub
   manifest, verify its checksum, and statically inspect strings/call sites for
   M27 and layer tracking. Do not execute it against the printer as part of this
   static-analysis step.
3. Keep evidence separate by model and exact firmware build. In particular,
   do not reuse 5M/AD5X HTTP fields or timelapse options as an A4 feature.
4. Until another path is verified, use interval-based HTTP snapshots rather
   than claiming per-layer capture on this Adventurer 4.
