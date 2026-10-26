#!/usr/bin/env python3
"""OrcaSlicer Linux post-processing helper.

Orca invokes this configured command through ``$SHELL -c`` and appends the
generated G-code path as its final, shell-quoted argument. Do not add a filename
placeholder to the configured command.
"""
from __future__ import annotations

import argparse
import configparser
import math
import sys
from pathlib import Path

from ffadv4manager.core import FlashForgeClient
from ffadv4manager.core.gcode_to_gx import upload_file as gx_upload_file
from ffadv4manager import config as config_store

DEFAULT_PORT = 8899
DEFAULT_TIMEOUT = 8.0


class HookConfigurationError(ValueError):
    """Invalid/missing persisted hook configuration (usage exit status 2)."""


def _port_arg(value: str) -> int:
    try:
        port = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("port must be an integer from 1 to 65535") from exc
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError("port must be an integer from 1 to 65535")
    return port


def _timeout_arg(value: str) -> float:
    try:
        timeout = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("timeout must be a finite positive number") from exc
    if not math.isfinite(timeout) or timeout <= 0:
        raise argparse.ArgumentTypeError("timeout must be a finite positive number")
    return timeout


def _require_safe_status(client: FlashForgeClient, stage: str) -> None:
    try:
        status = client.status()
    except Exception as exc:
        raise RuntimeError(f"could not read printer status {stage}; refusing to continue: {exc}") from exc
    if not status.machine_status:
        raise RuntimeError(
            f"printer status is unavailable or unparseable {stage}; refusing to continue"
        )
    if status.is_printing:
        raise RuntimeError(f"printer reports an active print {stage}; refusing (use --force to override)")
    machine_status = status.machine_status.strip().upper()
    if machine_status != "READY":
        raise RuntimeError(
            f"printer state {status.machine_status!r} is not a known idle state {stage}; "
            "refusing (use --force to override)"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("gcode", nargs="?", help="Generated G-code path appended by OrcaSlicer")
    parser.add_argument("--gcode", dest="gcode_option", help="G-code path (alternative to positional path)")
    parser.add_argument("--host", help="Printer IP/hostname; otherwise use shared ffadv4manager config")
    parser.add_argument("--port", type=_port_arg)
    parser.add_argument("--timeout", type=_timeout_arg)
    parser.add_argument("--start", action="store_true")
    parser.add_argument("--force", action="store_true", help="Override printer busy-state safety checks")
    parser.add_argument("--no-convert", action="store_true", help="Upload the generated file unchanged")
    args = parser.parse_args(argv)

    if args.gcode and args.gcode_option:
        parser.error("supply the G-code path either positionally or with --gcode, not both")
    gcode = args.gcode_option or args.gcode
    if not gcode:
        parser.error("no G-code path supplied; OrcaSlicer appends it as the final argument")

    try:
        try:
            stored = config_store.load_config()
        except configparser.Error as exc:
            raise HookConfigurationError(f"could not read shared config: {exc}") from exc
        host = args.host or stored.get("host")
        if not host:
            raise HookConfigurationError(
                "no printer host configured; pass --host or run ffadv4manager config set --host <ip>"
            )
        try:
            port = args.port if args.port is not None else int(stored.get("port", DEFAULT_PORT))
            timeout = args.timeout if args.timeout is not None else float(
                stored.get("timeout", DEFAULT_TIMEOUT)
            )
        except ValueError as exc:
            raise HookConfigurationError(f"invalid shared printer configuration: {exc}") from exc
        if not 1 <= port <= 65535:
            raise HookConfigurationError("configured printer port must be from 1 to 65535")
        if not math.isfinite(timeout) or timeout <= 0:
            raise HookConfigurationError("configured timeout must be a finite positive number")

        client = FlashForgeClient(host, port, timeout=timeout)
        if not args.force:
            _require_safe_status(client, "before upload")
        with gx_upload_file(
            gcode, no_convert=args.no_convert
        ) as (upload_path, converted_name):
            if converted_name:
                remote = client.upload_and_confirm_listed(upload_path, converted_name)
            else:
                remote = client.upload_and_confirm_listed(upload_path)
        print(f"Uploaded and listed {remote}")
        if args.start:
            if not args.force:
                _require_safe_status(client, "immediately before print start")
            print(client.print_file(remote))
        return 0
    except HookConfigurationError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001 - postprocessor must never emit a traceback
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
