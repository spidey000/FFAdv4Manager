import base64
import io
import struct

import pytest
from PIL import Image

from ffadv4manager import cli
from ffadv4manager.core.gcode_to_gx import (
    BMP_SIZE,
    GCODE_OFFSET,
    GX_MAGIC,
    HEADER_SIZE,
    convert_gcode_to_gx,
    upload_file,
    validate_gx,
)


def _source_gcode() -> bytes:
    image = Image.new("RGB", (4, 3), (220, 50, 30))
    encoded = io.BytesIO()
    image.save(encoded, format="PNG")
    b64 = base64.b64encode(encoded.getvalue()).decode("ascii")
    return (
        "; estimated printing time (normal mode) = 1h 2m 3s\n"
        "; filament used [mm] = 123.4\n"
        "; layer_height = 0.2\n"
        "; nozzle_temperature = 220\n"
        "; first_layer_bed_temperature = 60\n"
        "; thumbnail begin 4x3 123\n"
        f"; {b64}\n"
        "; thumbnail end\n"
        "G1 X1\n"
    ).encode()


def test_in_process_conversion_preserves_input_and_generates_ad4_gx(monkeypatch, tmp_path):
    monkeypatch.setenv("PATH", "")
    source = tmp_path / "model.gcode"
    original = _source_gcode()
    source.write_bytes(original)
    output = tmp_path / "model.gx"

    convert_gcode_to_gx(source, output)

    data = output.read_bytes()
    assert source.read_bytes() == original
    assert data[:len(GX_MAGIC)] == GX_MAGIC
    assert len(data[:HEADER_SIZE]) == HEADER_SIZE
    assert struct.unpack_from("<4i", data, 12) == (0, 58, GCODE_OFFSET, GCODE_OFFSET)
    assert len(data[58:GCODE_OFFSET]) == BMP_SIZE
    assert data[58:60] == b"BM"
    assert data[GCODE_OFFSET:] == original
    # AD4 profile is single-extruder; metadata values are encoded in GX header.
    assert struct.unpack_from("<iiih", data, 28) == (3723, 123, 0, 0)
    assert struct.unpack_from("<8h", data, 42)[0] == 200
    assert struct.unpack_from("<8h", data, 42)[4:7] == (60, 220, 0)


def test_upload_file_detects_gx_magic_and_rejects_unknown(tmp_path):
    gx = tmp_path / "weird.bin"
    gx.write_bytes(GX_MAGIC + bytes(GCODE_OFFSET - len(GX_MAGIC)))
    with upload_file(gx) as (path, remote):
        assert path == gx and remote == "weird.gx"
    with pytest.raises(ValueError, match="cannot automatically convert"):
        with upload_file(tmp_path / "arbitrary.bin"):
            pass


def test_convert_cli_local_output_and_upload_conversion(monkeypatch, tmp_path, capsys):
    source = tmp_path / "part.gco"
    original = _source_gcode()
    source.write_bytes(original)
    output = tmp_path / "part.gx"
    assert cli.main(["convert", str(source), "--output", str(output)]) == 0
    assert output.read_bytes()[GCODE_OFFSET:] == original
    assert str(output) in capsys.readouterr().out

    class Client:
        def __init__(self, *_args, **_kwargs):
            pass

        def status(self):
            return type("Status", (), {"is_printing": False})()

        def upload_and_confirm_listed(self, path, remote_name, **_kwargs):
            assert path.read_bytes()[GCODE_OFFSET:] == original
            assert remote_name == "part.gx"
            return "0:/user/part.gx"

    monkeypatch.setattr(cli, "_progress", lambda *_: None)
    monkeypatch.setattr(cli, "FlashForgeClient", Client)
    assert cli.main(["--host", "printer", "upload", str(source)]) == 0
    assert source.read_bytes() == original


@pytest.mark.parametrize(
    ("field_values", "message"),
    [
        ((0, 57, GCODE_OFFSET, GCODE_OFFSET), "BMP offset"),
        ((0, 58, GCODE_OFFSET - 1, GCODE_OFFSET), "G-code offset"),
        ((0, 58, GCODE_OFFSET, GCODE_OFFSET + 1), "G-code offset"),
    ],
)
def test_validate_rejects_bad_header_offsets(tmp_path, field_values, message):
    payload = bytearray(GCODE_OFFSET + 1)
    payload[:len(GX_MAGIC)] = GX_MAGIC
    struct.pack_into("<4i", payload, 12, *field_values)
    payload[58:60] = b"BM"
    path = tmp_path / "invalid.gx"
    path.write_bytes(payload)
    with pytest.raises(ValueError, match=message):
        validate_gx(path)


def test_conversion_rejects_empty_source_without_output(tmp_path):
    source = tmp_path / "empty.gcode"
    source.write_bytes(b"")
    output = tmp_path / "empty.gx"
    with pytest.raises(ValueError, match="Empty or unreadable"):
        convert_gcode_to_gx(source, output)
    assert not output.exists()


def test_conversion_preserves_source_and_documents_upstream_text_encoding(tmp_path):
    source = tmp_path / "unicode.gcode"
    original = "G1 X1 ; café ☃\n".encode("utf-8")
    source.write_bytes(original)
    output = tmp_path / "unicode.gx"

    convert_gcode_to_gx(source, output)

    assert source.read_bytes() == original
    assert output.read_bytes()[GCODE_OFFSET:] == b"G1 X1 ; caf\xe9 ?\n"
