# FFADV4Manager

FFADV4Manager is an open-source Python command-line toolkit for controlling legacy FlashForge printers that are no longer well supported by current FlashForge desktop software. The `ffadv4manager` CLI is designed for Linux terminals and AI-agent workflows; `ad4ctl` remains as a compatibility alias.

The first target is the **FlashForge Adventurer 4** on TCP port `8899`. Earlier
project notes refer to a separate test on firmware `v2.3.3-3.33`; the printer
used in the 2026-10-18 upload investigation reported firmware `v2.2.4` via M115.

## Current status

Working today:

- Printer status
- Temperature readout
- Print progress readout
- Parsed and raw printer file listings (`files`, `files-raw`)
- Upload G-code/GX files
- Confirm uploaded filename appears in M661; this does not verify stored size/content
- Optional timestamped JSONL logs of printer upload/verification replies (`--log-file`)
- Start prints remotely
- Pause/resume/cancel commands
- Live `watch` mode
- UDP printer discovery, with optional JSON output
- Camera stream URL, browser launch, and bounded JPEG snapshot (`camera snapshot`)

See the [printer command and G-code evidence catalog](docs/PRINTER-COMMANDS.md)
for device responses, implemented commands, test-file contents, and explicit
uncertainty/safety notes. It is not an exhaustive Adventurer 4 command list.

Planned CLI and protocol improvements:

- Support for related FlashForge models

## Linux CLI installation and use

The Python CLI works from a terminal on Linux with Python 3.9 or newer. From a
checkout, install it in an isolated virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

Set a printer address, then run commands without repeating it:

```bash
ffadv4manager config set --host 192.168.1.50
ffadv4manager status
ffadv4manager files
ffadv4manager help                 # comprehensive guide; no printer connection
ffadv4manager help upload          # command-specific help; no printer connection
ffadv4manager discover --json      # find printers without a configured host
```

You can also pass a host directly, e.g. `ffadv4manager --host 192.168.1.50 status`.
See [Configuration](#configuration) and [Usage](#usage) for details.
For the full command reference, see [docs/CLI.md](docs/CLI.md).

## Configuration

Rather than passing `--host` on every command, store connection defaults once:

```bash
ffadv4manager config set --host 192.168.1.50
ffadv4manager config set --host 192.168.1.50 --port 8899 --timeout 8
ffadv4manager config set --camera-port 8080 --camera-path '/?action=stream'
```

Then commands can be run without flags:

```bash
ffadv4manager status
ffadv4manager files
```

A flag always overrides the stored value, so you can point at a different printer
temporarily:

```bash
ffadv4manager --host 192.168.1.60 status
```

Inspect or clear the stored config:

```bash
ffadv4manager config show
ffadv4manager config path
ffadv4manager config unset port camera_path
```

The config lives at `~/.config/ffadv4manager/config.ini` (respecting `XDG_CONFIG_HOME`).
Set `FFADV4MANAGER_CONFIG` to point at a different file. It takes precedence over
legacy `AD4CONNECT_CONFIG`, which is used when the new variable is unset. If no
override is set and the new default config is absent, the existing
`~/.config/ad4connect/config.ini` (or its `XDG_CONFIG_HOME` equivalent) is read.
Writes go to the new path and leave the legacy file untouched.
Camera defaults are `camera_port = 8080` and `camera_path = /?action=stream`;
camera command options override them. Camera paths are kept literally, including
query strings.

## Usage

```bash
ffadv4manager --host 192.168.1.50 status
ffadv4manager --host 192.168.1.50 files
ffadv4manager --host 192.168.1.50 files-raw
ffadv4manager --host 192.168.1.50 watch
ffadv4manager discover
ffadv4manager discover --json
```

Upload only:

```bash
ffadv4manager --host 192.168.1.50 upload ~/Downloads/model.gcode --remote-name model.gcode
```

The input must be an existing, non-empty G-code/GX file (typically exported by a
slicer); empty files are rejected before the upload starts. The upload command
does not generate or slice a model. Without `--start`, it only uploads and
checks that M661 lists the uploaded filename; it does not select or print the
file in the client command path. M661 confirms listed presence only, not stored
size or content integrity. On this printer, an older upload-only verification
path issued M23 and the user observed the file execute; the current path omits
M23/M24. M601 S1 is still part of the preamble and its firmware-side effect is
not authoritatively documented, so this is not a proven physical no-start
guarantee. Supervise the printer during uploads until verified on your firmware.
Use the separate `print` command to start an already-uploaded file, or pass
`--start` to explicitly opt into printing after M661 lists the filename.

Upload and start:

```bash
ffadv4manager --host 192.168.1.50 upload ~/Downloads/model.gcode --remote-name model.gcode --start --log-file upload.jsonl
```

With `--start`, the CLI starts the job only after the printer acknowledges upload
completion and M661 lists the uploaded filename. M661 confirms presence only;
this workflow does not verify stored size or content integrity before starting.
The JSONL log is appended and includes the printer's raw protocol replies.

Print an existing printer-side file:

```bash
ffadv4manager --host 192.168.1.50 print model.gcode
```

Pause/resume/cancel:

```bash
ffadv4manager --host 192.168.1.50 pause
ffadv4manager --host 192.168.1.50 resume
ffadv4manager --host 192.168.1.50 cancel
```

## Discovery and camera

Discovery sends UDP multicast/broadcast probes to the supported FlashForge
discovery targets and listens for up to three seconds by default. It needs no
stored host and does not open a printer command connection:

```bash
ffadv4manager discover
ffadv4manager discover --timeout 5 --json
```

On an interactive terminal, plain `discover` offers to save the discovered host
as the local default only when a printer advertises command port `8899`. If more
than one printer advertises that port, select one and confirm before saving. The
port is the value advertised in the UDP discovery response; the command does not
scan TCP ports or the subnet. `--json` and non-interactive runs never prompt or
write the config. If no eligible printer is found, the config is unchanged.

Camera commands use the configured printer host (or an explicit root `--host`)
and the camera's separate HTTP MJPEG endpoint. The defaults are port `8080` and
path `/?action=stream`:

```bash
ffadv4manager camera url                         # prints only the URL; useful for piping
ffadv4manager camera open                        # asks the system browser to open it
ffadv4manager camera snapshot /tmp/ad4-frame.jpg # saves first complete JPEG frame
ffadv4manager --host 192.168.1.60 camera url --camera-port 8081
```

`camera snapshot OUTPUT` saves the first complete JPEG frame to the given path;
for example, `/tmp/ad4-frame.jpg` above. `camera url` prints a URL without
connecting, while `camera open` requires a usable desktop browser.

`camera open` depends on `webbrowser` finding a usable desktop browser; in a
headless environment it reports that it could not open the browser and shows the
URL. Use `camera url` or `camera snapshot` in terminal-only/agent workflows.
Snapshot download is bounded and only writes a complete JPEG frame. The camera
HTTP stream has no authentication or encryption, so expose/use it only on a
trusted network. These camera operations use HTTP, not the printer-control TCP
protocol.

## Protocol notes

The Adventurer 4 exposes a legacy FlashForge TCP service on port `8899`. Commands are sent as:

```text
~M119\r\n
```

Protocol evidence is limited to one Adventurer 4 unit/firmware: replies and
reported state do not establish universal firmware behavior or physical effect.
Read-only queries (including status, M114/M115, M661 and M662) responded;
M662 returned a complete BMP. Supervised tests also observed M106/M107 fan
effects and transitions for M24/M25/M26, but the print-control test stayed at
`0/100`, and small movement probes were not visually resolved. M104 ACKs and
changing current-temperature telemetry did not confirm a nozzle setpoint. Upload
listing does not verify file contents, and an earlier upload path preceded
unexpected execution. See the [evidence catalog](docs/PRINTER-COMMANDS.md) for
the hardware-confirmed, partial, static-only, and do-not-probe classifications.

Commands present in the client/protocol:

| Command | Purpose |
| --- | --- |
| `M119` | Printer state / current file |
| `M105` | Temperature state |
| `M27` | Print progress |
| `M661` | File listing |
| `M601 S1`, `M115`, `M650`, `M119` | Acknowledged upload preamble (separate connection) |
| `M28 <size> 0:/user/file.gcode` | Begin file upload with declared byte size and destination |
| `M29` | Finish file upload |
| `M23 0:/user/file.gcode` | Select file (only for explicit print/start actions) |
| `M24` | Start/resume print |
| `M25` | Pause print |
| `M26` | Cancel/reset SD print state |

Uploads require a standalone `ok` response after every preamble command, M28
readiness, and M29 completion. Payload is sent as raw chunks followed by a 3-second
flush delay. Upload-only checks M661 for the basename in either `/data/` or
`0:/user/` and does not issue M23/M24. M661 confirms listed presence only, not
stored size or content integrity. M23/M24 are reserved for explicit print/start
actions. M115 from the investigated printer reported firmware `v2.2.4`; the
older `v2.3.3-3.33` note is from a separate project test.

## Safety

This is early alpha software. Watch the printer when starting prints remotely. Use at your own risk.

## OrcaSlicer Linux post-processing hook

The optional `scripts/orca_ad4_upload.py` hook accepts the generated G-code path
as a final positional argument. In the verified OrcaSlicer Linux post-processing
contract, Orca runs each configured command line through `$SHELL -c` and appends
the G-code path as one shell-quoted final argument. The tested contract is based
on OrcaSlicer source commit `1ee0b730a1e6484e55a631dd567b41c986fc1d6a`; downstream
builds or versions may differ.

Configure one command per line in OrcaSlicer, for example:

```sh
'/home/user/venv/bin/python' '/home/user/FFADV4Manager/scripts/orca_ad4_upload.py' --host 192.168.1.50 --start
```

Quote paths to the Python executable and script in the configured command, and
use shell quoting if either path contains spaces or quote characters. OrcaSlicer
appends the generated G-code filename automatically, quoting it as a single shell
word (including paths with spaces or single quotes). **Do not append a filename
placeholder** such as `$1` or `{file}`. The hook also accepts `--gcode PATH` for
manual invocation, or `--gcode` may be omitted in favor of the appended positional
path.

The hook uses `--host` when supplied; otherwise it reads the same stored config
as `ffadv4manager`. It also honors explicit `--port` / `--timeout` before the stored
values and built-in defaults. It checks printer status before uploading and,
with `--start`, checks again immediately before starting the print. An unavailable
or unparseable status and a busy printer fail closed by default. `--force`
explicitly bypasses these status gates; `--start` remains opt-in. Hook failures
return nonzero, which OrcaSlicer treats as export failure under the verified
contract. Usage/configuration errors return status 2; operational errors return
status 1.

## Local Three_Slicer Adventurer 4 UI

The optional local web UI embeds the published Three_Slicer viewer/slicer with
the bundled Adventurer 4 0.4 mm nozzle, process, and filament presets. It is a
separate browser UI, not a native printer feature in upstream Three_Slicer.
Configure the printer and build the web app once:

```sh
ffadv4manager config set --host 192.168.1.50
cd web
npm ci
npm run build
cd ..
ffadv4manager slicer
```

The manager serves it only on `127.0.0.1:8765`. After slicing, choose **UPLOAD
FILE** to upload only, or **UPLOAD + START** and confirm to request a print start.
The local bridge invokes the existing CLI, which converts G-code to GX as needed.
An accepted upload/start command is not proof that the printer stored the exact
file or physically began printing; supervise first use. Requests are limited to
64 MiB. The `three-slicer` npm package is AGPL-3.0-or-later; review its license
obligations before redistributing a built application.

## GX converter attribution and license

FFADV4Manager is distributed under the GNU General Public License v3.0 or later
(GPL-3.0-or-later); see [LICENSE](LICENSE). It includes an adapted, in-process
GX conversion implementation based on [HellEvro/FF_Gcode_to_GX](https://github.com/HellEvro/FF_Gcode_to_GX)
version 1.1.0, upstream commit `b44b5760671594e4c0a0234131adc7f398338349`,
copyright © 2026 Gcode_to_Gx contributors and licensed under GPL-3.0-or-later.
The adapted GX writer, metadata parser, thumbnail encoder, and Adventurer printer
profile implementation are located in `ffadv4manager/core/gx_converter/`.
The upstream project notes that its design is based in part on
[urself25/Orca_Gcode_to_Gx](https://github.com/urself25/Orca_Gcode_to_Gx),
also licensed under GPLv3.
