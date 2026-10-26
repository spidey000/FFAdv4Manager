"""End-to-end web G-code annotation -> real FlashForge GX binary.

No printer, network or browser is contacted. Node executes the actual frontend
annotation module, and Python executes the actual FFAdv4Manager converter.
"""
from __future__ import annotations

import base64
from io import BytesIO
import json
from pathlib import Path
import shutil
import struct
import subprocess

import pytest
from PIL import Image

from ffadv4manager.core.gcode_to_gx import GCODE_OFFSET, GX_MAGIC, convert_gcode_to_gx


ROOT = Path(__file__).resolve().parents[2]
NODE_CODE = r"""
import { readFileSync } from 'node:fs'
import { annotateAd4Gcode } from './frontend/src/ad4JobMetadata.js'

const { png } = JSON.parse(readFileSync(0, 'utf8'))
const rgba = new Uint8Array(80 * 60 * 4)
for (let i = 0; i < rgba.length; i += 4) {
  rgba[i] = 225; rgba[i + 1] = 70; rgba[i + 2] = 35; rgba[i + 3] = 255
}
const canvasFactory = () => ({
  getContext: () => ({
    createImageData: (w, h) => ({ data: new Uint8ClampedArray(w * h * 4) }),
    putImageData: () => {},
  }),
  toDataURL: () => 'data:image/png;base64,' + png,
})
const source = 'G28\nM104 S205\nM140 S55\nG1 X20 Y10 E1\n'
const result = annotateAd4Gcode(
  source,
  { time_estimate: 3723, filament_mm: 1234.5 },
  { layer_height: 0.2, wall_loops: 3, outer_wall_speed: 45,
    bed_temperature: 55, nozzle_temperature: 205 },
  rgba,
  canvasFactory,
)
process.stdout.write(result)
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js required for cross-stack test")
def test_browser_job_generates_genuine_gx_header_and_bmp(tmp_path):
    png_image = Image.new("RGBA", (80, 60), (225, 70, 35, 255))
    png_bytes = BytesIO()
    png_image.save(png_bytes, format="PNG")
    runner = subprocess.run(
        ["node", "--input-type=module", "--eval", NODE_CODE],
        input=json.dumps({"png": base64.b64encode(png_bytes.getvalue()).decode("ascii")}),
        text=True,
        encoding="utf-8",
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=15,
        check=True,
    )
    gcode = runner.stdout
    assert gcode.startswith("; estimated printing time (normal mode) = 1h 2m 3s")
    assert "; thumbnail begin 80x60 " in gcode
    assert "; filament used [mm] = 1234.50" in gcode
    assert "M104 S205" in gcode and "M140 S55" in gcode
    assert "G28\nM104 S205\nM140 S55\nG1 X20 Y10 E1\n" in gcode

    path = tmp_path / "browser-job.gcode"
    gx_path = tmp_path / "browser-job.gx"
    path.write_text(gcode, encoding="utf-8")
    convert_gcode_to_gx(path, gx_path)
    gx = gx_path.read_bytes()
    assert gx.startswith(GX_MAGIC)
    assert struct.unpack_from("<I", gx, 28)[0] == 3723
    assert struct.unpack_from("<I", gx, 32)[0] == 1234
    assert struct.unpack_from("<H", gx, 42)[0] == 200
    assert struct.unpack_from("<H", gx, 50)[0] == 55
    assert struct.unpack_from("<H", gx, 52)[0] == 205
    assert gx[58:60] == b"BM"
    bmp = Image.open(BytesIO(gx[58:GCODE_OFFSET])).convert("RGB")
    assert bmp.size == (80, 60)
    gray = bmp.getpixel((40, 30))
    assert 0 < gray[0] == gray[1] == gray[2] < 255
    assert gx[GCODE_OFFSET:] == gcode.encode("utf-8")
