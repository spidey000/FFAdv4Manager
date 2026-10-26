# Secure worldwide access with Cloudflare Tunnel + Access

ThreeSlicer Responsive can be operated from a phone, tablet or computer anywhere in
the world, **without opening inbound router ports**, when its local printer bridge
runs behind a Cloudflare Tunnel protected by Cloudflare Access.

```text
Remote browser (HTTPS + Cloudflare Access login)
      │
      ▼
Cloudflare Access (email/identity allow policy)
      │
      ▼
Cloudflare Tunnel (outbound-only cloudflared connector)
      │
      ▼
127.0.0.1:8765 — ThreeSlicer HTTP bridge (origin validates Access JWT)
      │
      ▼
FFAD4Manager CLI on the always-on home Linux host
      │
      ▼
FlashForge Adventurer 4 on the trusted local network
```

**The hostname and Cloudflare Access app are not configured by this repository.**
You must configure them in your own Cloudflare account. Never put Cloudflare
credentials or service-token secrets in your Git repository.

## Prerequisites

- Linux host which can remain powered on and reach the printer on its LAN.
- Node.js 20+, npm, Python 3.9+ with venv and pip, WebGL-capable client browser.
- A domain hosted in Cloudflare DNS, a Cloudflare Zero Trust account, and the
  `cloudflared` connector on **the same host** as the local ThreeSlicer bridge.
- A **specific authorized login email** and a Cloudflare Access self-hosted
  application. Only this user should be included in its Allow policy.
- Cloudflare's **application AUD tag** and **team domain** (e.g.
  `myteam.cloudflareaccess.com`), available in your Zero Trust dashboard.
- Python package `PyJWT[crypto]` installed into the same Python environment as
  FFAD4Manager. The origin uses Cloudflare signing keys and validates Access JWTs.

## 1. Install the local slicer and printer CLI

Install under the account that will run the background service (examples below
use `/srv/threeslicer`; choose another directory if desired):

```bash
mkdir -p ~/threeslicer && cd ~/threeslicer
git clone https://github.com/spidey000/Three_slicer_responsive.git
git clone https://github.com/spidey000/FFAD4Manager.git
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ./FFAD4Manager
python -m pip install 'PyJWT[crypto]'
ffadv4manager discover --json            # read-only; may return []
ffadv4manager config set --host PRINTER_IP # use your confirmed printer IP
ffadv4manager status --json              # read-only connection check
cd Three_slicer_responsive
npm ci
npm run build
```

Do not assume a discovered device is the intended printer. Do not send movement,
heat, fan, upload, pause, resume, cancel or print commands during installation.

The CLI's configuration is stored under the Linux service user's home directory
(`~/.config/ffadv4manager/config.ini`, unless configured otherwise). Use the
same Linux account/venv to run the bridge, or configure a valid `AD4_HOST`.

## 2. Create the Cloudflare Access application **first**

In the [Cloudflare Zero Trust dashboard](https://one.dash.cloudflare.com/):

1. Open **Access controls → Applications → Create new application**.
2. Choose **Self-hosted and private** / public hostname.
3. Enter the exact hostname you will use, e.g. `slicer.example.com`. Protect
   the entire hostname, including `/Three_slicer_responsive/` and `/api/printer/*`.
4. Create an **Allow** policy for your specific login email/identity provider.
   Require MFA in your identity provider where possible. **Do not** add Bypass
   policies or leave unprotected URL paths.
5. After saving, copy the **Application Audience (AUD) Tag**, and note your
   Cloudflare Access **team hostname** (e.g. `team.cloudflareaccess.com`).

Access blocks unauthenticated visitors at the Cloudflare edge. The origin also
verifies the `Cf-Access-Jwt-Assertion` header's RSA signature, issuer, AUD,
expiration and exact allowed email; it does not trust the header's mere presence.

## 3. Publish only the loopback HTTP service with Tunnel

In the Cloudflare dashboard, open **Networking → Tunnels**. Create or select a
Tunnel running `cloudflared` on the same Linux host. Under its **Routes**, add a
**Published application** with:

| Setting | Value |
| --- | --- |
| Public hostname | `slicer.example.com` (replace with your real hostname) |
| Service type | HTTP |
| Service URL | `http://127.0.0.1:8765` |
| Origin HTTP Host header override | **None**: preserve `Host: slicer.example.com` |
| Access policy | The self-hosted Access application from step 2 |
| Other public routes to this port | **None** |

Cloudflare automatically creates an appropriate DNS record for a dashboard-managed
published application route on a Cloudflare-managed zone. Install and run the
`cloudflared` connector using Cloudflare's official instructions. On a remotely
managed tunnel, Cloudflare displays an installation command with a tunnel token:
**treat it as a secret**, never commit or paste it into your frontend.

Enable **Protect with Access** in Tunnel's settings if your Cloudflare dashboard
offers it. Keep origin JWT validation enabled regardless. Do not configure an
`httpHostHeader: localhost` override: it will break the bridge's public Host
validation and should not be used to bypass it.

Neither TCP port `8899` nor camera HTTP port `8080` is published; they are
only used by FFAD4Manager on the LAN. Port `8765` must stay bound to
`127.0.0.1`, not `0.0.0.0`. You do **not** need port forwarding.

## 4. Configure the local origin to validate Cloudflare Access

Set **all four** environment variables for the ThreeSlicer bridge process
(use the actual values from your Cloudflare account):

```dotenv
CF_ACCESS_TEAM_DOMAIN=YOUR_TEAM.cloudflareaccess.com
CF_ACCESS_AUD=YOUR_ACCESS_APPLICATION_AUD
CF_ACCESS_PUBLIC_ORIGIN=https://slicer.example.com
CF_ACCESS_EMAIL=your-allowed-email@example.com
```

The public origin is **only the HTTPS scheme plus the hostname**: no trailing
slash, port or path. The team hostname has no scheme. These settings are
server-side; do not put them into Vite/browser configuration.

**Fail-closed behavior:** if any variable is missing, the bridge refuses to
start. In Access mode, **every HTTP GET and POST** (including static UI files)
requires a valid Cloudflare Access JWT and the exact expected public Host.
Mutating POST requests additionally require
`Origin: https://slicer.example.com`. Requests to
`http://127.0.0.1:8765` are intentionally rejected while Access mode is on;
perform local diagnostics with the CLI instead.

Without any of the four variables, the bridge retains its existing
**local-loopback-only mode** and rejects nonlocal origins. Do not tunnel or
expose that unauthenticated development mode.

## 5. Run both services continuously

Use your OS service manager so the bridge and `cloudflared` restart after
power loss. Example **systemd** unit for the application (substitute your
real Linux account, paths and virtual environment):

```ini
# /etc/systemd/system/threeslicer.service
[Unit]
Description=ThreeSlicer Adventurer 4 secured origin
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=YOUR_LINUX_USERNAME
WorkingDirectory=/home/YOUR_LINUX_USERNAME/threeslicer/Three_slicer_responsive
EnvironmentFile=/etc/threeslicer/access.env
Environment=PATH=/home/YOUR_LINUX_USERNAME/threeslicer/.venv/bin:/usr/bin:/bin
ExecStart=/home/YOUR_LINUX_USERNAME/threeslicer/.venv/bin/python /home/YOUR_LINUX_USERNAME/threeslicer/Three_slicer_responsive/server/ad4_bridge.py
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

Store the four `CF_ACCESS_*` variables in
`/etc/threeslicer/access.env` with restrictive permissions and ownership.
The file is used by `EnvironmentFile`; do not prefix lines with `export`.
Only an authorized administrator should create this unit and restart services.
Do not reuse a service account without verifying its CLI configuration and file
permissions.

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now threeslicer
sudo systemctl status threeslicer
sudo journalctl -u threeslicer -n 60 --no-pager
# Verify that the bridge only listens on loopback:
ss -ltn | grep ':8765'
```

Start and enable your existing `cloudflared` system service according to its
installation instructions. Keep its tunnel token in its managed configuration,
not in this repository.

## 6. Verify access securely, without affecting the printer

1. From the origin host, run `ffadv4manager status --json`. This verifies
   read-only LAN communication with the Adventurer 4.
2. With Access mode enabled, an unauthenticated direct-origin probe must be
   **denied**, e.g.:

   ```bash
   curl -i -H 'Host: slicer.example.com' http://127.0.0.1:8765/Three_slicer_responsive/
   # Expected: HTTP 401 (no valid Access JWT)
   ```

3. Using **mobile data**, not household Wi-Fi, open
   `https://slicer.example.com/Three_slicer_responsive/`. Access must require
   the permitted login; unauthorized accounts must be denied.
4. After signing in, verify the page loads, the printer status is reported and
   the still-image camera works if desired. The web UI uses same-origin APIs;
   no CORS exception or public printer IP is required.
5. Confirm all `/api/printer/*` paths, including print-control endpoints, are
   protected by the same Access app and JWT validation.
6. **Never** execute upload, print, pause, resume, cancel, fan or movement
   commands as a deployment smoke test. Do a separate supervised hardware test
   only with the owner's explicit permission.

If the remote page returns 401 after a successful Access login, check the exact
`Host` forwarded to the origin, `CF_ACCESS_PUBLIC_ORIGIN`, team domain,
AUD, allowed email, Python `PyJWT[crypto]` installation, clock synchronization,
and JWT validation logs. A missing JWT header will be rejected. Do not disable
origin verification to make a failing setup appear to work.

## Operational notes and limitations

- GitHub Pages remains a **public slicer-only demo**. The privately authenticated
  remotely controllable app is the **self-hosted** origin behind your Tunnel.
- Cloudflare and your account plan may impose upload/body-size and timeout
  limits on large G-code submissions; the local bridge's 100 MiB maximum is
  **not** a promise that Cloudflare accepts a request of that size.
- Local process and CLI can still reach the printer with no Internet, but remote
  access requires the Linux host, `cloudflared` and Cloudflare Access to be up.
- Client-side custom slicer process/filament profiles currently use
  browser-local storage; they are **not synchronized** across mobile and PC.
- The Access JWT validator loads the team's current public signing keys from
  Cloudflare and caches them briefly, allowing regular key rotation.
- The printer's legacy command protocol and camera stream are not authenticated
  or encrypted on the LAN. Keep the printer on a trusted network; Access only
  secures the connection from the browser to the local gateway.
- The CLI's M661 upload verification proves a filename is listed, **not** file
  integrity or physical printing. Upload-only has firmware-specific caveats;
  supervise actual operations.

## Official references

- [Cloudflare Tunnel setup](https://developers.cloudflare.com/tunnel/get-started/)
- [Publish and protect a self-hosted Access application](https://developers.cloudflare.com/cloudflare-one/access-controls/applications/http-apps/self-hosted-public-app/)
- [Validate Access JWTs at the origin](https://developers.cloudflare.com/cloudflare-one/access-controls/applications/http-apps/authorization-cookie/validating-json/)
- [ThreeSlicer local setup](AD4_LOCAL.md)
- [FFAD4Manager CLI commands](https://github.com/spidey000/FFAD4Manager/blob/main/docs/CLI.md)
