import json

from ffadv4manager.core.layers import LayerIndex
from server import ad4_bridge as bridge


def test_status_estimates_layers_by_m114_not_m27(tmp_path, monkeypatch):
    monkeypatch.setattr(bridge, "LAYER_DIR", tmp_path)
    monkeypatch.setattr(bridge, "_printer_key", lambda: "printer-a")
    bridge.LAYER_TRACKERS.clear()
    bridge._save_index("model.gx", LayerIndex((0.2, 0.4, 0.6)))
    z_values = iter((0.2, 0.2, 0.4, 0.4, 0.6, 0.6))
    calls = []

    def command(*args, **_kwargs):
        calls.append(args)
        return json.dumps({"Z": next(z_values)})

    monkeypatch.setattr(bridge, "command", command)
    base = {"machine_status": "BUILDING_FROM_SD", "current_file": "/data/model.gx",
            "layer_current": 0, "layer_total": 0, "progress_percent": 98}
    results = [bridge._augment_status(dict(base)) for _ in range(6)]
    assert [entry["layer_estimated_current"] for entry in results] == [
        None, 1, 1, 2, 2, 3]
    assert all(entry["layer_estimated_total"] == 3 for entry in results)
    assert all(entry["layer_source"] == "estimated_z" for entry in results)
    assert calls == [("position", "--json")] * 6
    bridge._augment_status({**base, "machine_status": "READY"})
    assert not bridge.LAYER_TRACKERS


def test_status_does_not_guess_for_unindexed_file_or_other_printer(tmp_path, monkeypatch):
    monkeypatch.setattr(bridge, "LAYER_DIR", tmp_path)
    monkeypatch.setattr(bridge, "_printer_key", lambda: "printer-a")
    bridge._save_index("model.gx", LayerIndex((0.2,)))
    called = []

    def command(*args, **kwargs):
        called.append(args)
        return "{}"

    monkeypatch.setattr(bridge, "command", command)
    base = {"machine_status": "PRINTING", "current_file": "other.gx",
            "layer_current": 0, "layer_total": 0}
    result = bridge._augment_status(base)
    assert result["layer_estimated_current"] is None
    assert not called
    monkeypatch.setattr(bridge, "_printer_key", lambda: "printer-b")
    assert bridge._load_index("model.gx") is None


def test_real_nonzero_firmware_layer_takes_priority(monkeypatch):
    monkeypatch.setattr(bridge, "command",
                        lambda *a, **kw: (_ for _ in ()).throw(AssertionError("no M114")))
    original = {"machine_status": "PRINTING", "current_file": "model.gx",
                "layer_current": 3, "layer_total": 50}
    result = bridge._augment_status(original)
    assert result["layer_source"] == "firmware"
    assert result["layer_current"] == 3
