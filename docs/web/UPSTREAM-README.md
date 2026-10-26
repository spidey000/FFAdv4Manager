# Install ThreeSlicer remotely — copy this prompt into your AI agent

> **Copy the entire prompt below into an AI coding agent with terminal access to your always-on Linux host.** The goal is to control your FlashForge Adventurer 4 **securely from anywhere in the world**, via a private web UI protected by **Cloudflare Tunnel + Cloudflare Access**, without opening router ports. The agent should follow [the complete deployment guide](docs/REMOTE_ACCESS.md).

```text
Act as my installation, security and verification agent. Deploy ThreeSlicer
Responsive as an always-on, private HTTPS web application so I can slice models
and manage my FlashForge Adventurer 4 from my phone or computer worldwide.

Repositories:
- https://github.com/spidey000/Three_slicer_responsive
- https://github.com/spidey000/FFAD4Manager

Architecture: remote browser -> Cloudflare Access -> Cloudflare Tunnel ->
127.0.0.1:8765 ThreeSlicer backend (validates Cloudflare Access JWT) ->
FFAD4Manager CLI -> Adventurer 4 on the local printer network.

First read README.md, docs/REMOTE_ACCESS.md, docs/AD4_LOCAL.md,
and the FFAD4Manager CLI docs. Work on a Linux computer that stays online
and shares a trusted LAN with the Adventurer 4. Require Node.js 20+,
npm, Python 3.9+, a Python venv, pip and cloudflared.

IMPORTANT: Cloudflare configuration MUST precede publishing the Tunnel route.
Never make a public, unauthenticated printer-control endpoint. Never expose
ports 8765, 8899 or 8080 through router port forwarding or 0.0.0.0.
Ask permission before changing OS packages, services, firewall or Cloudflare.

1. Inspect the host, check whether repositories or a cloudflared Tunnel already
   exist, and preserve all existing files, services and unrelated tunnel routes.
   Ask me for the intended public hostname, approved login email, Cloudflare
   team domain, Access application AUD tag, and the printer LAN IP (or let me
   confirm a read-only ffadv4manager discover --json result). Use placeholders
   until the required settings are known; do not invent domains or passwords.
2. Clone or safely update both repositories. Use an isolated Python virtualenv.
   Install FFAD4Manager from its source repository with pip install -e and
   install PyJWT[crypto] for origin JWT signature validation. Run the read-only
   ffadv4manager status --json command; never start a print while testing.
3. Enter Three_slicer_responsive, run npm ci and npm run build, and verify that
   dist/index.html exists. Do not deploy an unbuilt or GitHub-Pages-only version.
4. In Cloudflare Zero Trust, create/reuse a Self-hosted Access application for
   the exact public hostname (protect ALL paths), restrict Allow to my
   authorized identity, ideally with MFA, and allow no Bypass rules. Obtain
   its AUD tag. Set up/reuse a persistent Cloudflare Tunnel with a published
   HTTP route mapping that hostname to http://127.0.0.1:8765 ON THIS HOST.
   Do not override the forwarded Host header to localhost. If available,
   enable Tunnel's Protect with Access as an additional validation layer.
   Never touch unrelated DNS, routes, Access applications or tunnel tokens.
5. Configure the bridge's four SERVER-SIDE settings, all required:
   CF_ACCESS_TEAM_DOMAIN, CF_ACCESS_AUD, CF_ACCESS_PUBLIC_ORIGIN (the exact
   https://hostname, without path or slash), and CF_ACCESS_EMAIL.
   Do not bundle them in browser JS or commit them into Git.
   The origin MUST verify Cf-Access-Jwt-Assertion signature, issuer, audience,
   expiration and allowed email. Public POST requests must have the matching
   Origin header. Missing or invalid tokens must fail closed.
6. Run the bridge with the Python venv and an unprivileged Linux service
   account that can use its configured FFAD4Manager. Configure systemd
   restart-on-failure and boot startup, and configure cloudflared to stay
   running. Keep the backend bound ONLY to 127.0.0.1. Secure env/token files.
7. Verify, WITHOUT sending machine-changing commands:
   - The app build and Python tests pass.
   - The CLI can query the actual printer on the LAN.
   - Unauthenticated requests to the public URL are blocked by Access.
   - Direct origin requests without valid JWT are denied (HTTP 401).
   - From an EXTERNAL NETWORK (for example, mobile data), the HTTPS hostname
     requires Access login; my authorized session can load the real web UI.
   - Read-only printer status and optionally a camera still work remotely.
   - All /api/printer/* paths are behind the same Access policy.
   If you cannot test an external network, report that explicitly.
8. Hand back the final private HTTPS URL, service status, restart/log commands,
   rollback instructions, which features are actually wired to FFAD4Manager,
   and any unverified steps. Do not claim worldwide access works just because
   a local build or Cloudflare configuration command succeeded.

For safety, do NOT upload G-code, start/pause/resume/cancel jobs, switch fans,
rename printers or issue other state-changing printer actions without my
explicit permission. Read-only checks are appropriate. Uploaded filename
confirmation does not prove file integrity or physical printer behavior.
Do not include credentials, tunnel tokens, service-token secrets, printer LAN
addresses or account identifiers in public commits/logs. Follow the official
Cloudflare guides and docs/REMOTE_ACCESS.md for exact configuration.
```

---

# ThreeSlicer Responsive — Adventurer 4 Web Slicer

A responsive browser-based slicer and Adventurer 4 management UI powered by [Three Slicer](https://github.com/kimgh06/Three_Slicer) and [FFAD4Manager](https://github.com/spidey000/FFAD4Manager). Its **recommended installation is a private, worldwide-accessible HTTPS service**: Cloudflare Access authenticates the user, Cloudflare Tunnel connects to an always-on home Linux host, and the loopback bridge validates Cloudflare Access JWTs before accessing the printer.

**[Secure worldwide deployment (recommended)](docs/REMOTE_ACCESS.md)** · **[Try the public slicer-only demo](https://spidey000.github.io/Three_slicer_responsive/)** · **[Local-only setup](docs/AD4_LOCAL.md)** · **[CLI reference](https://github.com/spidey000/FFAD4Manager/blob/main/docs/CLI.md)**

**Conservative printing defaults:** The standard 0.4 mm Adventurer 4 now opens with a low-speed, quality-oriented 0.20 mm profile **and Artillery PLA Basic material selected by default** (210°C first layer, 205°C subsequent layers, 55°C bed). When this PLA is selected, G-code containing heating instructions or recognized metadata above 220°C nozzle / 65°C bed is blocked before upload. This does not rewrite other material profiles or physically validate printer behavior. All bundled AD4 processes share the conservative speed and acceleration settings; saved custom processes can intentionally override them. See [the speed, acceleration and evidence reference](docs/AD4_CONSERVATIVE_PROFILE.md).

## What works today

| Feature | Available | Notes |
| --- | --- | --- |
| Responsive desktop, tablet and mobile UI | Yes | Mobile settings drawer; dark theme and touch-friendly controls. |
| Load 3D models | Yes | STL, OBJ, 3MF, AMF, PLY and STEP/STP through the underlying viewer. |
| 3D object/plate editing | Yes | Native viewer tools include transform, object management, multi-plate functions and painting where supported. |
| Browser-side slicing | Yes | `three-slicer@0.4.0` WebAssembly worker; does not require the CLI or the printer. |
| Adventurer 4 process/material presets | Yes | Fixed AD4 0.4 mm machine; all built-in process presets share cautious motion settings while retaining each process's other parameters. |
| Save, edit and delete named process/filament profiles | Yes (browser-local) | Choose Save current settings as new profile in either dropdown. Saved custom presets persist in this browser's site storage; Update saved and Delete are available. No cloud synchronization. |
| Artillery PLA Basic filament preset | Yes | 205°C nozzle, 210°C initial layer, 55°C bed; non-HS starting values based on Artillery's temperature range. |
| Advanced slicing settings | Yes | Connected `SettingsPanel` with the same shared slicer settings state. |
| Automatic re-slicing | Yes | Optional Auto slice; changing the model or settings invalidates previous generated G-code. |
| Toolpath preview and simulated nozzle traversal | Yes | Layer and move scrubbing, play, fast-forward, pause and reset; simulated movement is **not** an accurate real-time print prediction. |
| Project/model export | Yes | Native viewer export actions, including 3MF/STL where supported by the upstream package. |
| Live printer status label | Authenticated self-hosted bridge | Reads `ffadv4manager status --json` approximately every 8 seconds; no bridge on GitHub Pages. |
| Camera still image | Authenticated self-hosted bridge | Uses `ffadv4manager camera snapshot`. If unavailable, the UI clearly shows a demo placeholder, not a live feed. |
| Upload sliced G-code to printer | Authenticated self-hosted bridge | Invokes `ffadv4manager upload` and automatic G-code-to-GX wrapping. Requires a reachable printer. |
| Upload and request print start | Authenticated self-hosted bridge | Invokes `ffadv4manager upload ... --start`. Device state must be supervised. |

This is functional slicer integration, not a static mockup. The UI delegates geometry manipulation, slicing and G-code preview to `three-slicer-viewer@0.4.0` and `three-slicer@0.4.0` instead of recreating the underlying engine.

## Secure worldwide installation (recommended)

The normal production URL is your **own protected Cloudflare hostname**, for example `https://slicer.example.com/Three_slicer_responsive/`. That is **not** the GitHub Pages URL, which intentionally has no printer backend. Cloudflare Access requires an authorized login before the UI and all `/api/printer/*` routes; the local bridge verifies the Access JWT again at the origin.

**Required order:**

1. Set up an always-on Linux machine on the printer's local network. Install the slicer, FFAD4Manager and `PyJWT[crypto]`; build with `npm ci && npm run build`.
2. **Before publishing the hostname**, create a Cloudflare Access self-hosted application for the **entire hostname**, with an explicit Allow policy for your identity and no Bypass paths.
3. Create or reuse an outbound Cloudflare Tunnel route from that hostname to `http://127.0.0.1:8765` on the same machine; **preserve the public Host header**, and do not open router ports.
4. Configure the bridge's `CF_ACCESS_TEAM_DOMAIN`, `CF_ACCESS_AUD`, `CF_ACCESS_PUBLIC_ORIGIN` and `CF_ACCESS_EMAIL` environment variables. The bridge rejects unsigned or invalid JWTs, wrong Host/Origin and incomplete configuration.
5. Start the bridge and `cloudflared` as persistent systemd services. Verify unauthorized requests are denied, then sign in to your private HTTPS URL **from outside your home network** and check printer status without changing printer state.

The complete, reproducible procedure, Cloudflare dashboard steps, environment-file template, example systemd unit and verification checklist are in **[docs/REMOTE_ACCESS.md](docs/REMOTE_ACCESS.md)**. Never publish the unauthenticated local-only mode using a Tunnel.

### Local-only installation (development and troubleshooting)

The following commands are for a trusted local host; this mode **does not provide worldwide access**.

### Requirements

- A Linux host with **Node.js 20+**, npm, **Python 3.9+**, Python venv and pip.
- A browser with WebGL for the 3D workspace.
- For printer features only: an Adventurer 4 reachable on the same trusted local network, the FFAD4Manager CLI, and the printer's IP address. The legacy command protocol uses TCP port `8899`, and the default camera URL uses HTTP port `8080`.
- No printer connection is required to use browser-based slicing.

```bash
git clone https://github.com/spidey000/Three_slicer_responsive.git
git clone https://github.com/spidey000/FFAD4Manager.git
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ./FFAD4Manager
ffadv4manager config set --host 192.168.1.50   # REPLACE with your printer's IP
ffadv4manager status --json                     # read-only connection check
cd Three_slicer_responsive
npm ci
npm run build
npm run local
```

Open **http://127.0.0.1:8765/Three_slicer_responsive/** on the host running the bridge (local mode only). To make this installation accessible worldwide, complete **all** Cloudflare Access, Tunnel and origin validation steps in [the remote access guide](docs/REMOTE_ACCESS.md). You can use `AD4_HOST`, `AD4_CLI` and `AD4_WEB_PORT` locally as documented in [the local setup](docs/AD4_LOCAL.md).

For browser-only development:

```bash
npm ci
npm run dev
# Optional production smoke check:
npm run build
```

The Vite dev server proxies `/api` to the local bridge on port `8765`; printer functions therefore require the bridge even in development.

## What FFAD4Manager can do — and what this web UI exposes

**Key:** **UI** = available in the ThreeSlicer web UI through its protected self-hosted bridge; **CLI only** = implemented by FFAD4Manager but **not wired into this web UI**; **not available** = not provided as described. These statuses describe the current software interface, **not** a blanket guarantee of physical printer behavior.

| CLI function / command | CLI support | ThreeSlicer web UI | Details |
| --- | --- | --- | --- |
| Printer status, temperature, progress — `status --json` | Implemented | **UI** | Status, temperatures, current job, layers and reported progress in Printer Manager. |
| Printer camera still — `camera snapshot` | Implemented | **UI** | One image per request/refresh, not continuous video. |
| Upload G-code / GX — `upload FILE` | Implemented | **UI** | UI posts freshly sliced G-code; CLI performs GX wrapping and listing check. |
| Upload and start — `upload FILE --start` | Implemented | **UI** | Requests an actual print; requires explicit user action. |
| Readable and JSON file list — `files [--json]` | Implemented | **UI (local bridge)** | Printer Manager lists files and can start an existing file. |
| Raw file-list diagnostics — `files-raw` | Implemented | **CLI only** | Debug output is not shown in the app. |
| Existing printer file BMP preview — `files preview` | Implemented | **CLI only** | Different from camera snapshots. |
| Printer discovery — `discover [--json]` | Implemented | **UI (local bridge)** | Discover and select a printer exposed on port 8899. |
| Continuous status sampling — `watch` | Implemented | **CLI only** | UI polls basic status, but does not expose the CLI watch display/JSONL. |
| Firmware and identity — `info` | Implemented | **UI (local bridge)** | Information available in diagnostics. |
| Reported coordinates — `position` | Implemented | **UI (local bridge)** | Read-only reports; not physical measurement. |
| Connection diagnostics — `doctor` | Implemented | **UI (local bridge)** | The actual CLI doctor result is shown, without a simulated wizard. |
| Wait for printer conditions — `wait` | Implemented | **CLI only** | No web automation for ready/temperature thresholds. |
| Monitor to JSONL — `monitor` | Implemented | **CLI only** | Status/event logs and optional state-change snapshots. |
| Desktop state notifications — `notify` | Implemented | **UI (local bridge)** | Requires Linux `notify-send`; no web notifications. |
| Timelapse capture — `camera timelapse` | Implemented | **UI (local bridge)** | Interval-based still images; not synchronized to layers. |
| Get/open camera URL — `camera url/open` | Implemented | **CLI only** | UI provides a still-image modal, not a raw stream player. |
| Convert G-code to GX — `convert` | Implemented | **CLI only** as a separate control | Automatic conversion during upload is used, but no standalone UI converter. |
| Inspect local file metadata — `inspect` | Implemented | **CLI only** | CLI checks SHA-256, size and limited G-code metadata. |
| Start a stored remote job — `print REMOTE_NAME` | Implemented | **UI (local bridge)** | Stored files can be selected and printed after confirmation. |
| Pause, resume, cancel — `pause/resume/cancel` | Implemented | **UI (local bridge)** | The printer-management panel exposes these controls. |
| Fan on/off — `fan on/off` | Implemented | **UI (local bridge)** | Only 100%-on/off for the part-cooling fan, not the enclosure fan. |
| Rename printer — `printer rename` | Implemented | **CLI only** | No UI control. |
| Connection config — `config` | Implemented | **CLI only** | Host and camera settings managed on the host. |
| Named printer profiles — `profiles` / `--profile` | Implemented | **UI (local bridge)** | Named CLI connection profiles are managed separately from the slicer profile. |
| CLI help — `help` | Implemented | **CLI only** | Full CLI documentation is external to the web UI. |
| Separate FFAD4Manager slicer launcher — `slicer` | Implemented in FFAD4Manager | **Not used by this web app** | The CLI ships its own separately bundled local slicer UI; this repository uses `npm run local` and its own bridge. |
| OrcaSlicer post-processing upload hook | Implemented separately | **Not integrated** | Available in FFAD4Manager for OrcaSlicer, not called by this web app. |
| Continuous authenticated camera streaming in this UI | Not provided by this integration | **Not available** | Only on-demand JPEG snapshots are implemented here. |
| End-to-end uploaded-file integrity verification | Not implemented | **Not available** | M661 confirms listed filename, not the file's stored content/size. |
| Physically verified unattended print start / guaranteed no-start upload | Not established | **Not guaranteed** | Printer firmware side effects and GX compatibility require supervised real-world validation. |

The CLI has broader capabilities than this web UI. For details, flags and precise safety conditions, consult the [full FFAD4Manager command reference](https://github.com/spidey000/FFAD4Manager/blob/main/docs/CLI.md).

**Printer Manager:** tap the top-right AD4 status pill. The management screen reflects real CLI results only; GitHub Pages has no printer API. [Functionality and safety notes](docs/PRINTER_MANAGER.md).

## Printer workflow (local or authenticated remote session)

1. On the local server, confirm `ffadv4manager status --json` works and the printer is ready. Check the nozzle, bed, material, filament and printer-side conditions yourself.
2. Import a 3D file and adjust process/filament parameters. Select **Slice** or enable **Auto slice**.
3. Review the toolpath preview, estimated time, layers, and generated output. The preview simulation does not control the physical printer.
4. Choose **Upload only** to invoke the CLI without its explicit start flag, or **Print** to request an upload followed by a start. Both actions contact real hardware; supervise the printer.

**Important:** Upload-only intentionally omits M23/M24, but M601 S1 has undocumented firmware behavior; it cannot be advertised as a universal physical no-start guarantee. The filename-verification step checks M661 listing only. Automatic GX conversion does **not** correct incompatible G-code commands. Do not assume an accepted upload/start response proves a successful, safe print.

## Architecture, limits and safety

- **Static demo:** GitHub Pages hosts only the browser slicer. The `/api/printer/*` routes do **not** exist on Pages; a static site cannot reach your local printer through those paths.
- **Self-hosted protected origin:** `server/ad4_bridge.py` serves `dist/` and the allowlisted Printer Manager endpoints (status, files, discovery, camera, jobs, diagnostics, timelapse, printer profiles and controls). The server always listens on `127.0.0.1:8765`; Cloudflare Tunnel forwards permitted HTTPS sessions from the Access-protected hostname. Requests must pass origin JWT and Host/Origin checks in protected mode. [Endpoint details](docs/PRINTER_MANAGER.md).
- **Access control:** Without `CF_ACCESS_*` variables, the bridge accepts only local loopback requests and must **not** be published through Cloudflare Tunnel. With all four required variables configured, it accepts the configured public hostname **only with a valid Cloudflare Access JWT** (verified signature, issuer, audience, expiry and authorized email); public POST requests additionally require the exact HTTPS Origin. Cloudflare Access policy and origin validation are both mandatory. See [secure remote installation](docs/REMOTE_ACCESS.md).
- **Browser requirements:** The viewer needs WebGL. GitHub Pages cannot set isolation headers needed for `SharedArrayBuffer`; the slicer may fall back to a single-threaded worker.
- **Slicing profile:** This app pins the bundled `Flashforge Adventurer 4 Series 0.4 Nozzle` preset for slicing. The new discovered-printer list and CLI connection profiles select a command target; they do not change slicer machine presets.
- **Hardware testing:** We can validate builds and the deployed browser UI automatically; we cannot claim the physical print protocol is verified across printer firmware versions.

## Developer notes

`Viewport`, `SettingsPanel` and `useSlicer` share the same settings. The responsive styling is injected into the viewer's open Shadow DOM. The [toolpath control bridge](docs/REPRODUCCION_TRAYECTORIA.md) drives the actual upstream Preview inputs rather than a second renderer. If `three-slicer-viewer` changes its internal test IDs, re-test layer and movement scrubbing.

The GitHub Pages build deploys automatically from `main` using GitHub Actions. A post-deployment Chromium test checks the empty-state card at several mobile widths and opens the printer manager at 390px. Run `npm run build` to check the production bundle.

## Credits and licenses

This application integrates [Three Slicer](https://github.com/kimgh06/Three_Slicer): `three-slicer` is AGPL-3.0-or-later and `three-slicer-viewer` is MIT. Printer communication is provided by the separate [FFAD4Manager](https://github.com/spidey000/FFAD4Manager) project (GPL-3.0-or-later). This repository is distributed under AGPL-3.0-or-later. See [LICENSE](LICENSE) and the relevant upstream notices.
