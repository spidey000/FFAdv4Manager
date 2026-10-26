"""UDP discovery for FlashForge printers."""

from __future__ import annotations

import math
import socket
import time
from dataclasses import dataclass

DEFAULT_PORT = 8899
DISCOVERY_TARGETS = (
    ("225.0.0.9", 8899),
    ("225.0.0.9", 19000),
    ("255.255.255.255", 48899),
)

__all__ = [
    "DEFAULT_PORT",
    "DISCOVERY_TARGETS",
    "DiscoveredPrinter",
    "discover_printers",
    "parse_discovery_packet",
]


@dataclass(frozen=True)
class DiscoveredPrinter:
    """A printer found by UDP discovery."""

    name: str
    host: str
    port: int


def _validate_port(port: int, argument: str = "default_port") -> None:
    if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
        raise ValueError(f"{argument} must be an integer from 1 to 65535")


def _validate_timeout(timeout: float) -> None:
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)):
        raise ValueError("timeout must be a finite positive number of seconds")
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("timeout must be a finite positive number of seconds")


def parse_discovery_packet(
    packet: bytes,
    source_ip: str,
    default_port: int = DEFAULT_PORT,
) -> DiscoveredPrinter | None:
    """Parse one discovery datagram, returning ``None`` for undersized packets."""
    _validate_port(default_port)
    if not isinstance(packet, bytes):
        raise TypeError("packet must be bytes")
    if not isinstance(source_ip, str):
        raise TypeError("source_ip must be a string")
    if len(packet) < 32:
        return None

    name = packet[:128].split(b"\0", 1)[0].decode("utf-8", errors="replace")
    if not name:
        name = source_ip

    port = default_port
    if len(packet) >= 196:
        parsed_port = int.from_bytes(packet[0x84:0x86], byteorder="big", signed=False)
        if parsed_port:
            port = parsed_port

    return DiscoveredPrinter(name=name, host=source_ip, port=port)


def discover_printers(
    timeout: float = 3.0,
    default_port: int = DEFAULT_PORT,
) -> list[DiscoveredPrinter]:
    """Broadcast/multicast discovery and return unique printers sorted by name.

    The socket is bound implicitly by the first send and is always closed before
    this function returns or raises. A first response from each source IP wins.
    """
    _validate_timeout(timeout)
    _validate_port(default_port)

    found: dict[str, DiscoveredPrinter] = {}
    deadline = time.monotonic() + timeout
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1)
        for target in DISCOVERY_TARGETS:
            sock.sendto(b"discover", target)

        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            sock.settimeout(remaining)
            try:
                packet, source = sock.recvfrom(65535)
            except socket.timeout:
                break

            source_ip = source[0]
            if source_ip in found:
                continue
            printer = parse_discovery_packet(packet, source_ip, default_port)
            if printer is not None:
                found[source_ip] = printer

    return sorted(found.values(), key=lambda printer: printer.name)
