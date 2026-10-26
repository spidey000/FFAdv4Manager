"""Regression tests for metadata/thumbnail fields read on Adventurer 4."""
import base64
import io
import struct

import pytest
from PIL import Image

from ffadv4manager.core.gcode_to_gx import GCODE_OFFSET, convert_gcode_to_gx
from ffadv4manager.core.gx_converter.metadata import _parse_print_time, extract_metadata
from ffadv4manager.core.gx_converter.printers.registry import get_profile


@pytest.mark.parametrize(("text", "seconds"), [
    ("1h 2m 3s", 3723), ("2h 14m", 8040),
    ("00:03:12", 192), ("3:12", 192), ("3723", 3723),
    ("3723.4 seconds", 3723), ("unknown", 0),
])
def test_supported_time_formats(text, seconds):
    assert _parse_print_time(text) == seconds


def test_slicer_metadata_for_single_extruder_ad4():
    metadata = extract_metadata([
        ";TIME:3723\n",
        "; filament used [m] = 1.234\n",
        "; layer_height = 0.18\n",
        "; wall_loops = 3\n",
        "; machine_max_speed_x = 150\n",
        "; outer_wall_speed = 45\n",
        "; bed_temperature = 60\n",
        "; nozzle_temperature = 205\n",
    ], get_profile("adventurer4"))
    assert metadata.print_time == 3723
    assert metadata.filament_right_mm == 1234
    assert metadata.filament_left_mm == 0
    assert metadata.layer_height_um == 180
    assert metadata.perimeter_shells == 3
    assert metadata.print_speed == 45
    assert metadata.bed_temp == 60
    assert metadata.nozzle_right == 205
    assert metadata.nozzle_left == 0


def test_missing_time_is_unknown_not_one_second():
    metadata = extract_metadata(["G1 X12\n"], get_profile("adventurer4"))
    assert metadata.print_time == 0


def test_gx_encodes_duration_and_gray_model_thumbnail(tmp_path):
    picture = Image.new("RGBA", (80, 60), (220, 50, 30, 255))
    png = io.BytesIO()
    picture.save(png, format="PNG")
    encoded = base64.b64encode(png.getvalue()).decode("ascii")
    gcode = (
        "; estimated printing time (normal mode) = 1h 2m 3s\n"
        "; filament used [mm] = 1234.5\n"
        "; layer_height = 0.2\n"
        f"; thumbnail begin 80x60 {len(encoded)}\n"
        f"; {encoded}\n; thumbnail end\n"
        "G1 X1\n"
    )
    source = tmp_path / "part.gcode"
    dest = tmp_path / "part.gx"
    source.write_text(gcode)
    convert_gcode_to_gx(source, dest)
    payload = dest.read_bytes()
    assert struct.unpack_from("<I", payload, 28)[0] == 3723
    assert struct.unpack_from("<I", payload, 32)[0] == 1234
    assert payload[58:60] == b"BM"
    assert len(payload[58:GCODE_OFFSET]) == 14454
    bitmap = Image.open(io.BytesIO(payload[58:GCODE_OFFSET]))
    assert bitmap.size == (80, 60)
    r, g, b = bitmap.convert("RGB").getpixel((40, 30))
    assert 0 < r == g == b < 255
    assert payload[GCODE_OFFSET:] == gcode.encode()


def test_transparency_composites_to_black(tmp_path):
    picture = Image.new("RGBA", (80, 60), (255, 255, 255, 0))
    picture.putpixel((40, 30), (255, 255, 255, 255))
    png = io.BytesIO()
    picture.save(png, format="PNG")
    encoded = base64.b64encode(png.getvalue()).decode("ascii")
    source = tmp_path / "alpha.gcode"
    source.write_text(f"; thumbnail begin 80x60 {len(encoded)}\n; {encoded}\n; thumbnail end\nG1 X1\n")
    output = tmp_path / "alpha.gx"
    convert_gcode_to_gx(source, output)
    bitmap = Image.open(io.BytesIO(output.read_bytes()[58:GCODE_OFFSET])).convert("RGB")
    assert bitmap.getpixel((0, 0)) == (0, 0, 0)
    assert bitmap.getpixel((40, 30)) == (255, 255, 255)
