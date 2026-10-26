#!/usr/bin/env bash
# Install the CLI, bridge, bundled FFmpeg and web build from one checkout.
# No printer access, firewall changes, service changes or credentials.
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

for program in python3 node npm; do
  if ! command -v "$program" >/dev/null 2>&1; then
    printf "Missing required executable: %s\n" "$program" >&2
    exit 1
  fi
done

python3 -c 'import sys; assert sys.version_info >= (3, 9), "Python 3.9+ required"'
node -e 'if (Number(process.versions.node.split(".")[0]) < 20) { console.error("Node.js 20+ required"); process.exit(1) }'

if [[ ! -x .venv/bin/python ]]; then
  python3 -m venv .venv || {
    printf "Cannot create .venv; install the OS python3-venv package and retry.\n" >&2
    exit 1
  }
fi

.venv/bin/python -m pip install -e . --only-binary=imageio-ffmpeg
npm --prefix frontend ci
npm --prefix frontend run build

# Verify FFmpeg launches from this Python environment. No printer is contacted.
.venv/bin/python -c 'import subprocess; from ffadv4manager.core.video import ffmpeg_executable; subprocess.run([ffmpeg_executable(), "-version"], check=True, stdout=subprocess.DEVNULL)'

printf "\nInstallation complete (CLI, UI and bundled FFmpeg).\n"
printf "Configure printer: ./.venv/bin/ffadv4manager config set --host YOUR_PRINTER_IP\n"
printf "Start local only: ./.venv/bin/ffadv4manager slicer\n"
printf "For secure remote access, first configure Cloudflare Access + Tunnel (docs/DEPLOY_CLOUDFLARE.md).\n"
