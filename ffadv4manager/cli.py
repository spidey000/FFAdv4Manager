from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import time
import urllib.request
import webbrowser

from ffadv4manager.core import (
    CameraError,
    FlashForgeClient,
    build_stream_url,
    capture_first_frame,
    discover_printers,
)
from ffadv4manager import config as config_store
from ffadv4manager import profiles as profile_store
from ffadv4manager.core.inspect_file import inspect_file
from ffadv4manager.core.gcode_to_gx import (
    convert_gcode_to_gx,
    upload_file as gx_upload_file,
)

DEFAULT_PORT = 8899
DEFAULT_TIMEOUT = 8.0
DEFAULT_CAMERA_PORT = 8080
DEFAULT_CAMERA_PATH = "/?action=stream"

_HELP_TOPICS = {
    "status": "status\n  Read printer state, current file, temperatures, and progress. Prints a human-readable status summary.",
    "files": "files\n  List printer-side files. Output is one file per line.",
    "files-raw": "files-raw\n  Print the unparsed response to the printer's file-list request.",
    "files preview": "files preview REMOTE_NAME --output FILE.bmp\n  Fetch a printer-side BMP thumbnail with M662; this is not a live camera image.",
    "watch": "watch [--interval SECONDS] [--jsonl] [--count N]\n  Refresh status; JSONL emits one structured sample per line.",
    "discover": "discover [--timeout SECONDS] [--json]\n  Search for printers with UDP multicast/broadcast discovery. Does not require a configured host or connect to printer TCP. Prints a name/IP/port table, or a JSON array with --json; no JSON results is []. On an interactive terminal, human-readable output offers to save a discovered host when exactly one printer advertises command port 8899; with multiple such printers, choose one first. This uses the port advertised in UDP discovery, not a TCP port scan. JSON and non-interactive runs never prompt or save config.",
    "camera": "camera {url,open,snapshot}\n  Build or use the printer's live MJPEG stream URL. Uses the configured printer host or root --host, and does not open a printer TCP connection. Camera defaults: HTTP port 8080 and path /?action=stream. The HTTP endpoint has no authentication; use only on a trusted network. See `ffadv4manager help camera url`, `ffadv4manager help camera open`, or `ffadv4manager help camera snapshot`.",
    "camera url": "camera url [--camera-port PORT] [--camera-path PATH]\n  Print only the camera stream URL, suitable for piping. Uses the configured printer host or root --host. Defaults are port 8080 and path /?action=stream; paths are kept literally, including query strings. No network request is made.",
    "camera open": "camera open [--camera-port PORT] [--camera-path PATH]\n  Ask Python's stdlib webbrowser module to open the MJPEG URL. This depends on a usable desktop browser; headless systems may not open a browser, in which case the URL is printed with guidance. The stream is plain HTTP and has no authentication.",
    "camera snapshot": "camera snapshot OUTPUT [--camera-port PORT] [--camera-path PATH]\n  Download and save the first complete JPEG frame, bounded by the helper's response-size limit. On success prints only the saved path. Requires the camera HTTP endpoint to be reachable; no printer TCP connection is used.",
    "camera timelapse": "camera timelapse DIRECTORY [--interval SECONDS] [--count N | --duration SECONDS]\n  Capture interval-based JPEG stills and append status metadata to timelapse.jsonl. Layer synchronization is not provided.",
    "upload": "upload LOCAL_FILE [--remote-name NAME] [--no-convert] [--start] [--force] [--log-file PATH]\n  Upload a local G-code/GX file; G-code is wrapped as GX automatically, preserving the original. --no-convert bypasses wrapping. Without --start, upload does not select or print the file; M661 does not verify size or content. --start explicitly selects and starts it after the listing check. Upload is refused when status reports printing unless --force is supplied. --log-file appends timestamped printer-response JSONL.",
    "convert": "convert INPUT --output OUTPUT.gx\n  Locally wrap supported G-code as GX. Does not contact a printer.",
    "inspect": "inspect LOCAL_FILE\n  Inspect local size, SHA-256, format, and recognized G-code metadata; does not contact a printer.",
    "info": "info [--json]\n  Query identity and firmware fields reported by M115.",
    "position": "position [--json]\n  Query reported axes using M114; reported coordinates are not independently measured.",
    "doctor": "doctor\n  Check stored connection, printer status, and camera endpoint availability.",
    "wait": "wait [--state STATE | --bed-below CELSIUS] [--interval SECONDS] [--timeout SECONDS]\n  Poll until one observed condition is true; timeout exits 1.",
    "monitor": "monitor --output PATH [--interval SECONDS] [--snapshots DIR]\n  Append printer status and state transitions to JSONL; optional still-image capture on change.",
    "notify": "notify --events paused,offline [--interval SECONDS]\n  Watch observed state changes and send Linux desktop notifications via notify-send.",
    "printer rename": "printer rename NAME\n  Set the reported printer name with M610 and verify it with M115.",
    "fan": "fan {on,off}\n  Switch the layer/part-cooling fan. This does not control the enclosure fan.",
    "profiles": "profiles {list,show,add,update,delete}\n  Manage named local connection/camera profiles; use --profile NAME before another command.",
    "print": "print REMOTE_NAME [--force]\n  Select a file already on the printer and start it. Use the printer-side name, with or without /data/. This starts a physical print. It is refused while status reports printing unless --force is supplied.",
    "pause": "pause\n  Pause the current print.",
    "resume": "resume\n  Resume the current print.",
    "cancel": "cancel\n  Cancel/reset the current SD print state. This is destructive to the active job.",
    "config": "config show | path | set | unset\n  Manage connection and camera defaults locally; these actions do not contact a printer. See `ffadv4manager help config show`, `ffadv4manager help config path`, `ffadv4manager help config set`, or `ffadv4manager help config unset`.",
    "config show": "config show\n  Print stored connection and camera values, or explain that no config is stored. Does not contact a printer.",
    "config path": "config path\n  Print the active config file location. Does not contact a printer.",
    "config set": "config set [--host HOST] [--port PORT] [--timeout SECONDS] [--camera-port PORT] [--camera-path PATH]\n  Store one or more connection/camera defaults. Camera defaults are port 8080 and path /?action=stream. At least one option is required. This writes the local config file and does not contact a printer.",
    "config unset": "config unset {host,port,timeout,camera_port,camera_path} [...]\n  Remove one or more stored connection or camera values. This writes the local config file and does not contact a printer.",
}


def _print_help(topic: str | None = None) -> int:
    if topic:
        text = _HELP_TOPICS.get(topic)
        if text is None:
            print(f"Unknown help topic: {topic}. Run 'ffadv4manager help' for available topics.", file=sys.stderr)
            return 2
        print(text)
        return 0

    print(f"""ffadv4manager — Linux/Python command-line client for FlashForge Adventurer printers
  The legacy `ad4ctl` command is also available as an alias.

USAGE
  ffadv4manager [CONNECTION OPTIONS] COMMAND [ARGS]
  ffadv4manager help [COMMAND [SUBCOMMAND]]

SUPPORTED COMMANDS
  status       Read machine state, temperatures, current file, and progress.
  watch        Repeatedly display status; supports JSONL and bounded samples.
  files        List remote files or fetch an M662 BMP preview.
  files-raw    Show the unparsed file-list response.
  info         Read model/firmware information (M115).
  position     Read reported axes (M114).
  inspect      Inspect a local G-code/GX file and calculate SHA-256.
  convert      Convert local G-code to GX for an Adventurer 4.
  doctor       Diagnose printer status and camera HTTP availability.
  wait         Wait for a reported printer condition.
  monitor      Record status samples and changes to JSONL.
  notify       Send desktop notifications for observed state events.
  upload       Upload a local file; optionally start it with --start.
  print        Select and start a printer-side file.
  pause        Pause the active print.
  resume       Resume the active print.
  cancel       Cancel/reset the active SD print state.
  discover     Find printers by UDP multicast/broadcast; no host required.
  camera       Build a stream URL, open the stream, or save a snapshot.
  config       Show, locate, set, or unset local connection/camera defaults.
  profiles     Manage named local printer profiles.
  printer      Rename the printer-reported name.
  fan          Control the layer/part-cooling fan.

CONNECTION AND CONFIGURATION
  Options: --host HOST, --port PORT, --timeout SECONDS. Defaults are port {DEFAULT_PORT}
  and timeout {DEFAULT_TIMEOUT:g} seconds. Values resolve separately in this order:
  command-line option > config file > built-in default. Host is required for
  printer commands; help, config, discovery, and camera URL commands need no
  printer-command connection (camera needs a host to construct its HTTP URL).

  Config is an INI file with a [connection] section and host, port, timeout,
  camera_port, and camera_path keys. Default path: ~/.config/ffadv4manager/config.ini;
  XDG_CONFIG_HOME changes
  the base directory to $XDG_CONFIG_HOME/ffadv4manager/config.ini. FFADV4MANAGER_CONFIG
  overrides the file path and takes precedence over legacy AD4CONNECT_CONFIG.
  If neither override is set and the new default file is absent, an existing
  ~/.config/ad4connect/config.ini is read; writes go to the new path and leave
  the legacy file untouched. These environment variables are read directly;
  ffadv4manager does not load .env files. No credentials are stored or used.

NETWORK / PROTOCOL
  Printer commands connect over TCP (default port 8899) using the legacy
  FlashForge protocol, sending ~GCODE followed by CRLF. This is not an encrypted
  or authenticated channel. The implementation is confirmed against Adventurer 4
  firmware v2.3.3-3.33; compatible firmware/models may behave differently.
  The printer must be reachable on the network. Help and config commands do not
  instantiate a network client or connect to a printer.

DISCOVERY AND CAMERA
  discover sends UDP discovery requests to multicast/broadcast targets and
  listens for the requested timeout. It does not require printer config.
  camera uses HTTP MJPEG (default http://HOST:8080/?action=stream), separate from
  the printer's command TCP protocol. No HTTP authentication is used. The camera
  endpoint must be reachable on a trusted network. camera open depends on the
  system browser and may not work headlessly; camera url supports piping and
  camera snapshot saves the first complete bounded JPEG without a browser.

SAFETY
  status/files/watch are observational; upload writes a file to printer storage.
  print, upload --start, resume, pause, and cancel affect a physical job/state.
  Review the target printer and file before starting a print. Upload/print check
  reported printing status and refuse by default; --force bypasses that check,
  not a general safety mechanism. cancel can discard/cancel the active job.

OUTPUT AND EXIT STATUS
  Successful commands return 0. Runtime/configuration errors return 1; Ctrl+C
  during watch returns 130. Discovery/camera errors and missing camera host return
  1. A busy-printer safety refusal or config set without
  values returns 2. Argument errors/help topics not recognized by argparse return
  2. Output is plain text; upload prints progress and the resulting remote path.

EXAMPLES
  ffadv4manager help upload
  ffadv4manager discover --json
  ffadv4manager camera url
  ffadv4manager camera snapshot /tmp/ad4.jpg
  ffadv4manager config set --host 192.168.1.50
  ffadv4manager status
  ffadv4manager status --json
  ffadv4manager profiles list
  ffadv4manager --profile workshop status
  ffadv4manager inspect ~/Downloads/part.gcode
  ffadv4manager --host 192.168.1.60 --timeout 12 files
  ffadv4manager upload ~/Downloads/part.gcode --remote-name part.gcode
  ffadv4manager upload ~/Downloads/part.gcode --start
  ffadv4manager print part.gcode
  ffadv4manager config show

Run `ffadv4manager help COMMAND` for command-specific details. `ffadv4manager COMMAND --help`
also displays that command's argument syntax.""")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ffadv4manager")
    # Defaults are None so we can tell an explicit flag apart from "fall back to
    # the stored config". Resolution happens after parsing in _resolve_connection.
    parser.add_argument("--host", help="Printer IP address or hostname (or store it with 'ffadv4manager config set')")
    parser.add_argument("--port", type=int, help=f"Printer TCP port, default {DEFAULT_PORT}")
    parser.add_argument("--timeout", type=float, help=f"Socket timeout in seconds, default {DEFAULT_TIMEOUT}")
    parser.add_argument("--profile", help="Use a named printer profile")

    sub = parser.add_subparsers(dest="command", required=True)
    help_cmd = sub.add_parser("help", help="Show the CLI guide or help for a command")
    help_cmd.add_argument("topic", nargs="*")
    status_cmd = sub.add_parser("status")
    status_cmd.add_argument("--json", action="store_true")
    files_cmd = sub.add_parser("files")
    files_cmd.add_argument("--json", action="store_true")
    files_sub = files_cmd.add_subparsers(dest="files_action")
    preview_cmd = files_sub.add_parser("preview", help="Save a printer-side BMP thumbnail")
    preview_cmd.add_argument("remote_name")
    preview_cmd.add_argument("--output", required=True)
    sub.add_parser("files-raw")

    info_cmd = sub.add_parser("info", help="Read printer identity and firmware details")
    info_cmd.add_argument("--json", action="store_true")
    position_cmd = sub.add_parser("position", help="Read reported machine coordinates")
    position_cmd.add_argument("--json", action="store_true")
    inspect_cmd = sub.add_parser("inspect", help="Inspect a local G-code/GX file")
    inspect_cmd.add_argument("file")
    doctor = sub.add_parser("doctor", help="Check printer and camera connectivity")
    wait_cmd = sub.add_parser("wait", help="Wait for a reported printer condition")
    wait_group = wait_cmd.add_mutually_exclusive_group(required=True)
    wait_group.add_argument("--state")
    wait_group.add_argument("--bed-below", type=float)
    wait_cmd.add_argument("--interval", type=float, default=5.0)
    wait_cmd.add_argument("--timeout", dest="wait_timeout", type=float, default=3600.0)

    discover = sub.add_parser("discover", help="Discover printers using UDP")
    discover.add_argument("--timeout", type=float, default=3.0)
    discover.add_argument("--json", action="store_true", help="Output a JSON array")

    camera_cmd = sub.add_parser("camera", help="Get or open the camera stream")
    camera_sub = camera_cmd.add_subparsers(dest="camera_action", required=True)
    camera_url = camera_sub.add_parser("url", help="Print only the camera stream URL")
    camera_open = camera_sub.add_parser("open", help="Open the camera stream in a browser")
    camera_snapshot = camera_sub.add_parser("snapshot", help="Save the first complete JPEG frame")
    camera_snapshot.add_argument("output")
    for camera_parser in (camera_url, camera_open, camera_snapshot):
        camera_parser.add_argument("--camera-port", type=_camera_port_arg)
        camera_parser.add_argument("--camera-path")

    watch = sub.add_parser("watch")
    watch.add_argument("--interval", type=float, default=5.0)
    watch.add_argument("--jsonl", action="store_true")
    watch.add_argument("--count", type=int)

    timelapse = camera_sub.add_parser("timelapse", help="Capture JPEG frames at an interval")
    timelapse.add_argument("directory")
    timelapse.add_argument("--interval", type=float, default=10.0)
    timelapse.add_argument("--count", type=int)
    timelapse.add_argument("--duration", type=float)
    timelapse.add_argument("--camera-port", type=_camera_port_arg)
    timelapse.add_argument("--camera-path")
    monitor = sub.add_parser("monitor", help="Record printer status to JSONL")
    monitor.add_argument("--output", required=True)
    monitor.add_argument("--interval", type=float, default=5.0)
    monitor.add_argument("--count", type=int)
    monitor.add_argument("--snapshots", help="Capture camera JPEGs on observed state changes")
    notify = sub.add_parser("notify", help="Notify on printer state events")
    notify.add_argument("--events", default="paused,offline")
    notify.add_argument("--interval", type=float, default=5.0)
    notify.add_argument("--count", type=int)

    upload = sub.add_parser("upload")
    upload.add_argument("file")
    upload.add_argument("--remote-name")
    upload.add_argument("--start", action="store_true")
    upload.add_argument("--force", action="store_true", help="Allow upload while printer reports printing")
    upload.add_argument("--log-file", help="Append timestamped printer responses to this JSONL file")
    upload.add_argument("--no-convert", action="store_true", help="Upload input unchanged")
    convert = sub.add_parser("convert", help="Convert local G-code to GX")
    convert.add_argument("input")
    convert.add_argument("--output", required=True)

    print_cmd = sub.add_parser("print")
    print_cmd.add_argument("remote_name")
    print_cmd.add_argument("--force", action="store_true", help="Allow print command while printer reports printing")

    sub.add_parser("pause")
    sub.add_parser("resume")
    sub.add_parser("cancel")

    printer_cmd = sub.add_parser("printer", help="Change printer identity")
    printer_sub = printer_cmd.add_subparsers(dest="printer_action", required=True)
    rename_cmd = printer_sub.add_parser("rename", help="Set the printer-reported name")
    rename_cmd.add_argument("name")
    fan_cmd = sub.add_parser("fan", help="Control the part-cooling fan")
    fan_sub = fan_cmd.add_subparsers(dest="fan_action", required=True)
    fan_sub.add_parser("on")
    fan_sub.add_parser("off")

    profiles_cmd = sub.add_parser("profiles", help="Manage named printer profiles")
    profiles_sub = profiles_cmd.add_subparsers(dest="profiles_action", required=True)
    profiles_sub.add_parser("list")
    profile_show = profiles_sub.add_parser("show")
    profile_show.add_argument("name")
    profile_add = profiles_sub.add_parser("add")
    profile_add.add_argument("name")
    _add_profile_values(profile_add)
    profile_update = profiles_sub.add_parser("update")
    profile_update.add_argument("name")
    _add_profile_values(profile_update)
    profile_delete = profiles_sub.add_parser("delete")
    profile_delete.add_argument("name")

    slicer_cmd = sub.add_parser(
        "slicer", help="Start the integrated web UI and printer API (requires a frontend build)"
    )
    slicer_cmd.add_argument(
        "--require-access",
        action="store_true",
        help="Refuse startup unless complete Cloudflare Access settings are configured",
    )

    config_cmd = sub.add_parser("config", help="View or edit stored connection defaults")
    config_sub = config_cmd.add_subparsers(dest="config_action", required=True)
    config_sub.add_parser("show", help="Print the stored config")
    config_sub.add_parser("path", help="Print the config file location")
    set_cmd = config_sub.add_parser("set", help="Store one or more connection defaults")
    set_cmd.add_argument("--host", help="Printer IP address or hostname")
    set_cmd.add_argument("--port", type=int)
    set_cmd.add_argument("--timeout", type=float)
    set_cmd.add_argument("--camera-port", type=_camera_port_arg)
    set_cmd.add_argument("--camera-path")
    unset_cmd = config_sub.add_parser("unset", help="Remove stored keys")
    unset_cmd.add_argument("keys", nargs="+", choices=config_store.KEYS)

    args = parser.parse_args(argv)

    if args.command == "help":
        if len(args.topic) > 2:
            parser.error("help accepts a command and optional subcommand")
        return _print_help(" ".join(args.topic) or None)

    if args.command == "config":
        return _handle_config(args)

    if args.command == "profiles":
        return _handle_profiles(args)

    if args.command == "slicer":
        from server.ad4_bridge import serve

        try:
            serve(require_access=args.require_access)
            return 0
        except Exception as exc:  # noqa: BLE001
            print(f"Error: {exc}", file=sys.stderr)
            return 1

    if args.command == "inspect":
        try:
            result = inspect_file(args.file)
            print(json.dumps(_inspection_json(result), ensure_ascii=False, sort_keys=True))
            return 0
        except Exception as exc:  # noqa: BLE001
            print(f"Error: {exc}", file=sys.stderr)
            return 1

    if args.command == "convert":
        try:
            convert_gcode_to_gx(args.input, args.output)
            print(args.output)
            return 0
        except Exception as exc:  # noqa: BLE001
            print(f"Error: {exc}", file=sys.stderr)
            return 1

    if args.command == "discover":
        try:
            printers = discover_printers(timeout=args.timeout)
            if args.json:
                print(json.dumps([{"name": p.name, "ip": p.host, "port": p.port} for p in printers]))
            elif not printers:
                print("No printers discovered.")
            else:
                print(f"{'NAME':<32} {'IP':<39} PORT")
                for printer in printers:
                    print(f"{printer.name:<32} {printer.host:<39} {printer.port}")
            if not args.json:
                _offer_discovered_host(printers)
            return 0
        except Exception as exc:  # noqa: BLE001 - CLI should show clear errors
            print(f"Error: {exc}", file=sys.stderr)
            return 1

    if args.command == "camera":
        try:
            return _handle_camera(args)
        except Exception as exc:  # noqa: BLE001 - CLI should show clear errors
            print(f"Error: {exc}", file=sys.stderr)
            return 1

    if args.command == "doctor":
        try:
            return _handle_doctor(args)
        except Exception as exc:  # noqa: BLE001
            print(f"Error: {exc}", file=sys.stderr)
            return 1

    host, port, timeout = _resolve_connection(args, parser)
    client = FlashForgeClient(host, port, timeout=timeout)

    try:
        if args.command == "status":
            status = client.status()
            if args.json:
                print(json.dumps(_status_json(status), sort_keys=True))
            else:
                _print_status(status)
        elif args.command == "watch":
            _watch(client, args.interval, jsonl=args.jsonl, count=args.count)
        elif args.command == "files":
            if args.files_action == "preview":
                bmp = client.preview_bmp(args.remote_name)
                Path(args.output).write_bytes(bmp)
                print(args.output)
            else:
                files = client.files()
                if args.json:
                    print(json.dumps(files, ensure_ascii=False))
                else:
                    for file in files:
                        print(file)
        elif args.command == "files-raw":
            print(client.files_raw())
        elif args.command == "info":
            info = client.info()
            print(json.dumps(info, ensure_ascii=False, sort_keys=True) if args.json else "\n".join(f"{k}: {v}" for k, v in info.items()))
        elif args.command == "position":
            position = client.position()
            print(json.dumps(position, sort_keys=True) if args.json else "\n".join(f"{axis}: {value:g}" for axis, value in position.items()))
        elif args.command == "wait":
            return _wait_for_condition(client, args.state, args.bed_below, args.interval, args.wait_timeout)
        elif args.command == "monitor":
            return _monitor(client, args, host)
        elif args.command == "notify":
            return _notify(client, args)
        elif args.command == "printer":
            response = client.rename(args.name)
            info = client.info()
            if info.get("Machine Name") != args.name:
                raise RuntimeError("M610 acknowledged but M115 did not report the requested printer name")
            print(response.rstrip())
        elif args.command == "fan":
            print((client.set_fan(255) if args.fan_action == "on" else client.fan_off()).rstrip())
        elif args.command == "upload":
            status = client.status()
            if status.is_printing and not args.force:
                print(
                    "Printer appears to be printing. Use --force to upload anyway.",
                    file=sys.stderr,
                )
                return 2
            response_callback = _response_logger(args.log_file) if args.log_file else _print_response
            with gx_upload_file(
                args.file, no_convert=args.no_convert
            ) as (upload_path, converted_name):
                remote_name = args.remote_name
                if converted_name:
                    requested = Path(remote_name).name if remote_name else converted_name
                    remote_name = str(Path(requested).with_suffix(".gx"))
                remote = client.upload_and_confirm_listed(
                    upload_path, remote_name, progress=_progress,
                    response_callback=response_callback,
                )
            print(f"\nUploaded and listed: {remote}")
            if args.start:
                print(client.print_file(remote, response_callback=response_callback))
        elif args.command == "print":
            status = client.status()
            if status.is_printing and not args.force:
                print(
                    "Printer appears to be printing. Use --force to start another job anyway.",
                    file=sys.stderr,
                )
                return 2
            print(client.print_file(args.remote_name))
        elif args.command == "pause":
            print(client.pause())
        elif args.command == "resume":
            print(client.resume())
        elif args.command == "cancel":
            print(client.cancel())
        elif args.command == "camera":
            return _capture_timelapse(client, args, host)
    except KeyboardInterrupt:
        return 130
    except Exception as exc:  # noqa: BLE001 - CLI should show clear errors
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


def _offer_discovered_host(printers) -> None:
    """Offer to store a discovered host, but only in an interactive terminal."""
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        return

    candidates = [printer for printer in printers if printer.port == DEFAULT_PORT]
    if not candidates:
        if printers:
            print("Ninguna impresora anuncia el puerto de comandos 8899; configuración sin cambios.")
        return

    if len(candidates) == 1:
        candidate = candidates[0]
        print(
            f"Puerto de comandos anunciado por descubrimiento: {candidate.port} "
            f"({candidate.name}, {candidate.host}); no se realizó un escaneo TCP."
        )
    else:
        print(
            f"Varias impresoras anuncian el puerto de comandos 8899 "
            "(puerto indicado por UDP, sin escaneo TCP):"
        )
        for number, printer in enumerate(candidates, start=1):
            print(f"  {number}) {printer.name} — {printer.host}:{printer.port}")
        try:
            selection = input("Elige una para configurar su host (número; Enter cancela): ").strip()
        except (EOFError, KeyboardInterrupt):
            selection = ""
        if not selection:
            print("Selección cancelada; configuración sin cambios.")
            return
        try:
            index = int(selection) - 1
        except ValueError:
            print("Selección no válida; configuración sin cambios.")
            return
        if not 0 <= index < len(candidates):
            print("Selección fuera de rango; configuración sin cambios.")
            return
        candidate = candidates[index]

    try:
        answer = input(
            f"¿Guardar {candidate.host} como host predeterminado de ffadv4manager? [s/N] "
        ).strip().casefold()
    except (EOFError, KeyboardInterrupt):
        answer = ""
    if answer not in {"s", "si", "sí"}:
        print("No se guardó el host; configuración sin cambios.")
        return

    config_store.save_config({"host": candidate.host, "port": candidate.port})
    print(f"Host predeterminado guardado: {candidate.host}")


def _resolve_connection(args, parser) -> tuple[str, int, float]:
    """Combine CLI flags, profile, stored config and defaults by field."""
    try:
        stored = _effective_settings(args)
    except (KeyError, ValueError) as exc:
        parser.error(str(exc))
    host = args.host or stored.get("host")
    if not host:
        parser.error(
            "no host given: pass --host <ip> or store one with "
            "'ffadv4manager config set --host <ip>'"
        )
    port = args.port if args.port is not None else int(stored.get("port", DEFAULT_PORT))
    timeout = (
        args.timeout if args.timeout is not None else float(stored.get("timeout", DEFAULT_TIMEOUT))
    )
    return host, port, timeout


def _effective_settings(args) -> dict[str, object]:
    stored: dict[str, object] = dict(config_store.load_config())
    profile_name = getattr(args, "profile", None)
    if profile_name:
        try:
            stored.update(profile_store.get_profile(profile_name))
        except KeyError as exc:
            raise ValueError(f"unknown printer profile: {profile_name}") from exc
    for key in ("host", "port", "timeout"):
        value = getattr(args, key, None)
        if value is not None:
            stored[key] = value
    return stored


def _add_profile_values(parser) -> None:
    parser.add_argument("--host")
    parser.add_argument("--port", type=int)
    parser.add_argument("--timeout", type=float)
    parser.add_argument("--camera-port", type=_camera_port_arg)
    parser.add_argument("--camera-path")


def _handle_profiles(args) -> int:
    action = args.profiles_action
    try:
        if action == "list":
            print(json.dumps(profile_store.list_profiles(), ensure_ascii=False))
        elif action == "show":
            print(json.dumps(profile_store.get_profile(args.name), ensure_ascii=False, sort_keys=True))
        elif action in {"add", "update"}:
            values = {key: getattr(args, key) for key in profile_store.PROFILE_KEYS if getattr(args, key) is not None}
            (profile_store.add_profile if action == "add" else profile_store.update_profile)(args.name, values)
            verb = "added" if action == "add" else "updated"
            print(f"Profile {verb}: {args.name}")
        elif action == "delete":
            profile_store.delete_profile(args.name)
            print(f"Deleted profile: {args.name}")
        return 0
    except (KeyError, ValueError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def _handle_config(args) -> int:
    path = config_store.config_path()

    if args.config_action == "path":
        print(path)
        return 0

    if args.config_action == "show":
        stored = config_store.load_config()
        if not stored:
            print(f"No config stored yet ({path}).")
            print("Set one with: ffadv4manager config set --host <ip>")
            return 0
        print(f"# {path}")
        for key in config_store.KEYS:
            if key in stored:
                print(f"{key} = {stored[key]}")
        return 0

    if args.config_action == "set":
        updates = {key: getattr(args, key) for key in config_store.KEYS if getattr(args, key) is not None}
        if not updates:
            print("Nothing to set. Pass a connection or camera option.", file=sys.stderr)
            return 2
        if "camera_port" in updates:
            try:
                _validate_camera_port(updates["camera_port"])
            except ValueError as exc:
                print(f"Invalid camera port: {exc}", file=sys.stderr)
                return 2
        saved = config_store.save_config(updates)
        print(f"Saved to {saved}")
        for key, value in updates.items():
            print(f"{key} = {value}")
        return 0

    if args.config_action == "unset":
        removed = config_store.unset_config(args.keys)
        if removed:
            print(f"Removed: {', '.join(removed)}")
        else:
            print("Nothing removed (keys were not set).")
        return 0

    return 0


def _camera_port_arg(value: str) -> int:
    try:
        port = int(value)
        _validate_camera_port(port)
        return port
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def _validate_camera_port(port: int) -> None:
    if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
        raise ValueError("camera port must be an integer from 1 to 65535")


def _handle_camera(args) -> int:
    stored = _effective_settings(args)
    host = args.host or stored.get("host")
    if not host:
        raise CameraError("no printer host given: pass --host <ip> or store one with 'ffadv4manager config set --host <ip>'")

    raw_port = args.camera_port
    if raw_port is None:
        raw_port = stored.get("camera_port", DEFAULT_CAMERA_PORT)
    try:
        camera_port = int(raw_port)
    except (TypeError, ValueError) as exc:
        raise CameraError(f"invalid configured camera port {raw_port!r}; set camera_port from 1 to 65535") from exc
    try:
        _validate_camera_port(camera_port)
    except ValueError as exc:
        raise CameraError(f"invalid camera port: {exc}") from exc

    camera_path = args.camera_path
    if camera_path is None:
        camera_path = stored.get("camera_path", DEFAULT_CAMERA_PATH)
    url = build_stream_url(host, camera_port, camera_path)

    if args.camera_action == "url":
        print(url)
        return 0
    if args.camera_action == "open":
        if webbrowser.open(url):
            print(f"Opened camera stream in your browser: {url}")
            return 0
        print(
            "Could not open a browser (this may be a headless system). "
            f"Open this camera URL manually: {url}",
            file=sys.stderr,
        )
        return 1
    if args.camera_action == "snapshot":
        saved = capture_first_frame(url, args.output)
        print(saved)
        return 0
    if args.camera_action == "timelapse":
        client = FlashForgeClient(host, int(stored.get("port", DEFAULT_PORT)), timeout=float(stored.get("timeout", DEFAULT_TIMEOUT)))
        return _capture_timelapse(client, args, host, url)
    return 0


def _print_status(status) -> None:
    print("FFADV4Manager status")
    print(f"Machine: {status.machine_status or '-'}")
    print(f"Move:    {status.move_mode or '-'}")
    print(f"File:    {status.current_file or '-'}")
    if status.nozzle_current is not None:
        print(f"Nozzle:  {status.nozzle_current}/{status.nozzle_target} °C")
    if status.bed_current is not None:
        print(f"Bed:     {status.bed_current}/{status.bed_target} °C")
    if status.sd_current is not None:
        pct = status.progress_percent
        pct_text = f" ({pct:.1f}%)" if pct is not None else ""
        print(f"Bytes:   {status.sd_current}/{status.sd_total}{pct_text}")
    if status.layer_current is not None:
        print(f"Layer:   {status.layer_current}/{status.layer_total}")


def _status_json(status) -> dict[str, object]:
    return {
        "machine_status": status.machine_status,
        "move_mode": status.move_mode,
        "current_file": status.current_file,
        "nozzle_current": status.nozzle_current,
        "nozzle_target": status.nozzle_target,
        "bed_current": status.bed_current,
        "bed_target": status.bed_target,
        "sd_current": status.sd_current,
        "sd_total": status.sd_total,
        "progress_percent": status.progress_percent,
        "layer_current": status.layer_current,
        "layer_total": status.layer_total,
    }


def _inspection_json(result) -> dict[str, object]:
    return {
        "path": str(result.path), "size_bytes": result.size_bytes,
        "sha256": result.sha256, "format": result.format, "metadata": result.metadata,
    }


def _record_jsonl(path: str, record: dict[str, object]) -> None:
    with open(path, "a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        stream.flush()


def _watch(client: FlashForgeClient, interval: float, *, jsonl: bool = False, count: int | None = None) -> None:
    _validate_poll(interval, count)
    samples = 0
    while count is None or samples < count:
        status = client.status()
        if jsonl:
            print(json.dumps({"timestamp": _utc_now(), **_status_json(status)}, sort_keys=True), flush=True)
        else:
            print("\033[2J\033[H", end="")
            _print_status(status)
            print("\nCtrl+C to stop watching.")
        samples += 1
        if count is None or samples < count:
            time.sleep(interval)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _validate_poll(interval: float, count: int | None) -> None:
    if not math.isfinite(interval) or interval <= 0:
        raise ValueError("interval must be a positive finite number")
    if count is not None and count <= 0:
        raise ValueError("count must be a positive integer")


def _wait_for_condition(client, state: str | None, bed_below: float | None, interval: float, timeout: float) -> int:
    _validate_poll(interval, None)
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("timeout must be a positive finite number")
    if bed_below is not None and not math.isfinite(bed_below):
        raise ValueError("bed-below must be a finite temperature")
    deadline = time.monotonic() + timeout
    while True:
        status = client.status()
        matched = (state is not None and status.machine_status == state) or (
            bed_below is not None and status.bed_current is not None and status.bed_current < bed_below
        )
        if matched:
            print(json.dumps({"matched": True, **_status_json(status)}, sort_keys=True))
            return 0
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            print("Timed out waiting for printer condition.", file=sys.stderr)
            return 1
        time.sleep(min(interval, remaining))


def _handle_doctor(args) -> int:
    settings = _effective_settings(args)
    host = settings.get("host")
    if not host:
        raise ValueError("no printer host configured; set one or use --profile / --host")
    port = int(settings.get("port", DEFAULT_PORT))
    timeout = float(settings.get("timeout", DEFAULT_TIMEOUT))
    result: dict[str, object] = {"host": host, "checks": []}
    failures = 0
    started = time.monotonic()
    try:
        status = FlashForgeClient(str(host), port, timeout).status()
        result["checks"].append({"name": "printer_status", "ok": True, "status": status.machine_status})
    except Exception as exc:
        failures += 1
        result["checks"].append({"name": "printer_status", "ok": False, "error": str(exc)})
    camera_port = int(settings.get("camera_port", DEFAULT_CAMERA_PORT))
    camera_path = str(settings.get("camera_path", DEFAULT_CAMERA_PATH))
    url = build_stream_url(str(host), camera_port, camera_path)
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            response.read(1)
        result["checks"].append({"name": "camera_http", "ok": True})
    except Exception as exc:
        failures += 1
        result["checks"].append({"name": "camera_http", "ok": False, "error": str(exc)})
    result["duration_seconds"] = round(time.monotonic() - started, 3)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 1 if failures else 0


def _capture_timelapse(client, args, host: str, url: str | None = None) -> int:
    _validate_poll(args.interval, args.count)
    if args.duration is not None and (not math.isfinite(args.duration) or args.duration <= 0):
        raise ValueError("duration must be a positive finite number")
    if args.count is not None and args.duration is not None:
        raise ValueError("choose either --count or --duration, not both")
    directory = Path(args.directory)
    directory.mkdir(parents=True, exist_ok=True)
    if url is None:
        settings = _effective_settings(args)
        url = build_stream_url(
            host,
            int(getattr(args, "camera_port", None) or settings.get("camera_port", DEFAULT_CAMERA_PORT)),
            getattr(args, "camera_path", None) or settings.get("camera_path", DEFAULT_CAMERA_PATH),
        )
    deadline = time.monotonic() + args.duration if args.duration is not None else None
    index = 0
    manifest = directory / "timelapse.jsonl"
    while args.count is None or index < args.count:
        if deadline is not None and time.monotonic() >= deadline:
            break
        status = client.status()
        stamp = datetime.now(timezone.utc)
        output = directory / f"frame-{stamp.strftime('%Y%m%dT%H%M%S')}-{index:06d}.jpg"
        capture_first_frame(url, output)
        _record_jsonl(str(manifest), {
            "timestamp": stamp.isoformat(), "image": output.name,
            "machine_status": status.machine_status, "current_file": status.current_file,
            "progress_percent": status.progress_percent,
        })
        print(output, flush=True)
        index += 1
        if args.count is not None and index >= args.count:
            break
        remaining = deadline - time.monotonic() if deadline is not None else args.interval
        if remaining > 0:
            time.sleep(min(args.interval, remaining))
    return 0


def _monitor(client, args, host: str) -> int:
    _validate_poll(args.interval, args.count)
    output = args.output
    snapshots = Path(args.snapshots) if args.snapshots else None
    if snapshots:
        snapshots.mkdir(parents=True, exist_ok=True)
    settings = _effective_settings(args)
    camera_url = build_stream_url(
        host, int(settings.get("camera_port", DEFAULT_CAMERA_PORT)),
        str(settings.get("camera_path", DEFAULT_CAMERA_PATH)),
    ) if snapshots else None
    previous = object()
    samples = 0
    while args.count is None or samples < args.count:
        stamp = _utc_now()
        try:
            status = client.status()
            state = status.machine_status or "UNKNOWN"
            changed = state != previous
            record: dict[str, object] = {"timestamp": stamp, "event": "status" if not changed else "state_change", **_status_json(status)}
            if changed and snapshots and camera_url:
                image = snapshots / f"event-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}-{samples:06d}.jpg"
                try:
                    capture_first_frame(camera_url, image)
                    record["snapshot"] = str(image)
                except Exception as exc:
                    record["snapshot_error"] = str(exc)
            previous = state
        except Exception as exc:
            state = "OFFLINE"
            changed = state != previous
            record = {"timestamp": stamp, "event": "offline" if changed else "poll_error", "error": str(exc)}
            previous = state
        _record_jsonl(output, record)
        print(json.dumps(record, ensure_ascii=False, sort_keys=True), flush=True)
        samples += 1
        if args.count is None or samples < args.count:
            time.sleep(args.interval)
    return 0


def _notify(client, args) -> int:
    _validate_poll(args.interval, args.count)
    executable = shutil.which("notify-send")
    if not executable:
        raise RuntimeError("notify-send was not found; install a desktop notification service")
    wanted = {event.strip().casefold() for event in args.events.split(",") if event.strip()}
    if not wanted or not wanted <= {"paused", "offline", "printing", "ready"}:
        raise ValueError("--events accepts paused,offline,printing,ready")
    previous = object()
    samples = 0
    while args.count is None or samples < args.count:
        try:
            status = client.status()
            raw_state = (status.machine_status or "unknown").casefold()
            state = "paused" if raw_state == "paused" else "printing" if status.is_printing else "ready" if raw_state == "ready" else raw_state
        except Exception:
            state = "offline"
        if state != previous and state in wanted:
            subprocess.run([executable, "FFADV4Manager", f"Printer state: {state}"], check=False)
            print(json.dumps({"timestamp": _utc_now(), "event": state}), flush=True)
        previous = state
        samples += 1
        if args.count is None or samples < args.count:
            time.sleep(args.interval)
    return 0


def _progress(done: int, total: int) -> None:
    width = 30
    ratio = done / total if total else 0
    filled = int(width * ratio)
    bar = "#" * filled + "-" * (width - filled)
    print(f"\rUploading [{bar}] {ratio * 100:5.1f}%", end="", flush=True)


def _print_response(command: str, response: str) -> None:
    print(f"Printer {command} reply: {response.rstrip()}", file=sys.stderr)


def _response_logger(path: str):
    def log_response(command: str, response: str) -> None:
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "command": command,
            "response": response,
        }
        with open(path, "a", encoding="utf-8") as log_file:
            log_file.write(json.dumps(record, ensure_ascii=False) + "\n")
        _print_response(command, response)

    return log_response


if __name__ == "__main__":
    raise SystemExit(main())
