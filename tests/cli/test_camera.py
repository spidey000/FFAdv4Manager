from __future__ import annotations

import urllib.error

import pytest

from ffadv4manager.core.camera import CameraError, build_stream_url, capture_first_frame


@pytest.mark.parametrize(
    ("host", "port", "path", "expected"),
    [
        (" printer.local ", 8080, "/?action=stream", "http://printer.local:8080/?action=stream"),
        ("192.0.2.2", 81, "camera", "http://192.0.2.2:81/camera"),
        ("2001:db8::1", 8080, "stream", "http://[2001:db8::1]:8080/stream"),
    ],
)
def test_build_stream_url_normalizes_values(host, port, path, expected):
    assert build_stream_url(host, port, path) == expected


@pytest.mark.parametrize(
    ("host", "port", "path"),
    [
        ("  ", 8080, "/"),
        ("printer/path", 8080, "/"),
        ("printer", 0, "/"),
        ("printer", 65536, "/"),
        ("printer", True, "/"),
        ("printer", 8080, ""),
        ("printer", 8080, "/stream\n"),
    ],
)
def test_build_stream_url_rejects_invalid_values(host, port, path):
    with pytest.raises(ValueError):
        build_stream_url(host, port, path)


class MockResponse:
    def __init__(self, chunks):
        self.chunks = iter(chunks)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def read(self, size):
        return next(self.chunks, b"")


def test_capture_first_frame_handles_markers_split_across_reads(monkeypatch, tmp_path):
    response = MockResponse([b"boundary\xff", b"\xd8jpeg-data\xff", b"\xd9extra"])
    called = {}

    def fake_urlopen(url, timeout):
        called.update(url=url, timeout=timeout)
        return response

    monkeypatch.setattr("ffadv4manager.core.camera.urllib.request.urlopen", fake_urlopen)
    destination = tmp_path / "frame.jpg"
    result = capture_first_frame("http://camera/stream", destination, timeout=2, max_bytes=100)

    assert result == destination
    assert destination.read_bytes() == b"\xff\xd8jpeg-data\xff\xd9"
    assert called == {"url": "http://camera/stream", "timeout": 2}


@pytest.mark.parametrize(
    ("payload", "max_bytes", "message"),
    [
        (b"not a jpeg", 100, "before a JPEG frame started"),
        (b"\xff\xd8partial", 100, "before the JPEG frame was complete"),
        (b"\xff\xd8too large\xff\xd9", 5, "exceeded max_bytes"),
    ],
)
def test_capture_errors_do_not_write_partial_output(monkeypatch, tmp_path, payload, max_bytes, message):
    monkeypatch.setattr(
        "ffadv4manager.core.camera.urllib.request.urlopen", lambda *args, **kwargs: MockResponse([payload])
    )
    destination = tmp_path / "frame.jpg"
    destination.write_bytes(b"existing")

    with pytest.raises(CameraError, match=message):
        capture_first_frame("http://camera/stream", destination, max_bytes=max_bytes)
    assert destination.read_bytes() == b"existing"


def test_capture_wraps_http_errors(monkeypatch, tmp_path):
    def fail(*args, **kwargs):
        raise urllib.error.URLError("offline")

    monkeypatch.setattr("ffadv4manager.core.camera.urllib.request.urlopen", fail)
    with pytest.raises(CameraError, match="could not read camera stream"):
        capture_first_frame("http://camera/stream", tmp_path / "frame.jpg")


def test_capture_does_not_create_missing_output_parent(monkeypatch, tmp_path):
    frame = b"\xff\xd8jpeg\xff\xd9"
    monkeypatch.setattr(
        "ffadv4manager.core.camera.urllib.request.urlopen", lambda *args, **kwargs: MockResponse([frame])
    )
    destination = tmp_path / "missing" / "frame.jpg"
    with pytest.raises(CameraError, match="could not write JPEG frame"):
        capture_first_frame("http://camera/stream", destination)
    assert not destination.parent.exists()
