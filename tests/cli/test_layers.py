from pathlib import Path

import pytest

from ffadv4manager.core.layers import LayerIndex, LayerTracker


GCODE = """; START
G90
M82
G1 Z0.2
G1 X10 E1
G1 Z0.6 ; hop: no extrusion
G1 X20 ; travel
G1 Z0.2
G1 X30 E2
G1 Z0.4
G1 X40 E3
G1 E2.8 ; retract
G1 Z0.8 ; hop
G1 Z0.4
G1 X50 E4
G92 E0
M83
G1 Z0.6
G1 X60 E0.3
G91
G1 Z0.2
G1 X10 E0.3
"""


def test_index_tracks_extrusion_planes_not_travel_or_hops(tmp_path):
    file = tmp_path / "part.gcode"
    file.write_text(GCODE)
    assert LayerIndex.from_file(file).heights == (0.2, 0.4, 0.6, 0.8)


def test_gx_reads_toolpath_after_binary_header(tmp_path):
    gx = tmp_path / "part.gx"
    gx.write_bytes(b"xgcode 1.0\n\x00" + b"\x00" * (14512 - 12) + GCODE.encode())
    assert LayerIndex.from_file(gx).heights == (0.2, 0.4, 0.6, 0.8)


def test_debounces_hops_monotonic_and_missing_samples():
    index = LayerIndex((0.2, 0.4, 0.6, 0.8))
    tracker = LayerTracker(index)
    assert not tracker.observe(0.2)
    assert tracker.observe(0.2)
    assert tracker.layer == 1
    assert not tracker.observe(1.0)  # hop outside tolerance
    assert not tracker.observe(0.4)
    assert tracker.observe(0.4)
    assert tracker.layer == 2
    assert not tracker.observe(0.2)
    assert tracker.layer == 2
    assert not tracker.observe(0.8)
    assert tracker.observe(0.8)  # missed layer 3
    assert tracker.layer == 4


def test_rejects_unsupported_or_empty_index(tmp_path):
    file = tmp_path / "empty.gcode"
    file.write_text("G1 X10 Y10\n")
    with pytest.raises(ValueError, match="no printable"):
        LayerIndex.from_file(file)
    with pytest.raises(ValueError):
        LayerIndex(())


def test_json_roundtrip(tmp_path):
    index = LayerIndex((0.2, 0.35, 0.52))
    path = tmp_path / "index.json"
    import json
    path.write_text(json.dumps(index.as_dict()))
    assert LayerIndex.from_json_file(path) == index


def test_rejects_invalid_layer_json(tmp_path):
    path = tmp_path / "index.json"
    path.write_text('{"version":1,"heights":[0.2,0.2]}')
    with pytest.raises(ValueError):
        LayerIndex.from_json_file(path)
