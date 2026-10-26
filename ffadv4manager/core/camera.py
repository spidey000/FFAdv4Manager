"""Helpers for building camera stream URLs and saving an MJPEG frame."""

from __future__ import annotations

import urllib.error
import urllib.request
from pathlib import Path


class CameraError(RuntimeError):
    """Raised when a camera stream cannot provide a complete JPEG frame."""


def build_stream_url(host: str, port: int = 8080, path: str = "/?action=stream") -> str:
    """Build the camera's HTTP MJPEG URL from a bare host, port, and path."""
    if not isinstance(host, str):
        raise ValueError("host must be a non-empty hostname or IP address")
    host = host.strip()
    if not host:
        raise ValueError("host must not be empty")
    if any(char in host for char in "/?#@") or any(char.isspace() for char in host):
        raise ValueError("host must be a hostname or IP address without a URL path")
    if not isinstance(port, int) or isinstance(port, bool) or not 1 <= port <= 65535:
        raise ValueError("port must be an integer between 1 and 65535")
    if not isinstance(path, str) or not path:
        raise ValueError("path must be a non-empty string")
    if any(ord(char) < 32 or ord(char) == 127 for char in path):
        raise ValueError("path must not contain control characters")
    path = path if path.startswith("/") else f"/{path}"

    # Bracket an unbracketed IPv6 address when placing it in a URL authority.
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    return f"http://{host}:{port}{path}"


def capture_first_frame(
    url: str,
    output_path: str | Path,
    timeout: float = 10.0,
    max_bytes: int = 10 * 1024 * 1024,
) -> Path:
    """Fetch an MJPEG response and save its first complete JPEG frame.

    The response is read with a strict total-byte limit. The output file is not
    opened until a complete SOI-to-EOI frame has been received.
    """
    if not isinstance(url, str) or not url.startswith(("http://", "https://")):
        raise ValueError("url must be an HTTP or HTTPS URL")
    if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or timeout <= 0:
        raise ValueError("timeout must be a positive number")
    if not isinstance(max_bytes, int) or isinstance(max_bytes, bool) or max_bytes <= 0:
        raise ValueError("max_bytes must be a positive integer")

    received = 0
    frame = bytearray()
    started = False
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            while received < max_bytes:
                chunk = response.read(min(4096, max_bytes - received + 1))
                if not chunk:
                    break
                received += len(chunk)
                if received > max_bytes:
                    raise CameraError(f"camera response exceeded max_bytes ({max_bytes})")

                for byte in chunk:
                    if not started:
                        if frame and frame[-1] == 0xFF and byte == 0xD8:
                            frame.append(byte)
                            started = True
                        else:
                            frame[:] = b"\xff" if byte == 0xFF else b""
                    else:
                        frame.append(byte)
                        if len(frame) >= 2 and frame[-2:] == b"\xff\xd9":
                            destination = Path(output_path)
                            try:
                                destination.write_bytes(frame)
                            except OSError as exc:
                                raise CameraError(f"could not write JPEG frame to {destination}: {exc}") from exc
                            return destination
    except CameraError:
        raise
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        raise CameraError(f"could not read camera stream: {exc}") from exc

    if not started:
        raise CameraError("camera stream ended before a JPEG frame started")
    raise CameraError("camera stream ended before the JPEG frame was complete")
