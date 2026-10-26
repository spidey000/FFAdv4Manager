# Local Adventurer 4 setup (development only)

This guide covers **loopback-only development and troubleshooting**. For the recommended **secure worldwide deployment using Cloudflare Tunnel + Access**, follow [REMOTE_ACCESS.md](REMOTE_ACCESS.md) instead. ThreeSlicer Responsive is a browser slicer with a local bridge to the **FlashForge Adventurer 4**. The printer profile is fixed to the bundled **Flashforge Adventurer 4 Series 0.4 Nozzle** preset. Process and filament parameters remain editable. Confirm that your physical nozzle, bed, filament and printer match the selected settings.

## Requirements

- Linux computer with Node.js 20+, npm, Python 3.9+, Python venv and pip.
- Browser with WebGL support.
- A printer on the same trusted network for printer features. Slicing alone works without the printer.
- An explicit printer host/IP; the CLI can discover printers without changing settings: `ffadv4manager discover --json`.

## Install and start

Run from the same parent directory, substituting your printer's **actual** LAN IP:

```bash
git clone https://github.com/spidey000/FFAD4Manager.git
git clone https://github.com/spidey000/Three_slicer_responsive.git
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ./FFAD4Manager
ffadv4manager config set --host 192.168.1.50
ffadv4manager status --json
cd Three_slicer_responsive
npm ci
npm run build
npm run local
```

Open **http://127.0.0.1:8765/Three_slicer_responsive/** in a browser **on the computer running the bridge**. Stop the bridge with Ctrl+C. A mobile device cannot use another computer's loopback address; the supported remote setup is described in [REMOTE_ACCESS.md](REMOTE_ACCESS.md).

`npm run dev` starts a Vite development frontend, which proxies `/api` to `http://127.0.0.1:8765`; run the local bridge alongside it for printer features. The server accepts `AD4_HOST` (overrides CLI-configured printer host), `AD4_CLI` (CLI command path) and `AD4_WEB_PORT` (local HTTP port, default 8765). When changing the port, update the Vite proxy if necessary.

The bridge always listens on **127.0.0.1**. With no `CF_ACCESS_*` configuration, it provides **local-only unauthenticated mode**, which must **not** be published via a Tunnel. With the four complete Cloudflare Access settings, it enables signed JWT validation and strict public Host/Origin checks; see [REMOTE_ACCESS.md](REMOTE_ACCESS.md). Never expose the legacy printer TCP port or MJPEG camera stream directly.

## What the local bridge actually implements

| HTTP endpoint | FFAD4Manager action | Behavior |
| --- | --- | --- |
| `GET /api/printer/status` | `status --json` | Observed printer state, shown as a compact status label in the UI. |
| `GET /api/printer/camera` | `camera snapshot TEMP.jpg` | Returns a single JPEG. If it fails, the browser shows a labeled placeholder. |
| `POST /api/printer/jobs?start=false` | `upload TEMP.gcode` | Upload only: no explicit M23/M24 selection or start in this CLI path. |
| `POST /api/printer/jobs?start=true` | `upload TEMP.gcode --start` | Upload and explicitly request selection/start after upload confirmation. |

The job body is plain-text G-code, up to 100 MiB. The bridge invokes CLI subprocesses with argument arrays rather than a shell, stores job bytes in a temporary directory, and sends back a JSON status/error response. Printer Manager now adds discovery, remote-file lists and printing, pause/resume/cancel, diagnostics, fan on/off, bounded timelapse, local Linux notifications and connection-profile management through additional allowlisted endpoints. See [Printer Manager reference](PRINTER_MANAGER.md).

**Mobile access:** GitHub Pages cannot talk to your printer, but a private HTTPS hostname protected by Cloudflare Access and routed via Cloudflare Tunnel to this loopback server **can** provide remote control. Enable and validate `CF_ACCESS_*` origin authentication before publishing the Tunnel route. Do not expose ports 8765, 8899 or 8080 directly.

## Normal workflow

1. Read the status and check that the printer is available. Inspect the physical setup yourself.
2. Import a model, choose process/material and settings, and click **Slice**. **Auto slice** is optional.
3. Review G-code/toolpath preview. Changing the model or settings invalidates the previous sliced result.
4. Select **Upload only** or **Print**. The latter sends the `--start` flag; both affect printer storage/state and must be supervised.

**Safety and verification:** The CLI rejects uploads to a printer reported as actively printing by default; the UI does not pass `--force`. Upload-only avoids M23/M24 but M601 S1 has firmware-dependent, incompletely documented behavior: it is **not** proven physically safe to treat upload-only as impossible to start a job. M661 confirms a file **name** is listed but not its contents or size. G-code-to-GX wrapping does not fix invalid toolpath commands. Actual printer-side success cannot be inferred from an HTTP 200 response.

## Troubleshooting

- **Disconnected** on the hosted GitHub Pages version is expected: Pages serves a static slicer and has no local `/api` routes. The AD4 pill opens the printer manager, but its real CLI controls are disabled without a trusted bridge.
- **Disconnected** locally: verify the venv is active, `ffadv4manager status --json`, host/IP, printer LAN connectivity, and local bridge logs.
- **Camera unavailable:** verify `ffadv4manager camera snapshot /tmp/ad4-test.jpg`; the camera HTTP endpoint is independent of printer-control TCP.
- **Missing build:** run `npm ci && npm run build` before `npm run local`.
- **Slicing problems:** verify browser WebGL, compatible models, settings, and console errors.

Related: [FFAD4Manager full CLI reference](https://github.com/spidey000/FFAD4Manager/blob/main/docs/CLI.md) and [root README feature matrix](../README.md#what-ffad4manager-can-do--and-what-this-web-ui-exposes).
