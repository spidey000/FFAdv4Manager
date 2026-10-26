from __future__ import annotations

import os
import re
import socket
import time
from pathlib import Path
from typing import Callable

from .models import PrinterStatus
from .parser import parse_file_list, parse_info, parse_position, parse_status

ProgressCallback = Callable[[int, int], None]
ResponseCallback = Callable[[str, str], None]
M661_TIMEOUT = 12.0
M661_IDLE_TIMEOUT = 0.3
M661_MAX_BYTES = 1_048_576
M662_MAX_BYTES = 16_777_216
UPLOAD_FLUSH_DELAY = 3.0
UPLOAD_ACK_TIMEOUT = 20.0
UPLOAD_PREAMBLE = ("M601 S1", "M115", "M650", "M119")


class ProtocolError(RuntimeError):
    """Raised when a printer rejects a command or omits its completion ack."""


class FlashForgeClient:
    """Small TCP client for legacy FlashForge printers on port 8899.

    The investigated printer identified as Adventurer 4 firmware v2.2.4 (M115);
    earlier project notes refer to a separate v2.3.3-3.33 compatibility test.
    Commands are sent as `~GCODE\r\n`. Upload follows the AD4 sender protocol:
    a separate acknowledged preamble, then `M28 <size> 0:/user/name`, payload,
    and `M29` on the upload socket.
    """

    def __init__(self, host: str, port: int = 8899, timeout: float = 8.0) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout

    def command(self, gcode: str, read_timeout: float | None = None) -> str:
        with self._connect(timeout=read_timeout or self.timeout) as sock:
            self._send_command(sock, gcode)
            return self._read_response(sock, read_timeout or self.timeout)

    def status(self) -> PrinterStatus:
        return parse_status(
            self.command("M119"),
            self.command("M105"),
            self.command("M27"),
        )

    def info(self) -> dict[str, str]:
        """Return key/value fields reported by M115; firmware fields vary by model."""
        return parse_info(self.command("M115"))

    def position(self) -> dict[str, float]:
        return parse_position(self.command("M114"))

    def preview_bmp(self, remote_name: str) -> bytes:
        """Fetch the M662 BMP preview, requiring its ACK and complete BMP payload.

        The printer's preview response is binary. The BMP's declared file size is
        used to delimit it; responses without a preceding standalone ACK, a valid
        BMP header, or the complete bounded payload fail closed.
        """
        remote_path = _validated_remote_path(remote_name)
        basename = remote_path.rsplit("/", 1)[-1]
        if any(char.isspace() or ord(char) < 32 or ord(char) == 127 or char == ";" for char in basename):
            raise ValueError("preview filename must not contain whitespace, controls, or semicolons")
        with self._connect(timeout=self.timeout) as sock:
            self._send_command(sock, f"M662 {remote_path}")
            return self._read_m662_bmp(sock, self.timeout, M662_MAX_BYTES)

    def rename(self, new_name: str) -> str:
        """Set the reported printer name using the observed M610 <name> form."""
        new_name = _validated_gcode_token(new_name, "printer name")
        response = self.command(f"M610 {new_name}")
        _require_ack("M610 rename", response, "M610")
        return response

    def set_fan(self, speed: int) -> str:
        if isinstance(speed, bool) or not isinstance(speed, int) or not 0 <= speed <= 255:
            raise ValueError("fan speed must be an integer from 0 to 255")
        response = self.command(f"M106 S{speed}")
        _require_ack("M106 fan control", response, "M106")
        return response

    def fan_off(self) -> str:
        response = self.command("M107")
        _require_ack("M107 fan control", response, "M107")
        return response

    def files_raw(self) -> str:
        with self._connect(timeout=M661_TIMEOUT) as sock:
            self._send_command(sock, "M661")
            return self._read_until_idle(
                sock,
                timeout=M661_TIMEOUT,
                idle_timeout=M661_IDLE_TIMEOUT,
                max_bytes=M661_MAX_BYTES,
            )

    def files(self) -> list[str]:
        return parse_file_list(self.files_raw())

    def upload(
        self,
        local_file: str | os.PathLike[str],
        remote_name: str | None = None,
        progress: ProgressCallback | None = None,
        chunk_size: int = 4096,
        response_callback: ResponseCallback | None = None,
    ) -> str:
        path = Path(local_file)
        if not path.is_file():
            raise FileNotFoundError(path)

        remote = path.name if remote_name is None else remote_name
        remote_path = _validated_remote_path(remote)
        total = path.stat().st_size
        if total == 0:
            raise ValueError(f"local file must not be empty: {path}")
        sent = 0

        self._send_upload_preamble(response_callback)
        upload_path = _upload_remote_path(remote)

        with self._connect(timeout=max(self.timeout, UPLOAD_ACK_TIMEOUT)) as sock:
            self._send_command(sock, f"M28 {total} {upload_path}")
            m28_response = self._read_until_exact_ok(sock, UPLOAD_ACK_TIMEOUT)
            _report_response(response_callback, "M28", m28_response)
            _require_exact_ok("M28 upload start", m28_response)

            with path.open("rb") as fh:
                while True:
                    chunk = fh.read(chunk_size)
                    if not chunk:
                        break
                    sock.sendall(chunk)
                    sent += len(chunk)
                    if progress:
                        progress(sent, total)

            if sent != total or path.stat().st_size != total:
                raise ValueError(
                    f"local file changed during upload: expected {total} bytes, sent {sent}"
                )

            time.sleep(UPLOAD_FLUSH_DELAY)
            self._send_command(sock, "M29")
            m29_response = self._read_until_exact_ok(sock, UPLOAD_ACK_TIMEOUT)
            _report_response(response_callback, "M29", m29_response)
            _require_exact_ok("M29 upload completion", m29_response)

        return upload_path

    def _send_upload_preamble(self, response_callback: ResponseCallback | None) -> None:
        with self._connect(timeout=max(self.timeout, UPLOAD_ACK_TIMEOUT)) as sock:
            for gcode in UPLOAD_PREAMBLE:
                self._send_command(sock, gcode)
                response = self._read_until_exact_ok(sock, UPLOAD_ACK_TIMEOUT)
                _report_response(response_callback, gcode.split()[0], response)
                _require_exact_ok(f"{gcode} preamble", response)

    def upload_and_confirm_listed(
        self,
        local_file: str | os.PathLike[str],
        remote_name: str | None = None,
        progress: ProgressCallback | None = None,
        response_callback: ResponseCallback | None = None,
    ) -> str:
        """Upload a file and confirm M661 lists its basename, without selecting it.

        Listing presence does not verify the printer-side byte size or content.
        """
        path = Path(local_file)
        if not path.is_file():
            raise FileNotFoundError(path)
        remote_path = self.upload(
            path, remote_name, progress=progress, response_callback=response_callback
        )

        listing = self.files_raw()
        _report_response(response_callback, "M661", listing)
        requested_basename = remote_path.rsplit("/", 1)[-1]
        listed_paths = re.findall(r"(?:/data/|0:/user/)[^:\x00\r\n]+", listing)
        listed_basenames = {item.strip().rsplit("/", 1)[-1] for item in listed_paths}
        if requested_basename not in listed_basenames:
            raise ProtocolError(
                f"upload completed, but M661 did not list {requested_basename!r}; "
                "file presence could not be confirmed"
            )
        return remote_path

    def print_file(
        self, remote_name: str, response_callback: ResponseCallback | None = None
    ) -> str:
        remote_path = _validated_remote_path(remote_name)
        # Proven working on AD4: select SD file then start/resume SD print.
        select_response = self.command(f"M23 {remote_path}")
        _report_response(response_callback, "M23", select_response)
        _require_ack("M23 file selection", select_response)
        start_response = self.command("M24")
        _report_response(response_callback, "M24", start_response)
        _require_ack("M24 print start", start_response)
        return select_response + "\n" + start_response

    def pause(self) -> str:
        return self.command("M25")

    def resume(self) -> str:
        return self.command("M24")

    def cancel(self) -> str:
        return self.command("M26")

    def _connect(self, timeout: float | None = None) -> socket.socket:
        sock = socket.create_connection((self.host, self.port), timeout=timeout or self.timeout)
        sock.settimeout(timeout or self.timeout)
        return sock

    @staticmethod
    def _send_command(sock: socket.socket, gcode: str) -> None:
        payload = f"~{gcode}\r\n".encode("utf-8")
        sock.sendall(payload)

    @staticmethod
    def _read_response(sock: socket.socket, timeout: float) -> str:
        sock.settimeout(timeout)
        chunks: list[bytes] = []
        end = time.time() + timeout
        while time.time() < end:
            try:
                data = sock.recv(8192)
            except socket.timeout:
                break
            if not data:
                break
            chunks.append(data)
            text = b"".join(chunks).decode("utf-8", errors="replace")
            if re.search(r"(?:^|\s)ok(?:\s|$)", text, flags=re.IGNORECASE):
                break
        return b"".join(chunks).decode("utf-8", errors="replace")

    @staticmethod
    def _read_available(sock: socket.socket, timeout: float) -> str:
        previous = sock.gettimeout()
        sock.settimeout(timeout)
        chunks: list[bytes] = []
        try:
            while True:
                try:
                    data = sock.recv(8192)
                except socket.timeout:
                    break
                if not data:
                    break
                chunks.append(data)
                if b"ok" in data:
                    break
        finally:
            sock.settimeout(previous)
        return b"".join(chunks).decode("utf-8", errors="replace")

    @staticmethod
    def _read_until_exact_ok(sock: socket.socket, timeout: float) -> str:
        sock.settimeout(timeout)
        deadline = time.monotonic() + timeout
        chunks: list[bytes] = []
        while time.monotonic() < deadline:
            sock.settimeout(max(0.001, deadline - time.monotonic()))
            try:
                data = sock.recv(8192)
            except socket.timeout:
                break
            if not data:
                break
            chunks.append(data)
            text = b"".join(chunks).decode("utf-8", errors="replace")
            if any(line.strip() == "ok" for line in text.splitlines()):
                return text
        return b"".join(chunks).decode("utf-8", errors="replace")

    @staticmethod
    def _read_until_idle(
        sock: socket.socket,
        timeout: float,
        idle_timeout: float,
        max_bytes: int,
    ) -> str:
        deadline = time.monotonic() + timeout
        chunks: list[bytes] = []
        total_bytes = 0
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            sock.settimeout(min(idle_timeout, remaining))
            try:
                data = sock.recv(min(8192, max_bytes - total_bytes + 1))
            except socket.timeout:
                break
            if not data:
                break
            total_bytes += len(data)
            if total_bytes > max_bytes:
                raise ProtocolError(f"printer M661 response exceeds {max_bytes} byte limit")
            chunks.append(data)
        return b"".join(chunks).decode("utf-8", errors="replace")

    @staticmethod
    def _read_m662_bmp(sock: socket.socket, timeout: float, max_bytes: int) -> bytes:
        deadline = time.monotonic() + timeout
        received = bytearray()
        bmp_start: int | None = None
        expected_size: int | None = None
        while time.monotonic() < deadline:
            sock.settimeout(max(0.001, deadline - time.monotonic()))
            try:
                chunk = sock.recv(8192)
            except socket.timeout as exc:
                raise ProtocolError("timed out reading complete M662 BMP response") from exc
            if not chunk:
                raise ProtocolError("connection closed before complete M662 BMP response")
            received.extend(chunk)
            if bmp_start is None:
                bmp_start = received.find(b"BM")
            if bmp_start is not None:
                ack = bytes(received[:bmp_start]).decode("ascii", errors="ignore")
                if not any(line.strip().lower() == "ok" for line in ack.splitlines()):
                    if len(received) > max_bytes + 8192:
                        raise ProtocolError("M662 response has no standalone ACK before BMP")
                    continue
                if len(received) >= bmp_start + 6 and expected_size is None:
                    expected_size = int.from_bytes(received[bmp_start + 2:bmp_start + 6], "little")
                    if expected_size < 14 or expected_size > max_bytes:
                        raise ProtocolError(f"invalid M662 BMP size: {expected_size}")
                if expected_size is not None and len(received) >= bmp_start + expected_size:
                    return bytes(received[bmp_start:bmp_start + expected_size])
            elif len(received) > max_bytes + 8192:
                raise ProtocolError(f"M662 response exceeds {max_bytes} byte limit")
        raise ProtocolError("timed out reading complete M662 BMP response")


def _validated_remote_path(remote_name: str) -> str:
    if not isinstance(remote_name, str) or not remote_name:
        raise ValueError("remote filename must not be empty")
    if any(ord(char) < 32 or ord(char) == 127 for char in remote_name):
        raise ValueError("remote filename must not contain ASCII control characters")

    if remote_name.startswith("/data/"):
        basename = remote_name[len("/data/"):]
        if not basename or "/" in basename or "\\" in basename:
            raise ValueError("remote path must be a filename in /data, not a nested path")
    elif remote_name.startswith("0:/user/"):
        basename = remote_name[len("0:/user/"):]
        if not basename or "/" in basename or "\\" in basename:
            raise ValueError("remote path must be a filename in 0:/user, not a nested path")
    else:
        basename = remote_name
        if "/" in basename or "\\" in basename:
            raise ValueError("remote filename must be a simple name or /data/<basename>")

    if basename in {".", ".."}:
        raise ValueError("remote filename must not be a traversal path")
    if remote_name.startswith("0:/user/"):
        return f"0:/user/{basename}"
    return f"/data/{basename}"


def _upload_remote_path(remote_name: str) -> str:
    basename = remote_name.rsplit("/", 1)[-1]
    return f"0:/user/{basename}"


def _validated_gcode_token(value: str, label: str) -> str:
    if (not isinstance(value, str) or not value or value in {".", ".."}
            or any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in value)
            or any(char in value for char in "\\/;")):
        raise ValueError(f"{label} must be a simple G-code token")
    return value


def _report_response(callback: ResponseCallback | None, command: str, response: str) -> None:
    if callback is not None:
        callback(command, response)


def _has_positive_ack(response: str) -> bool:
    return bool(re.search(r"(?:^|\s)ok(?:\s|$)", response, flags=re.IGNORECASE))


def _is_rejection(response: str) -> bool:
    return bool(
        re.search(
            r"\b(?:not\s+ok|error|failed|failure|reject(?:ed|ion)?|denied|cannot|unable|invalid|not found|busy|no sd)\b",
            response,
            flags=re.IGNORECASE,
        )
    )


def _response_detail(response: str) -> str:
    detail = " ".join(response.split())
    return detail or "no response"


def _require_ack(action: str, response: str, command: str | None = None) -> None:
    if _is_rejection(response):
        raise ProtocolError(f"printer rejected {action}: {_response_detail(response)}")
    has_command_receipt = command is not None and bool(
        re.search(rf"\bcmd\s+{re.escape(command)}\s+received\b", response, flags=re.IGNORECASE)
    )
    if not _has_positive_ack(response) and not has_command_receipt:
        raise ProtocolError(f"printer did not acknowledge {action}: {_response_detail(response)}")


def _require_exact_ok(action: str, response: str) -> None:
    if _is_rejection(response):
        raise ProtocolError(f"printer rejected {action}: {_response_detail(response)}")
    if not any(line.strip() == "ok" for line in response.splitlines()):
        raise ProtocolError(f"printer did not acknowledge {action} with standalone ok: {_response_detail(response)}")
