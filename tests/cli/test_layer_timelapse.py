"""No physical printer connection: synthetic M114/Z telemetry and camera frames."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from ffadv4manager import cli
from ffadv4manager.core.layers import LayerIndex


class FakeClient:
    def __init__(self, samples):
        self.samples = iter(samples)
        self.last = None

    def status(self):
        status, z = next(self.samples)
        self.last = z
        return SimpleNamespace(
            machine_status=status,
            is_printing=status == "BUILDING_FROM_SD",
            current_file="sample.gx",
            progress_percent=98,
        )

    def position(self):
        return {"Z": self.last}


def _args(tmp_path, index_file):
    return SimpleNamespace(
        interval=0.01, count=None, duration=None, directory=str(tmp_path / "frames"),
        camera_port=None, camera_path=None, on_layer=True, layer_file=str(index_file),
        layer_index=None, job_name="sample.gx",
    )


def test_timelapse_captures_stable_layer_transitions_only(tmp_path, monkeypatch):
    toolpath = tmp_path / "sample.gcode"
    toolpath.write_text(
        "G90\nM82\nG1 Z0.2\nG1 X2 E1\n"
        "G1 Z0.4\nG1 X4 E2\n"
        "G1 Z0.6\nG1 X6 E3\n"
    )
    assert LayerIndex.from_file(toolpath).heights == (0.2, 0.4, 0.6)
    args = _args(tmp_path, toolpath)
    readings = [
        ("BUILDING_FROM_SD", 0.2), ("BUILDING_FROM_SD", 0.2),
        ("BUILDING_FROM_SD", 1.0),  # Z-hop must not create a frame
        ("BUILDING_FROM_SD", 0.2),
        ("BUILDING_FROM_SD", 0.4), ("BUILDING_FROM_SD", 0.4),
        ("PAUSED", 0.4),
        ("BUILDING_FROM_SD", 0.6), ("BUILDING_FROM_SD", 0.6),
        ("READY", 0.6),
    ]
    captured = []
    finalized = []

    def camera(_url, destination):
        Path(destination).write_bytes(b"\xff\xd8\xff\xd9")
        captured.append(Path(destination).name)

    monkeypatch.setattr(cli, "capture_first_frame", camera)
    monkeypatch.setattr(cli, "_encode_timelapse", lambda folder: finalized.append(folder))
    monkeypatch.setattr(cli.shutil, "which", lambda _cmd: "/usr/bin/ffmpeg")
    monkeypatch.setattr(cli.time, "sleep", lambda _seconds: None)

    assert cli._capture_timelapse(FakeClient(readings), args, "printer", "http://printer/camera") == 0
    records = [json.loads(line) for line in
               (Path(args.directory) / "timelapse.jsonl").read_text().splitlines()]
    assert [record["layer_estimated"] for record in records] == [1, 2, 3]
    assert all(record["progress_percent"] == 98 for record in records)
    assert len(captured) == 3
    assert finalized == [Path(args.directory)]


def test_timelapse_fails_closed_when_active_job_changes(tmp_path, monkeypatch):
    file = tmp_path / "part.gcode"
    file.write_text("G1 Z0.2\nG1 X10 E1\n")
    args = _args(tmp_path, file)
    args.job_name = "another.gx"
    monkeypatch.setattr(cli.shutil, "which", lambda _cmd: "/usr/bin/ffmpeg")
    monkeypatch.setattr(cli, "_encode_timelapse", lambda _folder: None)
    client = FakeClient([("BUILDING_FROM_SD", 0.2)])
    with pytest.raises(RuntimeError, match="active printer file changed"):
        cli._capture_timelapse(client, args, "printer", "http://printer/camera")


def test_layer_timelapse_requires_an_index(tmp_path):
    args = SimpleNamespace(interval=1.0, count=None, duration=None, directory=str(tmp_path),
                           on_layer=True, layer_file=None, layer_index=None, job_name=None)
    with pytest.raises(ValueError, match="requires"):
        cli._capture_timelapse(None, args, "printer", "http://printer/camera")
