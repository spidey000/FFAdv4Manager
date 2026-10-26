# Integrated Web API (same-origin)

The HTTP server is `server/ad4_bridge.py`, bound to `127.0.0.1:8765`.
The frontend calls **relative** `/api/printer/*`; there is no separate public
printer API hostname. Every endpoint requires a valid Cloudflare Access session
when protected remote mode is enabled. The API cannot authenticate itself if
Access is not configured, so local-only mode **must not be exposed remotely**.

| Method | Route | CLI implementation | Notes |
| --- | --- | --- | --- |
| GET | `/api/printer/session` | Server state | Current connection/profile and notifications |
| GET | `/api/printer/status` | `status --json` | Live reported state |
| GET | `/api/printer/discover` | `discover --json` | UDP local discovery |
| GET | `/api/printer/files` | `files --json` | Stored filename list |
| GET | `/api/printer/profiles` | `profiles list` | CLI connection profiles |
| GET | `/api/printer/diagnostics?kind=doctor|info|position` | Same CLI commands | Allowlisted read-only diagnostics |
| GET | `/api/printer/camera` | `camera snapshot` | On-demand JPEG, not video |
| GET | `/api/printer/timelapse` | Server subprocess state | Frames and running status |
| POST | `/api/printer/jobs?start=true|false` | `upload` with optional `--start` | Content-Type text/plain; slice output |
| POST | `/api/printer/upload?name=...&start=true|false` | `upload` with optional `--start` | Binary file; 100 MiB limit |
| POST | `/api/printer/actions` | `pause`, `resume`, `cancel`, `print`, `fan` | Action allowlist; stored print must be listed |
| POST | `/api/printer/selection` | CLI profile or discovered host | Only discovered private IP or existing profile |
| POST | `/api/printer/profiles` | `profiles add` | Input validation |
| POST | `/api/printer/profiles/delete` | `profiles delete` | Input validation |
| POST | `/api/printer/timelapse` | CLI `camera timelapse` process | Start/stop interval captures |
| POST | `/api/printer/notifications` | CLI `notify` process | Linux desktop notification helper |

The API is intentionally a narrow interface; do not expose arbitrary CLI
commands, shell execution or free-form G-code endpoints. It rejects invalid
Host/Origin headers and validates JWT signing key, issuer, AUD, expiry and email
when in Access mode. The bridge does not verify uploaded file byte integrity
on the printer; CLI listing confirmation is not that verification.
