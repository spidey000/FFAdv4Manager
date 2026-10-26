"""Upload names must preserve the uploaded source and reflect real GX metadata."""
from __future__ import annotations

import struct

from ffadv4manager.core.gcode_to_gx import GX_MAGIC, convert_gcode_to_gx
from ffadv4manager.core.upload_naming import gx_remote_filename


def test_existing_converted_gx_gets_metadata_prefix_and_original_filename(tmp_path):
    source = tmp_path / "Mi Benchy.gcode"
    source.write_text(
        "; estimated printing time (normal mode) = 2h 17m 9s\n"
        "; filament used [mm] = 1234.5\nG28\n"
    )
    gx = tmp_path / "working-copy.gx"
    convert_gcode_to_gx(source, gx)
    assert gx_remote_filename(gx, source.name) == "02_17_1.23m_Mi_Benchy.gx"
    assert gx_remote_filename(gx, "working-copy.gx") == "02_17_1.23m_working-copy.gx"


def test_missing_metadata_is_explicitly_unknown(tmp_path):
    source = tmp_path / "Simple_Cube.gcode"
    source.write_text("G28\nG1 X10\n")
    gx = tmp_path / "part.gx"
    convert_gcode_to_gx(source, gx)
    assert gx_remote_filename(gx, source.name) == "--_--_unknownm_Simple_Cube.gx"


def test_prefixed_name_is_not_prefixed_twice(tmp_path):
    source = tmp_path / "part.gcode"
    source.write_text(";TIME:3600\n; filament used [mm] = 2450\nG28\n")
    gx = tmp_path / "part.gx"
    convert_gcode_to_gx(source, gx)
    assert gx_remote_filename(gx, "00_01_0.50m_Mi_Pieza.gx") == "01_00_2.45m_Mi_Pieza.gx"


def test_safe_ascii_and_truncation_for_printer_protocol(tmp_path):
    source = tmp_path / "part.gcode"
    source.write_text(";TIME:120\n; filament used [mm] = 120\nG28\n")
    gx = tmp_path / "part.gx"
    convert_gcode_to_gx(source, gx)
    name = gx_remote_filename(gx, "Café_" + "a" * 200 + ".gcode")
    assert name.startswith("00_02_0.12m_Cafe_")
    assert len(name) <= 100
    assert name.endswith(".gx")
    assert " " not in name


def test_does_not_read_non_gx_bytes_as_header(tmp_path):
    file = tmp_path / "not-gx.gx"
    file.write_bytes(b"NOT A GX" + bytes(32))
    import pytest
    with pytest.raises(ValueError):
        gx_remote_filename(file, "original.gx")
