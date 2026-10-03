import json
import subprocess
from pathlib import Path
from typing import Literal

from content_engine.errors import RenderFailedError


_TIMEOUT_S = 600

# Render's free plan has 512 MB RAM; ffmpeg's defaults (decoder + x264 threads per host
# core, 40-frame lookahead at 1080x1920) peaked at ~1.2 GB and got the process OOM-killed.
# Single-threaded decode/encode + veryfast measured ~270 MB.
# ponytail: fixed low-memory settings, make them configurable if a bigger box wants speed.
_FFMPEG = ["ffmpeg", "-y", "-threads", "1"]
_X264 = ["-c:v", "libx264", "-preset", "veryfast", "-threads", "1"]


def _run(args: list[str]) -> subprocess.CompletedProcess:
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=_TIMEOUT_S)
    except subprocess.TimeoutExpired as e:
        raise RenderFailedError(f"Command timed out after {_TIMEOUT_S}s: {' '.join(args)}") from e
    if result.returncode != 0:
        stderr_tail = "\n".join(result.stderr.splitlines()[-20:])
        raise RenderFailedError(f"Command failed: {' '.join(args)}\n{stderr_tail}")
    return result


def probe(path: Path) -> dict:
    result = _run(
        [
            "ffprobe",
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(path),
        ]
    )
    return json.loads(result.stdout)


def cut(src: Path, start_s: float, end_s: float, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    _run(
        [
            *_FFMPEG,
            "-ss",
            str(start_s),
            "-to",
            str(end_s),
            "-i",
            str(src),
            *_X264,
            "-c:a",
            "aac",
            str(dest),
        ]
    )


def to_vertical(src: Path, dest: Path, mode: Literal["crop", "pad_blur"] = "pad_blur") -> None:
    """pad_blur (default) keeps the whole source frame visible, centered on a blurred copy of
    itself; crop fills the 9:16 frame but cuts off ~70% of a 16:9 source's width."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if mode == "crop":
        vf = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920"
    else:
        # Background is blurred at 1/5 size then scaled up: same look, ~4x faster than
        # blurring at full 1080x1920 (matters on Render's fractional CPU).
        vf = (
            "split[bg][fg];"
            "[bg]scale=216:384:force_original_aspect_ratio=increase,crop=216:384,"
            "boxblur=6:2,scale=1080:1920[bg];"
            "[fg]scale=1080:1920:force_original_aspect_ratio=decrease[fg];"
            "[bg][fg]overlay=(W-w)/2:(H-h)/2"
        )
    _run(
        [
            *_FFMPEG,
            "-i",
            str(src),
            "-vf",
            vf,
            *_X264,
            "-c:a",
            "copy",
            str(dest),
        ]
    )


def _escape_filter_path(path: Path) -> str:
    return str(path).replace("\\", "/").replace(":", "\\:")


def _escape_drawtext(text: str) -> str:
    # "%" must be escaped too - ffmpeg's drawtext defaults to expansion=normal,
    # which otherwise interprets "%{...}" sequences in arbitrary (user/topic-
    # supplied) title text as expansion directives instead of literal text.
    return (
        text.replace("\\", "\\\\")
        .replace(":", "\\:")
        .replace("'", "\\'")
        .replace("%", "\\%")
    )


def burn_captions(src: Path, srt_path: Path, dest: Path, title_text: str | None = None) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    # MarginV is in libass's 288-line script space: 55 lifts captions to just under the
    # centered video, clear of the Shorts/Reels/TikTok buttons covering the bottom.
    filters = [f"subtitles='{_escape_filter_path(srt_path)}':force_style='MarginV=55'"]
    if title_text:
        escaped_title = _escape_drawtext(title_text)
        filters.append(
            f"drawtext=text='{escaped_title}':fontsize=60:fontcolor=white:"
            "x=(w-text_w)/2:y=80:box=1:boxcolor=black@0.5:boxborderw=15"
        )
    _run(
        [
            *_FFMPEG,
            "-i",
            str(src),
            "-vf",
            ",".join(filters),
            *_X264,
            "-c:a",
            "copy",
            str(dest),
        ]
    )
