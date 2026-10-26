"""The installed virtualenv includes an FFmpeg binary and can produce MP4."""
from pathlib import Path
import subprocess

from PIL import Image

from ffadv4manager import cli
from ffadv4manager.core.video import ffmpeg_executable


def test_bundled_ffmpeg_launches_and_encodes_a_real_mp4(tmp_path):
    exe = ffmpeg_executable()
    assert subprocess.run([exe, "-version"], capture_output=True, timeout=10).returncode == 0
    for frame in range(3):
        Image.new("RGB", (64, 64), (20 * frame, 45, 90)).save(
            tmp_path / f"frame-20260101T000000-{frame:06d}.jpg", "JPEG"
        )
    cli._encode_timelapse(tmp_path)
    video = tmp_path / "timelapse.mp4"
    assert video.is_file() and video.stat().st_size > 100
    assert not list(tmp_path.glob("frame-*.jpg"))
