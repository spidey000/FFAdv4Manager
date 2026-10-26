# Printer command and G-code evidence catalog

This is a catalog of commands found in this project, the captured Adventurer 4
responses, and the local test G-code files. It is **not an exhaustive list of
commands that work**: no official complete command reference for regular
Adventurer 4 firmware `v2.2.4` is available in this project. Firmware, model,
and command context can change behavior. An acknowledgement proves that a
command was accepted or answered, not that its physical effect is safe.

Evidence was cross-checked against the active Python client/CLI and printer
responses collected during a local test session on 2026-10-18. The raw protocol
transcript, test G-code, inert probe, and local test log are not distributed in
this catalog. No undocumented command is presented as confirmed merely because
it appears in test code or a G-code file.

## Evidence classes

The classes below separate a response/ACK, telemetry, and an independently
observed physical effect. All live evidence is from one Adventurer 4 reporting
firmware `v2.2.4`; it is not a compatibility guarantee for other units or
firmware. A protocol ACK alone is never proof of the described effect.

### Hardware-confirmed responses/effects

Includes read-only responses and supervised physical effects explicitly
observed by the user. For movement and print controls, distinguish device
reported state from independently observed physical behavior.

### Partial or telemetry-only

The device replied or its state/telemetry changed, but the intended setting,
stored data, or physical effect is not fully established. This includes ACK-only
and status-only evidence.

### Static-only/unverified

Supported only by client/FlashPrint signatures, firmware strings, or offline
analysis; no AD4 acceptance/effect was established on hardware.

### Not tested / do not probe

No live test was made and exploratory probing is not recommended because the
command may move, heat, interrupt, alter configuration, release control, or
affect firmware/boot state. Resolve via offline analysis or an isolated bench.

## Evidence labels (details)

- **Device response (`v2.2.4`)** — a response is present in the October 18
  device log, whose `M115` reply identifies an Adventurer 4 running firmware
  `v2.2.4`. This does not necessarily establish all command semantics.
- **Hardware-confirmed control (`v2.2.4`)** — the user confirms print start,
  pause, resume, and cancel worked on the Adventurer 4. CLI replies and status
  transitions were recorded for the short bearing model. In the complete
  sequence, the printer ran for 30 seconds after resume before cancellation;
  progress remained `0/100`, so no extrusion or completed object is claimed.
  (An earlier aborted attempt paused and canceled immediately.)
- **Implemented; not directly hardware-verified** — present in the current
  client, but no direct device evidence for its behavior is recorded in this
  session.
- **Executed-file evidence; not individually observed** — included in the local
  `test.gcode` uploaded as `test2.gcode`, which the user confirmed physically
  executed. There is no per-line device trace, so this does not prove that each
  line ran or establish its exact effect.
- **Probe-file evidence; not executed** — present in the separate M117-only
  probe file and listed on the printer; the user reported that the probe did
  not execute.
- **Semantics uncertain / potentially risky** — acceptance or presence is not a
  guarantee of harmless behavior. Treat commands with physical-motion,
  heating, selection, cancellation, or undocumented firmware effects with
  care.

## FlashForge TCP command protocol

For ordinary printer commands, the client opens TCP port `8899` and frames a
command as `~<G-code>\r\n` (for example, `~M119\r\n`). This framing is specific
to the printer command connection. During an upload, the client sends framed
M28, waits for readiness, transmits the file payload as raw bytes/chunks
without adding a guessed G-code wrapper, waits the existing 3-second flush
interval, then sends framed M29. The payload is file content, not an additional
printer command.

The UDP multicast/broadcast requests used by `ffadv4manager discover` are a
separate discovery protocol, not G-code and not commands on the TCP connection.

## Printer commands

The table is grouped by the strongest justified evidence class. A command can
have a confirmed response while its intended effect remains partial.

### Hardware-confirmed responses/effects

| Command | Meaning in this project / response evidence | Evidence and confidence |
|---|---|---|
| `M119`, `M105`, `M27` / `status` | Status, temperature, and progress queries. | **Repeated hardware responses (`v2.2.4`)**: a recent read-only batch queried status (M119/M105/M27) and the raw commands. Replies are device telemetry, not physical measurement; M27 layer remained `0/0` in observed cases. |
| `M114` | Read-only position query. | **Hardware response (`v2.2.4`)** including reported `X0 Y0 Z0`; does not independently verify physical position. |
| `M115` | Firmware/device information query. | **Hardware response (`v2.2.4`)**. SN/MAC are redacted. M610 testing separately confirmed a temporarily changed Machine Name in M115 and restoration to `adv.gg0099`; no reboot persistence or panel check. |
| `M610 <name>` | Sets the printer-reported machine name. | **Reversibly hardware-verified (`v2.2.4`)**: M610 changed the reported name to `REA-TEST-20261019`, then restored `adv.gg0099`; M115 confirmed both. No panel check or reboot-persistence test. |
| `M661` | File-listing query. | **Hardware response (`v2.2.4`)**; latest batch counted 74 entries. Presence does not establish file size/content. |
| `M662 <file_path>` | Reads a printer-side file preview/thumbnail, not the live camera. | **Directly observed**: existing `.gx` path returned a complete BMP (14,486 bytes), not PNG. |
| Webcam HTTP snapshot | Separate HTTP/MJPEG camera endpoint, not G-code. | **Repeated hardware captures in idle**: complete JPEGs at 640×480 were captured repeatedly. This confirms response/capture, not continuous video or any control effect. |
| `M106` / `M107` | Firmware fan controls. | **Supervised physical effect observed**: M106 activated the layer/part-cooling fan; M107 stopped it. The enclosure fan continued. No command to turn off the enclosure fan is identified. |
| `M24` / `M25` / `M26` | Start/resume, pause, cancel/reset SD print state in this client path. | **Hardware-confirmed reported transitions**: M24 start/resume and M25 pause/M26 cancel were ACKed; status reported BUILDING/MOVING, PAUSED, then READY. Progress remained `0/100`; do not claim completed extrusion/object. M23 preceded a historical unexpected execution and is treated separately as potentially print-starting. |

### Partial or telemetry-only

| Command | Meaning in this project / response evidence | Evidence and confidence |
|---|---|---|
| `G1 X/Y/Z`, `G90`, `G91` | Small coordinate/motion probes. | **ACK and coordinate telemetry only**: reported X0→X1→X2, Z0→2, Y0→1; G90 and G1 X0/Y0/Z0 restored reported coordinates. Webcam did not resolve these small displacements; do not claim independently observed physical movement. No extrusion or feed-rate change. |
| `G28` | Homes specified axes; without arguments may home all axes. | **ACK/state only** after user confirmed travel path clear. M114 was X0/Y0/Z0 before and after, M119 Z-min:1 before and after; webcam did not resolve movement. Not evidence of homing from off-home. |
| `M140 S<°C>` | Requests bed target. | M140 S30 ACK; status reported 27/30 after 5 s. First S0 ACK was followed by 29/30; repeated S0 and later reads reported target 0 and cooling. Cause of delayed first target is unresolved; no independent thermometer. |
| `M104 S<°C>` / `M104 S<°C> T0` | Requests nozzle target; FlashPrint has T0/T1 literal forms, firmware grammar unresolved. | M104 S40/S100 and S100 T0 ACKed; current M105/status rose to about 99–100 then cooled after S0. Panel showed **no target value**, M105 target remained `/0`; setpoint is not confirmed. Do not test T1 or further heating pending offline analysis. |
| `M28`, raw upload payload, `M29` | File transfer framing/payload/finalization. | **Partial**: upload replies and file-list presence were observed, but M661 presence proves neither size nor contents. A prior upload preceded unexpected execution. Do not recommend another exploratory upload. |
| `M23 <path>` | Select/open file in print flow. | Response observed, but potentially print-starting on this unit: `test2.gcode` execution followed a historical M23-containing flow without M24. M23 is not a query; do not probe. |
| `M601 S1`, `M650` | Upload preamble commands. | Replies observed (`Control Success V2.1.`, and `X: 1.0 Y: 0.5`); firmware-side meanings/effects remain uncertain. Do not infer harmlessness from ACK. |

### Static-only/unverified

| Command | Meaning in this project / response evidence | Evidence and confidence |
|---|---|---|
| `M611`, `M612`, `M653`, `M654` | REA/network handler candidates. | Not dispatched by the TCP handler; no hardware acceptance established. Static evidence only. |
| `G9`, `M118`, `M904`, `M905` | Client/FlashPrint signatures or conventional interpretations. | Client signatures only; no confirmed AD4 acceptance. |
| IAP / STM32 update | Firmware update/bootloader paths from static reports. | No physical IAP test; do not infer hardware operation from static analysis. |

### Not tested / do not probe

| Command | Risk / known evidence limit | Guidance |
|---|---|---|
| `M17` / `M18` | Motor enable/disable implications unverified. | Do not live-probe; may change motor state. |
| `M108` | Handler/effect unverified. | Do not live-probe; may interrupt/alter an active operation. |
| `M112` | Emergency-stop semantics and recovery unverified. | Do not probe as a query or test. |
| `M602` | Control-release effect unverified. | Do not live-probe; may change control ownership/state. |
| `M144` / `M145` / `M146` | Downstream STM32 meaning unknown; M146 may toggle/configure LED. M119 reported `LED:1`, camera cannot decide LED state with certainty. | Not sent. Do not use as exploratory LED/fan toggles. |
| `M651` / `M652` | Downstream STM32 effects unknown; enclosure-fan control not identified. | Do not live-probe. No command identified to stop enclosure fan. |
| `M663 S<pct>` | Firmware routes it to a print-speed setter; community semantics are for newer 5M-series models. | Not sent to AD4; no AD4 behavior or safe range established. Setter, not a read query. |

### Latest compatible read-only batch

While idle/`READY`, a sequential read-only sweep queried `status` (M119/M105/M27),
then raw M119/M105/M27/M114/M115, M661, and a camera snapshot. All returned
responses; M661 parsed 74 entries. M115 serial number and MAC were redacted from
the recorded output. These calls are compatible because they are queries; they
were sent sequentially, not pipelined. No setters, motion, file writes, print
control, M146, or unknown MCU-forwarded codes were included. M662's BMP preview
was verified separately earlier.

### Enclosure/case fan: control not identified

The supplied REA firmware analysis only establishes that M106 forwards the
fixed text `M106 S255` to the STM32 and M107 forwards `M107`; it does not include
the STM32 application logic that maps those codes to outputs. In the supervised
hardware test on this AD4, M106/M107 switched the layer/part-cooling fan while
the already-running enclosure fan remained running. **No command to turn off the
enclosure fan has been identified.** Do not probe with M144/M145/M146 or
M651–M654: their STM32-side effects are unresolved. Identification requires the
matching STM32 firmware or an isolated, instrumented bench—not trial-and-error
on the operating printer.

### Layer reporting and heating sequence (observed AD4 v2.2.4)

For the full GitHub repository audit, verified command forms, and offline
firmware-analysis plan, see [Current-layer and timelapse research](CURRENT-LAYER-RESEARCH.md).

In a supervised print of the existing ~12-minute bearing file, M27 byte progress
advanced from `0/100` through `100/100`, while the response stayed at
`Layer: 0/0`. The user confirmed that multiple layers were physically visible.
Treat the layer pair as unavailable for this device/job and do not use it as a
timelapse trigger. The byte progress is usable to track overall job progress,
but it is not a substitute for per-layer events.

No official FlashForge Adventurer 4 manual, FlashPrint reference, or firmware
note was found that defines M27's layer fields or their update behavior. The
[official FlashForge Download Center](https://www.flashforge.com/pages/download-center)
did not expose such documentation in this review. The
[community TCP protocol reference for M27](https://github.com/Parallel-7/flashforge-api-docs/wiki/TCP-Protocol#m27---get-print-status)
documents the response shape but is not an official specification and does not
establish field accuracy during an active AD4 print. This remains a firmware
telemetry limitation, not a parser fix established by current evidence.

The same print demonstrated the printer's preheat order: the bed first approaches
its target; the nozzle then heats to its target. Early status samples showed the
bed warming while the nozzle remained near ambient, followed by nozzle heating
after the bed was near `60 °C`. The user confirmed this is expected behavior on
this printer. Allow for that wait when interpreting status; do not treat it as a
failed nozzle heater based only on an early sample.

## What information the CLI returns

This separates parsed model fields from raw protocol text and the user-facing
CLI output. `PrinterStatus.raw` retains the non-empty M119/M105/M27 responses
joined with newlines, but `status` and `watch` print only the human summary; they
do not print that raw string or expose M119's endstop/flag/LED details.

| CLI command | Information returned to the user | Limits and evidence |
|---|---|---|
| `discover` | Returns discovered printer name, IP/host, and UDP-advertised command port; `--json` returns an array of objects with `name`, `ip`, and `port`. | Uses UDP multicast/broadcast discovery, not a TCP query or scan. It reports what the device advertises, not proof that the command port is reachable. An interactive run may offer to save the host when exactly one eligible printer is found. |
| `status`, `watch` | Both use M119, M105, and M27. The CLI summary prints machine status, move mode, current file; nozzle and bed current/target temperatures when present; current/total SD bytes plus a computed percentage when present; and current/total layer when present. `watch` repeats this summary at its interval. | M119 parser fields are only `MachineStatus`, `MoveMode`, `CurrentFile`; generic M119 endstop values, status flags, and LED details remain only in `raw` and are omitted from the CLI summary. Missing parser matches are `None` and displayed as `-` for the three always-printed state/file fields or omitted for optional temperature/progress/layer rows. Hardware status examples include READY, PAUSED, and BUILDING_FROM_SD/MOVING; a short control test stayed at `0/100`. |
| `files` | Prints one unique `/data/...` path per line. | The parser extracts `/data/` names up to colon/NUL/line delimiters, trims whitespace, and removes duplicates. M661 listing presence does not establish file size or contents. |
| `files-raw` | Prints the decoded M661 response as received by the client, including its command reply and binary-ish separators. | It does not parse, normalize, or verify file sizes/content. Collection ends on idle/timeout or the response byte limit. |
| `upload` | Displays local send progress (`sent` bytes relative to the local file's initial size) and on success prints `Uploaded and listed: 0:/user/<name>`. It collects upload-preamble/M28/M29 replies on stderr or in optional JSONL logs, then checks that M661 lists the requested basename under `/data/` or `0:/user/`. With `--start`, after this check it also prints the raw M23 and M24 replies described for `print`. | Progress measures bytes sent by the client, not confirmed printer bytes. The observed M601/M115/M650/M119 preamble replies were respectively `Control Success V2.1.` + `ok`; the M115 fields listed above; `X: 1.0 Y: 0.5` + `ok`; and M119 status. M28/M29 require standalone `ok`; M28 reported writing under `/data/` although the current sender uses `0:/user/`. Upload-only confirms listing presence only—no remote-size or content verification. |
| `print` | Prints the raw text returned by M23 and then M24. In observed selection output, M23 reported `File opened: <filename> Size: <bytes>`, `File selected`, and `ok`; M24 returned `ok`. | For the short bearing model, M23 reported 547,871 bytes; M24 acknowledgment and following `BUILDING_FROM_SD` / `MOVING` status were hardware-observed. The current CLI does not parse these replies into a structured result. |
| `pause`, `resume`, `cancel` | Each prints the raw reply text from M25, M24, or M26 respectively; observed replies included `ok`. | No structured result is parsed. Hardware-confirmed status transitions in the short control test were `PAUSED` after M25, `BUILDING_FROM_SD` / `MOVING` 5 and 30 seconds after resume M24, then `READY` after M26. Progress remained `0/100`; this is not evidence of extrusion or a completed object. |
| `camera snapshot OUTPUT` | Fetches a bounded HTTP/MJPEG response, saves the first complete JPEG frame to `OUTPUT`, and on success prints the saved path only. | **Repeated captures hardware-verified during an active print** on AD4 firmware `v2.2.4`: spaced HTTP snapshots succeeded from print start through byte progress `100/100`. Sampled JPEGs were `640×480` and differed substantially in pixel content as the bed/head moved. This proves repeated still capture during an active print, not continuous video recording, exact per-layer timing, or a G-code trigger. Camera HTTP is separate from printer TCP/G-code/M662 and has no authentication. |
| `camera url`, `camera open` | `url` prints the constructed stream URL without making a network request. `open` asks the system browser to open that URL and prints either a success message or a manual-open URL/error. | Neither command obtains printer telemetry; `open` behavior depends on a usable browser. The default endpoint is unauthenticated HTTP/MJPEG. |
| `config show`, `config path` | `show` prints locally stored host, command port, timeout, camera port/path, or explains that no configuration is stored. `path` prints the active local config-file path. | Local configuration only; neither command contacts the printer. `config set`/`unset` change local config and do not return printer information. |

Direct information queries outside the CLI status summary return raw response
text through the client's `command()` method. In addition to M115/M114/M662
above, these recorded responses should be interpreted only at the evidence
level stated; command acceptance alone does not establish undocumented effects.

`M663 S<pct>` is **not** a read query: the community reference describes it as a
print-speed setter for newer 5M-series models. It was not sent to this AD4, so
there is no observed AD4 reply or confirmed AD4 behavior for it.

## G-code found in test files

The local `test.gcode` used during testing was a short motion/heat test. It was
uploaded under the name `test2.gcode`; the user confirmed that file physically
executed. The
commands below are therefore **executed-file evidence, not individually
observed**: no command-by-command trace confirms which lines ran or their
individual effects. Descriptions are conventional G-code interpretations, not
a guarantee of this firmware's exact implementation.

| G-code in file | Conventional meaning / parameters | Evidence and caution |
|---|---|---|
| `G21` | Use millimeter units. | **Executed-file evidence; not individually observed**. Standard interpretation; exact firmware handling not separately checked. |
| `G90` | Use absolute positioning. Appears before homing and again after relative movement. | **Executed-file evidence; not individually observed**. Mode affects subsequent movement. |
| `G28` | Home axes (no axis selector is supplied in the test file). | **Executed-file evidence; not individually observed**; **potentially risky** because homing moves the machine. |
| `G91` | Use relative positioning. | **Executed-file evidence; not individually observed**. |
| `G1 Y10 F300` | Linear move to Y +10 mm in relative mode at feedrate 300 mm/min (5 mm/s). | **Executed-file evidence; not individually observed**; **potentially risky** because it commands physical motion. |
| `M104 S80` | Set the nozzle temperature target to 80 °C without a wait in conventional usage. | **Executed-file evidence; not individually observed**; **potentially risky** because it requests heating. |
| `G4 S180` | Dwell for 180 seconds in conventional usage. | **Executed-file evidence; not individually observed**. The file comment describes this as a maximum three-minute heating interval; no per-line execution trace exists. |
| `M104 S0` | Set the nozzle target to 0 °C in conventional usage. | **Executed-file evidence; not individually observed**. |
| `M117 UPLOAD_PROBE_ONLY` | Conventional LCD/status-display message command. | **Probe-file evidence; not executed**. The M117-only probe was listed on the printer, and the user reported no execution. This is not evidence that M117 itself was executed or that the device displays the message as expected. |

The test-file comments are not printer commands. Presence in a file, an upload
acknowledgement, or an M661 listing alone should not be treated as proof that a
command executed or that its effects are safe.

## Upload-only safety boundary

Current CLI and Orca upload-only paths stop after M29 and an M661 basename
presence check. They do not issue M23 or M24 and do not claim exact remote size
or content verification. The prior M23-containing upload path was followed by
the user's report that `test2.gcode` executed without M24; consequently M23 is
treated as potentially print-starting on this printer. `--start`, `print`, and
`resume` are explicit execution controls, but undocumented firmware behavior
(including the uncertain M601 S1 preamble effect) means software command
separation is not a physical no-start guarantee. Supervise the device and do
not use test G-code without reviewing motion and heating effects.

## Camera, filament sensor, and buzzer notes

### Webcam: HTTP/MJPEG, not G-code

The project uses the camera's HTTP MJPEG stream at port `8080`, default path
`/?action=stream`. `ffadv4manager camera snapshot OUTPUT` reads a bounded stream
and saves its first complete JPEG frame; `camera url` only constructs the URL.
This is separate from TCP port `8899` and sends no G-code. Physical first-frame
snapshots were captured during printer preflight/start/pause, including
`/tmp/opencode/ad4-full-control-preflight-20261018.jpg`,
`/tmp/opencode/ad4-full-control-started-20261018.jpg`, and
`/tmp/opencode/ad4-full-control-paused-20261018.jpg` (recorded in `TEST_LOG.md`).
These are still images from the first complete JPEG frame only; they do not
establish camera motion, continuous streaming/video, or a time-lapse.

Evidence is **community/implementation-level**, not an official AD4 API spec:
[OrcaSlicer issue #6106](https://github.com/OrcaSlicer/OrcaSlicer/issues/6106)
mentions `http://PRINTER_IP:8080/?action=stream` for several FlashForge models
including Adventurer 4, and an [unofficial AD4-series page](https://github.com/Parallel-7/flashforge-api-docs/wiki/Adventurer-4-Series#camera)
describes HTTP/MJPEG. Flashforge's [official camera-install article](https://wiki.flashforge.com/en/adventurer-series/maintenance/install-the-camera)
is for Adventurer 5M, not the AD4 network endpoint. The stream is unauthenticated
plain HTTP; keep it on a trusted LAN. No verified G-code command for a webcam
snapshot was found. M662 is a printer-file preview/thumbnail query, not the live
camera. It returns binary file-preview data (the observed preview was a 14,486-byte
BMP), whereas `camera snapshot` writes a JPEG from the separate HTTP stream.

### Filament/runout sensor

No filament-sensor API or sensor-specific command is implemented in this
project. The observed M119 status reply has generic flags (`S:1 L:0 J:0 F:0`)
but does not label a runout sensor, so this log cannot identify its state.
Generic Marlin [M412](https://marlinfw.org/docs/gcode/M412.html) reports or
configures filament runout handling, but support on this regular AD4/v2.2.4 is
**unverified**. Bare M412 is a generic query; M412 S1/S0 changes configuration
and must not be treated as a read-only probe. No M412 command was sent.

Generic [M600](https://marlinfw.org/docs/gcode/M600.html) filament-change and
[M701/M702](https://marlinfw.org/docs/gcode/M701.html) load/unload operations
can pause a job, move the head, or extrude/retract filament. AD4/v2.2.4 support
was not established; do not test them without a dedicated, explicitly approved
physical plan.

### Buzzer/beeper

Generic Marlin [M300](https://marlinfw.org/docs/gcode/M300.html) requests a
beep/tone, but no AD4/v2.2.4 implementation evidence was found in the project,
retained device replies, or the sources reviewed. M300 is an audible action, not
a read-only command, and was not sent. Do not assume that generic Marlin codes
are accepted by Flashforge's proprietary firmware.
