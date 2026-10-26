# FFAdv4Manager — FlashForge Adventurer 4 web slicer + Python CLI

**One repository. One installation. Two independently identifiable products (Web UI and CLI), connected by a local HTTP bridge.**

This monorepo combines the latest [ThreeSlicer Responsive](https://github.com/spidey000/Three_slicer_responsive) web app with the [FFAD4Manager](https://github.com/spidey000/FFAD4Manager) Python printer CLI. The browser slices locally; the Python backend delegates printer control to the real CLI. It is intended for a Linux computer on the same trusted network as the printer, including private access from anywhere using **Cloudflare Tunnel + Cloudflare Access**.

## Give this prompt to your installation agent

> Copy the following prompt into a coding agent that has permission to operate on your Linux host. This is guidance, not an automatic installation.

```text
Install https://github.com/spidey000/FFAdv4Manager as ONE self-hosted application
for my FlashForge Adventurer 4. Follow README.md and docs/DEPLOY_CLOUDFLARE.md.
Do NOT clone the two historical upstream repos.

Architecture: browser -> authenticated HTTPS Cloudflare Access -> Cloudflare
Tunnel -> 127.0.0.1:8765 Python bridge -> installed local ffadv4manager CLI ->
printer LAN (TCP 8899; camera HTTP 8080).

1. Check Linux, Node.js >=20, Python >=3.9, npm and network access. Ask me for
   the printer's LAN IP, public HTTPS hostname, authorized login email,
   Cloudflare Access team hostname and the application's AUD. Do not guess.
2. Clone only this repository and run `bash scripts/install.sh`. It creates
   the .venv, installs the CLI/backend and the bundled FFmpeg binary through
   imageio-ffmpeg, installs npm dependencies and builds the frontend. Run
   frontend tests with `npm --prefix frontend test`.
3. Configure the printer with ./.venv/bin/ffadv4manager config set --host PRINTER_LAN_IP.
   Run read-only CLI status --json and discover --json; do not issue a print,
   upload, fan, temperature or motion command during setup.
4. Configure a Cloudflare Access self-hosted application with an Allow policy
   for my identity and NO Bypass policies. Protect the ENTIRE hostname before
   publishing the Tunnel route. Enable MFA wherever available.
5. Publish the exact hostname via Cloudflare Tunnel to
   http://127.0.0.1:8765, preserving the public Host header. Never forward
   router ports or expose port 8899 or 8080 publicly.
6. Store CF_ACCESS_TEAM_DOMAIN, CF_ACCESS_AUD, CF_ACCESS_EMAIL and
   CF_ACCESS_PUBLIC_ORIGIN in a root-readable, service-user-readable
   server-side environment file. No values in the repository or frontend.
7. Run './.venv/bin/ffadv4manager slicer --require-access' with the repository as systemd
   WorkingDirectory and the project's .venv. Keep the process loopback-only.
   Make the service persistent and preserve any unrelated tunnel routes.
8. Verify unauthenticated origin requests fail closed, the Access login is
   required from outside the LAN, and authorized read-only printer status works.
   Report what could not be verified; do not claim physical printer behavior
   or remote operation works before testing it.
9. Provide service commands, final private URL, log locations and rollback
   instructions. Ask before making network, firewall, service, account or
   printer-state-changing changes.
```

## Components and source layout

```text
FFAdv4Manager/
├── frontend/             React + Vite + ThreeSlicer, slicer UI & printer manager
│   ├── src/              Responsive interface, PLA defaults, profiles, preview
│   ├── tests/            Browser-independent UI/profile safety tests
│   └── dist/             Built assets (generated; not committed)
├── server/               Python same-origin REST bridge and Cloudflare JWT checks
│   ├── ad4_bridge.py     Serves frontend/dist and /api/printer/* endpoints
│   └── cloudflare_access.py
├── ffadv4manager/        Independent Python CLI + protocol, GX and camera
│   ├── cli.py            ffadv4manager command-line entry point
│   └── core/             FlashForge protocol and format implementations
├── tests/
│   ├── cli/              CLI/protocol tests from the original CLI project
│   └── server/           HTTP and Cloudflare Access tests
├── docs/                 Architecture, deployment, full CLI reference, API
├── scripts/              OrcaSlicer CLI upload hook
├── LICENSE               AGPL-3.0-or-later (web app)
├── LICENSES/              GPL-3.0-or-later CLI license text
└── pyproject.toml        Installable CLI (Python >=3.9)
```

**Division of responsibilities:** `frontend` never opens printer TCP sockets. `server` only accepts allowlisted requests and invokes the CLI; it is not a second printer protocol implementation. `ffadv4manager` can run independently of the web server. See [architecture](docs/ARCHITECTURE.md) and [the import plan](docs/INTEGRATION_PLAN.md).

## Quick start — local only

Requirements: Linux host on the printer LAN, Python 3.9+, pip/venv, Node.js 20+, npm, compatible Chromium/Firefox browser. No printer is required for slicer-only usage.

```bash
git clone https://github.com/spidey000/FFAdv4Manager.git
cd FFAdv4Manager
bash scripts/install.sh
./.venv/bin/ffadv4manager config set --host YOUR_PRINTER_IP
./.venv/bin/ffadv4manager status --json
./.venv/bin/ffadv4manager slicer
```

Open **http://127.0.0.1:8765/** on the server host. The bridge binds to loopback only: **never publish this unauthenticated mode** through a tunnel. `npm --prefix frontend run local` also uses the project's `.venv` without shell activation. The installer does not set up your printer, credentials, services or remote network access. Node/npm are required to build the frontend and remain in `frontend/node_modules`, separate from Python's `.venv`.

To use the slicer UI without the server while developing: `cd frontend && npm run dev`. Printer controls need the separately running bridge. The Vite development server is **not** the supported remote production service.

## Generate a real Adventurer 4 .gx file

**The web slicer outputs G-code; it is the Python CLI that creates GX.** The integrated workflow is:

```text
STL / 3MF -> browser ThreeSlicer -> G-code + duration + filament + PNG thumbnail
          -> POST /api/printer/jobs -> Python server -> ffadv4manager upload
          -> GX binary (58-byte header + 80x60 BMP + executable G-code)
          -> printer TCP 8899 (upload-only or upload-and-start)
```

The web UI uses the slicer's real estimate when available, renders an 80×60 model thumbnail (or uses an embedded thumbnail from the slicer), and adds G-code **comments only** for layer height, wall count, print speed, filament length and temperatures. The CLI converts those to the legacy FlashForge GX header and grayscale BMP. Temperature and motion commands in the executable G-code are **not** overwritten by metadata. When duration cannot be estimated, the header records `0` (unknown) rather than an invented second.

In the web UI, **Upload only** or **Print** automatically creates the real GX inside the local CLI upload process; it is normally a temporary file and is sent as `.gx` to the printer. To **save a persistent GX on disk** independently, first export a G-code file from the slicer, then run:

```bash
ffadv4manager convert model.gcode --output model.gx
ffadv4manager inspect model.gx
# After reviewing model and printer, upload without explicitly starting:
ffadv4manager upload model.gx
```

**Printer upload names:** by default both the slicer and CLI upload GX files as `HH_mm_X.XXm_original-name.gx`, e.g. `01_02_1.23m_Benchy.gx`. The hours/minutes and filament metres are taken from the actual GX header. When metadata is missing, the prefix visibly uses `--_--` or `unknownm` rather than claiming a fabricated estimate. An explicitly provided CLI `--remote-name` still overrides the automatic name. Names are normalized to safe ASCII printer filenames.

The separate CLI `convert` command does not contact the printer. The `upload` command contacts real hardware. **Upload only is not a firmware-verified guarantee of no physical start**; do not test it unattended.

See [GX thumbnail/metadata format and verification](docs/AD4_GX_METADATA.md). Firmware touchscreen behavior and correct storage of all bytes still need a supervised test on the actual Adventurer 4.

## Layer estimation and layer-triggered timelapse

The Adventurer 4 (observed firmware 2.2.4) reports `Layer: 0/0` even while printing. FFAdv4Manager now derives an **estimated** layer index from local G-code/GX extrusion heights and matches it to live `M114` Z coordinates; the `M27` percentage remains independent. Two stable readings are needed before a layer-change event, reducing false triggers from Z-hop. Layer tracking requires the original print file (or its generated index) and cannot identify a never-uploaded, unknown file. Variable layer heights are supported, but Z-hop coinciding with another layer height or very short layers can still reduce accuracy.

The web upload keeps only small, printer-scoped sidecar layer indices in the server's state directory (`$XDG_STATE_HOME/ffadv4manager/layers`, configurable using `AD4_LAYER_STATE_DIR`). Both the printer status API and the UI display estimated layer and Z, with an explicit source label. Select **automatic layer timelapse** before printing or start **By layer** during a tracked print. Layer captures stop when the printer reports a finished/ready state; an `M27` value of `100/100` alone does not terminate recording. Pause does not end recording. An MP4 is created at the end, downloadable through the authenticated UI. Captures are retained on the host at `$XDG_STATE_HOME/ffadv4manager/timelapses`.

`ffmpeg` is provided automatically by the `imageio-ffmpeg` wheel installed inside the project `.venv` on supported platforms; no `apt install ffmpeg` or separate system-wide binary is necessary. Offline CLI tools also work without the web UI:

```sh
ffadv4manager layers model.gx --json
ffadv4manager camera timelapse /path/to/output --on-layer --layer-file model.gx --interval 1.5 --job-name model.gx
```

Install or update both the CLI and web in one step using `bash scripts/install.sh` from the repository root. The installer reuses `.venv` and rebuilds the frontend; it does not contact the printer or touch Cloudflare settings. On unsupported operating systems or architectures, the installer reports a missing FFmpeg binary instead of falsely claiming the timelapse works.

Do not rely on layer estimates as verified firmware telemetry or a physical printer safety signal. No printer firmware modifications are made.

## Private HTTPS access from anywhere

Read **[Cloudflare Tunnel + Access deployment](docs/DEPLOY_CLOUDFLARE.md)**. In short: build the frontend on the LAN host, secure the public hostname with an Access Allow policy *first*, publish an outbound Tunnel route to `http://127.0.0.1:8765`, then run `ffadv4manager slicer --require-access` with all four `CF_ACCESS_*` variables. No port forwarding. The protected production URL is `https://YOUR_HOSTNAME/`, not the historical `/Three_slicer_responsive/` GitHub Pages path.

Configuration values are server-side only: `CF_ACCESS_TEAM_DOMAIN`, `CF_ACCESS_AUD`, `CF_ACCESS_EMAIL`, `CF_ACCESS_PUBLIC_ORIGIN`. The bridge verifies the signed Access assertion and the Host/Origin. Missing/partial configuration must never be treated as permission to expose it publicly.

## Feature matrix — UI versus CLI

| Capability | Python CLI | Integrated authenticated UI |
| --- | --- | --- |
| Status, temperatures, progress | Yes | Yes |
| Snapshot from printer camera | Yes | Yes; single JPEG, not video |
| Discover/select printer on LAN | Yes | Yes |
| List stored printer files | Yes | Yes |
| Upload G-code or GX | Yes | Yes; browser-generated G-code is converted to GX by CLI |
| Upload and request print start | Yes | Yes |
| Start stored file | Yes | Yes |
| Pause / resume / cancel | Yes | Yes |
| Firmware info, position, diagnostics | Yes | Yes |
| Cooling fan on/off | Yes | Yes |
| Camera timelapse | Yes | Yes; fixed interval session |
| Linux desktop notifications | Yes | Yes; runs on server, **not** phone push |
| Printer connection profiles | Yes | Yes |
| Generate 80×60 GX print thumbnail and time estimate | Yes | Yes; provided by browser slicing and converted by CLI |\n| Read a stored-file thumbnail from printer | Yes | CLI only |
| Raw protocol file listing | Yes | CLI only |
| CLI watch, monitor and wait | Yes | CLI only (UI polls status) |
| Rename printer | Yes | CLI only |
| Convert and inspect a local print file separately | Yes | CLI only; conversion also runs during upload |
| OrcaSlicer integration hook | Script included | No |
| Continuous camera stream | CLI can expose stream URL | Not integrated into UI |
| Verify remote uploaded bytes | Not established | Not established |
| Browser slicing and toolpath preview | No, independent UI capability | Yes |
| Artillery PLA Basic, saved process/material profiles | No, slicer setting | Yes, browser-local |

The frontend preserves the conservative Adventurer 4 process profile and **Artillery PLA Basic** default. Its profile storage is browser-local, separate from the CLI host/profile configuration. For complete command syntax see [CLI reference](docs/CLI.md); see [Web API](docs/WEB_API.md) for routes.

## Test without changing printer state

```bash
source .venv/bin/activate
python -m pip install pytest
python -m pytest -q tests
cd frontend
npm ci
npm test
npm run build
```

Automated tests are not a physical printer acceptance test. When validating a live printer, start with read-only `ffadv4manager status --json` and `files --json`. Do not run an unattended print to verify installation. File appearing in the M661 listing proves only that the filename was listed, **not** that GX bytes were stored correctly; and firmware effects of upload-only commands remain unverified across versions.

## Documentation and licensing

- [GX metadata and print preview](docs/AD4_GX_METADATA.md), [Architecture](docs/ARCHITECTURE.md), [integration plan and provenance](docs/INTEGRATION_PLAN.md), [Cloudflare deployment](docs/DEPLOY_CLOUDFLARE.md), [API routes](docs/WEB_API.md), [CLI commands](docs/CLI.md).
- `docs/web/` and `docs/cli/UPSTREAM-README.md` preserve historical upstream documentation for reference. **Follow this root README and docs/DEPLOY_CLOUDFLARE.md** for the integrated layout; original two-repo paths are obsolete.
- Web UI: AGPL-3.0-or-later (root [LICENSE](LICENSE)); original Python CLI: GPL-3.0-or-later ([license text](LICENSES/CLI-GPL-3.0.txt)); upstream Third-Party Notices: [frontend notices](frontend/THREE-PARTY-NOTICES.md). Keep source and third-party attribution when distributing modified builds.
