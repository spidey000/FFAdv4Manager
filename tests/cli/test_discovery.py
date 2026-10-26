import socket

import pytest

from ffadv4manager.core.discovery import (
    DEFAULT_PORT,
    DISCOVERY_TARGETS,
    DiscoveredPrinter,
    discover_printers,
    parse_discovery_packet,
)


def _packet(name="Printer", length=196, port=0):
    packet = bytearray(length)
    encoded = name.encode("utf-8")
    packet[: len(encoded)] = encoded
    if length >= 196:
        packet[0x84:0x86] = port.to_bytes(2, byteorder="big")
    return bytes(packet)


def test_parse_name_and_command_port():
    printer = parse_discovery_packet(_packet("AD4\N{SNOWMAN}", port=9021), "10.0.0.8")

    assert printer == DiscoveredPrinter("AD4\N{SNOWMAN}", "10.0.0.8", 9021)


def test_parse_falls_back_for_empty_or_invalid_utf8_name():
    empty_name = parse_discovery_packet(_packet("", port=8899), "10.0.0.9")
    invalid_utf8 = bytearray(_packet("Printer"))
    invalid_utf8[1] = 0xFF
    replaced = parse_discovery_packet(bytes(invalid_utf8), "10.0.0.10")

    assert empty_name == DiscoveredPrinter("10.0.0.9", "10.0.0.9", 8899)
    assert replaced is not None
    assert replaced.name.startswith("P\N{REPLACEMENT CHARACTER}")


def test_short_packets_are_ignored_and_short_or_zero_port_uses_default():
    assert parse_discovery_packet(b"x" * 31, "10.0.0.1") is None
    short = parse_discovery_packet(_packet("Short", length=195), "10.0.0.2")
    zero_port = parse_discovery_packet(_packet("Zero", port=0), "10.0.0.3")

    assert short == DiscoveredPrinter("Short", "10.0.0.2", DEFAULT_PORT)
    assert zero_port == DiscoveredPrinter("Zero", "10.0.0.3", DEFAULT_PORT)


class FakeSocket:
    def __init__(self, responses=()):
        self.responses = list(responses)
        self.options = []
        self.sent = []
        self.timeouts = []
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.closed = True

    def setsockopt(self, level, option, value):
        self.options.append((level, option, value))

    def sendto(self, data, target):
        self.sent.append((data, target))

    def settimeout(self, timeout):
        self.timeouts.append(timeout)

    def recvfrom(self, _size):
        if self.responses:
            return self.responses.pop(0)
        raise socket.timeout


def test_discovery_sends_targets_deduplicates_and_sorts(monkeypatch):
    fake = FakeSocket(
        [
            (_packet("Zulu"), ("10.0.0.2", 45000)),
            (_packet("Alpha"), ("10.0.0.1", 45000)),
            (_packet("Duplicate"), ("10.0.0.2", 45000)),
            (_packet("bad", length=31), ("10.0.0.3", 45000)),
        ]
    )
    monkeypatch.setattr(socket, "socket", lambda *args: fake)

    printers = discover_printers(timeout=1.5)

    assert printers == [
        DiscoveredPrinter("Alpha", "10.0.0.1", DEFAULT_PORT),
        DiscoveredPrinter("Zulu", "10.0.0.2", DEFAULT_PORT),
    ]
    assert fake.sent == [(b"discover", target) for target in DISCOVERY_TARGETS]
    assert (socket.SOL_SOCKET, socket.SO_BROADCAST, 1) in fake.options
    assert (socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1) in fake.options
    assert fake.timeouts and fake.timeouts[0] > 0
    assert fake.closed


def test_discovery_timeout_expires_and_closes_socket(monkeypatch):
    fake = FakeSocket()
    times = iter([10.0, 10.25])
    monkeypatch.setattr(socket, "socket", lambda *args: fake)
    monkeypatch.setattr("ffadv4manager.core.discovery.time.monotonic", lambda: next(times))

    assert discover_printers(timeout=2.0) == []
    assert fake.timeouts == [1.75]
    assert fake.closed


@pytest.mark.parametrize("timeout", [0, -1, float("inf"), float("nan"), True, "3"])
def test_discovery_rejects_invalid_timeout_before_opening_socket(monkeypatch, timeout):
    monkeypatch.setattr(
        socket,
        "socket",
        lambda *args: pytest.fail("invalid arguments must not open a socket"),
    )

    with pytest.raises(ValueError, match="timeout"):
        discover_printers(timeout=timeout)


@pytest.mark.parametrize("port", [0, -1, 65536, True, 8899.0])
def test_discovery_rejects_invalid_default_port(port):
    with pytest.raises(ValueError, match="default_port"):
        discover_printers(default_port=port)
