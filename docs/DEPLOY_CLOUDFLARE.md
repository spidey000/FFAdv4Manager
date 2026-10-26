# Secure deployment: Cloudflare Tunnel + Access

This is the **authoritative** deployment guide for the consolidated
`spidey000/FFAdv4Manager` repository. Historical upstream guides under
`docs/web/` use an obsolete two-repo layout and old URL prefix.

## Prerequisites

- Always-on Linux host on the same trusted LAN as the FlashForge Adventurer 4.
- Python 3.9+, pip/venv, Node.js 20+, npm; `cloudflared` installed on this host.
- Known printer LAN IP; exact HTTPS public hostname (e.g. `printer.example.com`).
- Cloudflare Zero Trust team hostname, Access self-hosted application AUD and
  authorized sign-in email.
- A working Cloudflare Tunnel that you own. Protect the app with Cloudflare
  Access **before** attaching any publicly reachable Tunnel route.

## 1. Install and build from the single monorepo

```bash
git clone https://github.com/spidey000/FFAdv4Manager.git
cd FFAdv4Manager
bash scripts/install.sh
./.venv/bin/ffadv4manager config set --host PRINTER_LAN_IP
./.venv/bin/ffadv4manager status --json
npm --prefix frontend test
./.venv/bin/python -m pip install pytest
./.venv/bin/python -m pytest -q tests
```

Replace `PRINTER_LAN_IP` with the device's actual IP. Never commit it to a
public configuration file. The installer creates `.venv`, installs the CLI,
server and a bundled FFmpeg binary via `imageio-ffmpeg`, then runs `npm ci`
and builds the frontend. No system-wide FFmpeg installation is needed on
supported Linux hosts. It never configures the printer or cloud credentials.
Running tests and `status` does not request printer movement or print start.

## 2. Create the Access policy before publishing

In Cloudflare Zero Trust, create a **Self-hosted** Access application protecting
the **entire** public hostname including `/`, `/assets/*` and `/api/printer/*`.
Allow only your intended identity or group, ideally with MFA. Do not create
Bypass routes or unauthenticated API exceptions. Record its AUD tag and
the team hostname such as `myteam.cloudflareaccess.com`.

## 3. Configure server-side validation

Store the following in a service-managed environment file such as
`/etc/ffadv4manager/bridge.env` (root-owned and readable by the service user;
NOT committed into Git):

```dotenv
CF_ACCESS_TEAM_DOMAIN=myteam.cloudflareaccess.com
CF_ACCESS_AUD=REPLACE_WITH_APPLICATION_AUD
CF_ACCESS_EMAIL=your-authorized-email@example.com
CF_ACCESS_PUBLIC_ORIGIN=https://printer.example.com
```

All four values are required. `CF_ACCESS_PUBLIC_ORIGIN` is the exact scheme and
hostname with no path or trailing slash. The origin validates the signed
Cloudflare Access JWT against public keys, issuer, audience, expiry and email.
Any partial configuration causes the service to reject startup.

Run production with `--require-access` so missing configuration fails closed:

```bash
# With the protected service environment loaded:
./.venv/bin/ffadv4manager slicer --require-access
```

If you use a systemd service, an example (adapt the absolute paths and service
account for your environment) is:

```ini
[Unit]
Description=FFAdv4Manager protected web slicer and printer control
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=ffadv4
Group=ffadv4
WorkingDirectory=/srv/FFAdv4Manager
EnvironmentFile=/etc/ffadv4manager/bridge.env
ExecStart=/srv/FFAdv4Manager/.venv/bin/ffadv4manager slicer --require-access
Restart=on-failure
RestartSec=5
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
```

Create and permission the service account/directory appropriately; ensure
the **same service account** owns the CLI config under its home directory
(`~/.config/ffadv4manager/config.ini`) or set
`FFADV4MANAGER_CONFIG` to a dedicated file. Never point the service at a
different user's home without consent. Once the unit is installed:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now ffadv4manager.service
sudo systemctl status ffadv4manager.service
sudo journalctl -u ffadv4manager.service -f
```

## 4. Publish the Tunnel route

In the Cloudflare Tunnel configuration, map exactly
`printer.example.com` -> **`http://127.0.0.1:8765`** on this Linux host.
**Preserve** the external `Host: printer.example.com` header; do not override
it to `localhost`. Configure the Access application for the same hostname.
Avoid changing unrelated Tunnel routes, DNS records or services.

Do **not** expose TCP 8899, camera HTTP 8080 or HTTP 8765 via router
port forwarding. Bind the bridge only to loopback; do not use
`python -m http.server`, GitHub Pages or the Vite dev server as the public
printer-control origin.

## 5. Read-only verification

1. Confirm the server is listening on `127.0.0.1:8765`, not `0.0.0.0`.
2. Confirm unauthorized requests are rejected; in Access mode even requests
   directly to the loopback origin without a valid assertion fail.
3. From mobile data or another external network, visit
   `https://printer.example.com/`; confirm Access sign-in is required.
4. After authenticating, open the slicer and Printer Manager; check live status,
   stored files and an optional single camera snapshot. These are read-only.
5. Check `/api/printer/*` is under the **same** hostname protection.
6. Do not claim successful end-to-end physical printing from these checks.
   Test uploads and actual print starts only with explicit approval and
   in-person supervision.

## Rollback

Stop and disable the service, and remove only this application's Tunnel route
and Access application if you no longer want remote access. Do not delete
shared Tunnel routes or secrets for other applications. To roll back a software
release, redeploy the previous reviewed Git commit, reinstall the editable
Python package if necessary, rebuild `frontend/` and restart the service.
