# Integrated Web API (same-origin)

The HTTP server is `server/ad4_bridge.py`, bound to `127.0.0.1:8765`.
The frontend calls **relative** `/api/printer/*`; there is no separate public
printer API hostname. Every endpoint requires a valid Cloudflare Access session
when protected remote mode is enabled. The API cannot authenticate itself if
Access is not configured, so local-only mode **must not be exposed remotely**.

| Method | Route | CLI implementation | Notes |
| --- | --- | --- | --- |
| GET | `/api/printer/session` | Server state | Current connection/profile and notifications |
| GET | `/api/printer/status` | `status --json` + `position --json` | Live status, firmware layer or debounced estimated Z layer when an uploaded index matches |
| GET | `/api/printer/discover` | `discover --json` | UDP local discovery |
| GET | `/api/printer/files` | `files --json` | Stored filename list |
| GET | `/api/printer/profiles` | `profiles list` | CLI connection profiles |
| GET | `/api/printer/diagnostics?kind=doctor|info|position` | Same CLI commands | Allowlisted read-only diagnostics |
| GET | `/api/printer/camera` | `camera snapshot` | On-demand JPEG, not video |
| GET | `/api/printer/timelapse` | Server subprocess state | Frames, capture mode, MP4-ready flag |\n| GET | `/api/printer/timelapse/video` | Recorded MP4 | Protected MP4 download; 404 until finalized |
| POST | `/api/printer/jobs?start=true|false` | `upload` with optional `--start` | Content-Type text/plain; slice output |
| POST | `/api/printer/upload?name=...&start=true|false&timelapse=layer` | `upload` with optional `--start` | Binary file, 100 MiB; timelapse flag only valid for start=true and indexed toolpaths |
| POST | `/api/printer/actions` | `pause`, `resume`, `cancel`, `print`, `fan` | Action allowlist; stored print must be listed |
| POST | `/api/printer/selection` | CLI profile or discovered host | Only discovered private IP or existing profile |
| POST | `/api/printer/profiles` | `profiles add` | Input validation |
| POST | `/api/printer/profiles/delete` | `profiles delete` | Input validation |
| POST | `/api/printer/timelapse` | CLI `camera timelapse` process | `{action:start,mode:layer|interval}` or `{action:stop}`; requires ffmpeg |
| POST | `/api/printer/notifications` | CLI `notify` process | Linux desktop notification helper |

For stored-file printing, `/api/printer/actions` accepts `timelapse_on_start: true` only when the selected file has a matching server-side layer index. Layer status is explicitly estimated, not the firmware's `M27 Layer: 0/0`.\n\nThe API is intentionally a narrow interface; do not expose arbitrary CLI
commands, shell execution or free-form G-code endpoints. It rejects invalid
Host/Origin headers and validates JWT signing key, issuer, AUD, expiry and email
when in Access mode. The bridge does not verify uploaded file byte integrity
on the printer; CLI listing confirmation is not that verification.
