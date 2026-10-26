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
2. Clone only this repository. Create .venv at its root, pip install -e .,
   then cd frontend && npm ci && npm test && npm run build.
3. Configure the printer with ffadv4manager config set --host PRINTER_LAN_IP.
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
7. Run 'ffadv4manager slicer --require-access' with the repository as systemd
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
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
ffadv4manager config set --host 192.168.1.50  # Replace with the real LAN IP
ffadv4manager status --json                     # Read-only connectivity check
cd frontend
npm ci
npm test
npm run build
npm run local
```

Open **http://127.0.0.1:8765/** on the server host. The server binds to loopback only. This URL is **not remotely accessible**; do not publish this unauthenticated local-only mode through a tunnel. `npm run local` runs the Python server from the frontend directory; run it with the activated Python venv. Alternatively, from the repository root, run `ffadv4manager slicer`.

To use the slicer UI without the server while developing: `cd frontend && npm run dev`. Printer controls need the separately running bridge. The Vite development server is **not** the supported remote production service.

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
| Upload G-code or GX | Yes | Yes |
| Upload and request print start | Yes | Yes |
| Start stored file | Yes | Yes |
| Pause / resume / cancel | Yes | Yes |
| Firmware info, position, diagnostics | Yes | Yes |
| Cooling fan on/off | Yes | Yes |
| Camera timelapse | Yes | Yes; fixed interval session |
| Linux desktop notifications | Yes | Yes; runs on server, **not** phone push |
| Printer connection profiles | Yes | Yes |
| File thumbnail preview via CLI | Yes | CLI only |
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

- [Architecture](docs/ARCHITECTURE.md), [integration plan and provenance](docs/INTEGRATION_PLAN.md), [Cloudflare deployment](docs/DEPLOY_CLOUDFLARE.md), [API routes](docs/WEB_API.md), [CLI commands](docs/CLI.md).
- `docs/web/` and `docs/cli/UPSTREAM-README.md` preserve historical upstream documentation for reference. **Follow this root README and docs/DEPLOY_CLOUDFLARE.md** for the integrated layout; original two-repo paths are obsolete.
- Web UI: AGPL-3.0-or-later (root [LICENSE](LICENSE)); original Python CLI: GPL-3.0-or-later ([license text](LICENSES/CLI-GPL-3.0.txt)); upstream Third-Party Notices: [frontend notices](frontend/THREE-PARTY-NOTICES.md). Keep source and third-party attribution when distributing modified builds.
