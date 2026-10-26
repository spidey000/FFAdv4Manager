"""Resolve the FFmpeg executable shipped in the Python environment."""
from imageio_ffmpeg import get_ffmpeg_exe


def ffmpeg_executable() -> str:
    """Return bundled FFmpeg (or provide an actionable installation error)."""
    try:
        return get_ffmpeg_exe()
    except (OSError, RuntimeError) as exc:
        raise RuntimeError(
            "FFmpeg is unavailable; install FFAdv4Manager with scripts/install.sh "
            "(supported Linux x86-64/aarch64)."
        ) from exc
