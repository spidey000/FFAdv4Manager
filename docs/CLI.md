# `ffadv4manager` CLI reference

`ffadv4manager` is the Linux/Python command-line client for FlashForge Adventurer
printers. For installation, create a virtual environment and install this
checkout with `python -m pip install -e .`; see the [README installation
steps](../README.md#linux-cli-installation-and-use). The installed command is
`ffadv4manager`; `ad4ctl` remains a compatibility alias to the same CLI. You can
also run it from a checkout with `python3 -m ffadv4manager.cli`.

For an evidence-qualified catalog of printer commands, G-code in the test files,
and the distinction between TCP command framing and UDP discovery, see the
[printer command catalog](PRINTER-COMMANDS.md). It is not an exhaustive command
reference.

Run `ffadv4manager help` for the built-in overview, `ffadv4manager help COMMAND` for a
command's concise help, or `ffadv4manager COMMAND --help` for argparse syntax. For
camera and config subcommands, the built-in topics include, for example,
`ffadv4manager help camera snapshot` and `ffadv4manager help config set`.

## Connection options and configuration

The general form is:

```text
ffadv4manager [--host HOST] [--port PORT] [--timeout SECONDS] COMMAND [ARGS]
```

For printer-command connection values, each option resolves independently in
this order: explicit command-line option, config file, built-in default.
`--host` is an IP address or hostname; it is required for printer commands and
has no built-in default. The printer TCP port defaults to `8899`, and the
connection timeout defaults to `8` seconds. Place global connection flags
before the command, for example `ffadv4manager --host 192.168.1.50 status`.

The INI config has a `[connection]` section and supports `host`, `port`,
`timeout`, `camera_port`, and `camera_path`. Its default location is
`~/.config/ffadv4manager/config.ini`. If `XDG_CONFIG_HOME` is set, the location is
`$XDG_CONFIG_HOME/ffadv4manager/config.ini`. `FFADV4MANAGER_CONFIG` overrides the
entire config file path and takes precedence over legacy `AD4CONNECT_CONFIG`, which
is used when the new variable is unset. If neither override is set and the new
default file does not exist, an existing
`~/.config/ad4connect/config.ini` (or `$XDG_CONFIG_HOME/ad4connect/config.ini`) is
read as a migration source. Writes use the new default path and leave the legacy
file untouched. These environment variables are read directly; `ffadv4manager`
does not load `.env` files. No credentials are stored or used.

Camera options also resolve from command-line camera options, config values,
then defaults: port `8080` and path `/?action=stream`. Camera commands use the
configured host or root `--host`, but do not open the printer-command TCP
connection. Discovery, config, and help likewise do not require a printer
host.

Set and inspect defaults locally:

```sh
ffadv4manager config set --host 192.168.1.50 --port 8899 --timeout 8
ffadv4manager config set --camera-port 8080 --camera-path '/?action=stream'
ffadv4manager config show
ffadv4manager config path
ffadv4manager config unset port camera_path
```

## Commands

Unless noted otherwise, printer commands require a reachable printer host,
provided with `--host` or stored in config. Examples below assume the host has
been configured; add `--host 192.168.1.50` before the command when needed.

### `status`

Read and print machine state, move mode, current file, temperatures, SD byte
progress/percentage, and layer information when reported. This is observational.

```sh
ffadv4manager status
```

### `watch`

Refresh the status display repeatedly. The default interval is 5 seconds;
`--interval SECONDS` changes it. Press Ctrl+C to stop.

```sh
ffadv4manager watch
ffadv4manager watch --interval 2
```

### `files` and `files-raw`

`files` parses the printer's file-list response and prints one filename per
line. `files-raw` prints the unparsed response, which can be useful when
diagnosing output the parser does not recognize.

```sh
ffadv4manager files
ffadv4manager files-raw
```

### `discover`

Send UDP multicast/broadcast discovery probes and listen for printers. This
does not need a configured host or open a printer command connection. The
default listen timeout is 3 seconds. Normal output is a name/IP/port table (or
a no-printers message); `--json` emits a JSON array, including `[]` when no
printers are found. On a TTY, plain human-readable discovery also offers to
store a printer host when exactly one result advertises command port `8899`; if
multiple results advertise it, select one first. The port is the value in the
UDP discovery response: no TCP port scan or subnet scan is performed. The host
is written through the local config store only after confirmation, preserving
other config values. No eligible result or a declined/cancelled prompt leaves
the config unchanged. `--json` and non-TTY use never prompt or write config.

```sh
ffadv4manager discover
ffadv4manager discover --timeout 5 --json
```

### `camera`

Camera actions use HTTP MJPEG, separate from the printer's command TCP
protocol. A host is needed to construct the URL, from config or root `--host`.
Each action accepts `--camera-port PORT` and `--camera-path PATH` to override
camera defaults. Paths are used literally, including query strings.

```sh
ffadv4manager camera url
ffadv4manager camera open
ffadv4manager camera snapshot /tmp/ad4-frame.jpg
ffadv4manager --host 192.168.1.60 camera url --camera-port 8081
```

- `camera url` prints only the URL and makes no network request.
- `camera open` asks Python's standard-library browser integration to open the
  URL. It depends on a usable desktop browser; headless systems may not open a
  browser, in which case the URL is printed with guidance.
- `camera snapshot OUTPUT` downloads and saves the first complete JPEG frame;
  the download is bounded, does not launch a browser, and prints only the saved
  path on success.

The default URL shape is `http://HOST:8080/?action=stream`. The endpoint has
no HTTP authentication or encryption; use it only on a trusted network.

### `upload`

Upload a local G-code/GX file to printer storage. By default, the remote name is
the local basename; `--remote-name NAME` selects another simple printer-side
filename. The upload protocol sends an acknowledged M601/M115/M650/M119
preamble on a separate connection, then sends the file size and
`0:/user/NAME` destination in M28. It requires standalone `ok` lines for each
preamble command, M28 readiness, and M29 completion before proceeding. It then
checks M661 for the uploaded basename, matching across `/data/` and `0:/user/`
namespaces. Missing names fail closed. Upload-only never sends M23 or M24.
M661 confirms only that the name is listed; it does not verify stored size or
content integrity. Without `--start`, upload stores the file and confirms its
listed presence and the client sends no M23/M24. This is a software-path
guarantee, not a proven physical no-start guarantee: on one tested Adventurer 4
running firmware `v2.2.4`, the user observed execution after an older
upload-verification path sent M23. The current M661-only path avoids that
selection, but M601 S1's firmware-side effect is not authoritatively documented;
supervise the printer until separately verified. The `print` command selects
and starts an uploaded file. Explicit `--start` opts into that print action after
M661 confirms the name is listed. The CLI checks
printer status before upload and refuses when status reports an active print,
unless `--force` is supplied. `--force` bypasses that busy-status check; it is
not a general safety guarantee. A local file must exist and must not be empty:
empty files are rejected locally before any upload connection/data transfer.

Supported G-code inputs (`.gcode`, `.gco`, `.g`) are automatically wrapped as GX
before upload; existing GX is detected by its `xgcode 1.0\n\0` magic, not its
extension, and is not converted again. The original G-code is preserved: bundled
converter code operates on a temporary copy, selecting the `adventurer4` profile.
Pillow is installed automatically as a project dependency; no standalone
converter installation is needed. Converted uploads use a `.gx` remote
extension; a requested remote basename is retained with that extension.
`--no-convert` uploads bytes unchanged. Unknown input types are rejected for
automatic conversion. Wrapping only adds the GX container and thumbnail; it does
not rewrite incompatible machine or toolpath commands. No actual-printer
acceptance of converted files has been validated.
The embedded G-code text follows the upstream encoder's Latin-1 conversion;
characters outside that encoding are replaced, though the original local file
is left untouched.

```sh
ffadv4manager upload ~/Downloads/model.gcode
ffadv4manager upload ~/Downloads/model.gcode --remote-name model.gcode
ffadv4manager upload ~/Downloads/model.gcode --start
ffadv4manager upload ~/Downloads/model.gcode --force
ffadv4manager upload ~/Downloads/model.gcode --log-file /tmp/ad4-printer.jsonl
ffadv4manager upload ~/Downloads/model.gcode --no-convert
ffadv4manager convert ~/Downloads/model.gcode --output /tmp/model.gx
```

`convert INPUT --output OUTPUT.gx` performs the same local-only conversion and
checks the expected GX header/BMP layout. Conversion only wraps the G-code and
adds a thumbnail; it does not rewrite incompatible machine or toolpath commands.

The command displays upload progress and then reports that the `0:/user/NAME`
file is listed. Preamble, M28, M29, and M661 replies are labeled on stderr;
M23/M24 replies occur only for explicit `--start` or the separate `print`
command. `--log-file PATH` additionally appends each response as a timestamped
JSON object per line; the log is not truncated. The
remote name must be a simple filename (optionally prefixed by `/data/` for
compatibility), not a nested path.

### `print`

Select and start a file that is already stored on the printer. Supply its
printer-side name, with or without the `/data/` prefix; the upload namespace
`0:/user/NAME` is also accepted. It checks status and
refuses when the printer reports printing unless `--force` is given.

```sh
ffadv4manager print model.gcode
ffadv4manager print /data/model.gcode --force
```

This starts a physical print; check the printer and file first. `--force`
bypasses the reported-printing check only.

### `pause`, `resume`, and `cancel`

These send the corresponding control action to the printer:

```sh
ffadv4manager pause
ffadv4manager resume
ffadv4manager cancel
```

Pause and resume affect the active print. `cancel` cancels/resets the current SD
print state and can discard the active job; use it deliberately.

### `config`

Configuration commands are local and do not contact a printer:

```sh
ffadv4manager config show
ffadv4manager config path
ffadv4manager config set --host 192.168.1.50
ffadv4manager config unset host camera_port
```

- `show` prints stored values or explains that no config is stored.
- `path` prints the active config path.
- `set` accepts one or more of `--host`, `--port`, `--timeout`,
  `--camera-port`, and `--camera-path`; at least one option is required.
- `unset` accepts one or more keys: `host`, `port`, `timeout`,
  `camera_port`, and `camera_path`.

### Structured output, identity, coordinates, and local inspection

`status --json` prints one JSON object with parsed values and `null` for
unavailable fields; the raw protocol transcript is intentionally omitted.
`files --json` prints a JSON array of remote paths. `watch --jsonl` prints one
status object per line and may be bounded with `--count`.

```sh
ffadv4manager status --json
ffadv4manager files --json
ffadv4manager watch --jsonl --interval 5 --count 12
ffadv4manager info --json
ffadv4manager position --json
ffadv4manager inspect ~/Downloads/model.gcode
```

`info` reads M115 fields (which vary by model); `position` reads M114 reported
coordinates and does not independently measure physical position. `inspect`
is local-only: it reports file size, SHA-256, and narrowly recognized G-code
comment metadata. GX files are treated as binary and currently report metadata
as unavailable.

`files preview REMOTE_NAME --output FILE.bmp` requests an M662 printer-side
thumbnail. The client requires a standalone ACK and a complete BMP before
writing it. This is not a live camera snapshot.

### Waiting, diagnostics, monitoring, and capture

```sh
ffadv4manager doctor
ffadv4manager wait --state READY --timeout 7200
ffadv4manager wait --bed-below 40 --interval 10 --timeout 3600
ffadv4manager camera timelapse ./captures --interval 10 --count 60
ffadv4manager monitor --output print.jsonl --interval 5 --count 100
ffadv4manager monitor --output print.jsonl --snapshots ./events
ffadv4manager notify --events paused,offline
```

`doctor` reports printer-status and camera HTTP checks. `wait` polls until one
reported state or bed-temperature condition matches; a timeout returns nonzero.
Timelapse captures interval-based JPEG stills plus a JSONL manifest. It does not
claim layer synchronization. `monitor` appends status samples and observed state
transitions to JSONL; when `--snapshots` is supplied, it captures a still on an
observed state change. `notify` requires Linux `notify-send`; supported events
are `paused`, `offline`, `printing`, and `ready`. These commands can be stopped
with Ctrl+C; monitoring/watching handles interruption with exit status 130.

### Named profiles and printer controls

```sh
ffadv4manager profiles add workshop --host 192.168.1.50 --port 8899
ffadv4manager profiles list
ffadv4manager profiles show workshop
ffadv4manager --profile workshop status
ffadv4manager profiles update workshop --camera-port 8081
ffadv4manager profiles delete workshop
ffadv4manager printer rename workshop-ad4
ffadv4manager fan on
ffadv4manager fan off
```

Profiles live separately in `profiles.json`; within each setting, explicit
connection flags override the selected profile, which overrides global config.
`printer rename` sends M610 and checks that M115 reports the requested name;
this verifies reported state, not persistence across reboot. `fan` controls the
layer/part-cooling fan only. It does not control the enclosure fan. Rename and
fan commands change printer state; acknowledgements are not proof of physical
effect.

## Exit behavior and safety

Successful commands return `0`. Runtime/configuration errors generally return
`1`; argparse usage errors and unknown built-in help topics return `2`. A
busy-printer refusal by `upload` or `print`, and `config set` with no options,
also return `2`. Ctrl+C during `watch` returns `130`. `camera open` returns `1`
if it cannot open a browser; camera/discovery errors (including a missing
camera host) return `1`.

`status`, `files`, `files-raw`, and `watch` are observational. Upload writes to
printer storage; `print`, `upload --start`, `pause`, `resume`, and `cancel`
affect a physical printer/job. The upload code path without `--start` sends no
M23/M24, but its physical no-start behavior is not guaranteed on undocumented
firmware; review the target and supervise it. The device used in the logged
upload investigation identified itself as Adventurer 4 firmware `v2.2.4`; older
project notes refer to a separate `v2.3.3-3.33` test. Printer commands use the
legacy FlashForge TCP protocol without encryption or authentication; other
models or firmware may behave differently.

## OrcaSlicer post-processing hook

For automatic upload from OrcaSlicer, see the [README's OrcaSlicer Linux
post-processing hook section](../README.md#orcaslicer-linux-post-processing-hook)
and `scripts/orca_ad4_upload.py`. In the documented Linux contract, Orca
appends the generated G-code path as a shell-quoted final argument; do not add a
filename placeholder. The hook shares `ffadv4manager` config and supports `--host`,
`--port`, `--timeout`, `--start`, `--force`, and `--no-convert`. It automatically
converts supported G-code using the shared converter helper; see upload above
for prerequisites and limitations. `--start` is opt-in; without
`--force`, the hook fails closed if status cannot be read/parsed or the printer
is not in a known idle `READY` state. The verified OrcaSlicer contract is
version/build-dependent; consult the README caveat before relying on export
failure behavior.
