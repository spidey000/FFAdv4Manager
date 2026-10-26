from ffadv4manager.core.parser import parse_file_list, parse_status


def test_parse_status():
    status = parse_status(
        "MachineStatus: READY\nMoveMode: READY\nCurrentFile: test.gcode\nok",
        "T0:14/0 B:-3/0\nok",
        "SD printing byte 9/100\nLayer: 0/0\nok",
    )
    assert status.machine_status == "READY"
    assert status.current_file == "test.gcode"
    assert status.nozzle_current == 14
    assert status.bed_current == -3
    assert status.progress_percent == 9.0


def test_parse_file_list():
    raw = "D��/data/test.gcode::��/data/Owlbear.gx::��"
    assert parse_file_list(raw) == ["/data/test.gcode", "/data/Owlbear.gx"]
