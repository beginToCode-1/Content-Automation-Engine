import json
import subprocess
from pathlib import Path
from typing import Literal

from content_engine.errors import RenderFailedError


def _run(args: list[str]) -> subprocess.CompletedProcess:
    result = subprocess.run(args, capture_output=True, text=True)
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
            "ffmpeg",
            "-y",
            "-ss",
            str(start_s),
            "-to",
            str(end_s),
            "-i",
            str(src),
            "-c:v",
            "libx264",
            "-c:a",
            "aac",
            str(dest),
        ]
    )


def to_vertical(src: Path, dest: Path, mode: Literal["crop", "pad_blur"] = "crop") -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if mode == "crop":
        vf = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920"
    else:
        vf = (
            "split[bg][fg];"
            "[bg]scale=1080:1920,boxblur=20:20[bg];"
            "[fg]scale=1080:1920:force_original_aspect_ratio=decrease[fg];"
            "[bg][fg]overlay=(W-w)/2:(H-h)/2"
        )
    _run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(src),
            "-vf",
            vf,
            "-c:v",
            "libx264",
            "-c:a",
            "copy",
            str(dest),
        ]
    )


def _escape_filter_path(path: Path) -> str:
    return str(path).replace("\\", "/").replace(":", "\\:")


def _escape_drawtext(text: str) -> str:
    return text.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def burn_captions(src: Path, srt_path: Path, dest: Path, title_text: str | None = None) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    filters = [f"subtitles='{_escape_filter_path(srt_path)}'"]
    if title_text:
        escaped_title = _escape_drawtext(title_text)
        filters.append(
            f"drawtext=text='{escaped_title}':fontsize=60:fontcolor=white:"
            "x=(w-text_w)/2:y=80:box=1:boxcolor=black@0.5:boxborderw=15"
        )
    _run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(src),
            "-vf",
            ",".join(filters),
            "-c:v",
            "libx264",
            "-c:a",
            "copy",
            str(dest),
        ]
    )
