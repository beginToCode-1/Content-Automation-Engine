import json
import subprocess
import textwrap
import time
from pathlib import Path
from typing import Callable, Literal

from content_engine.errors import RenderFailedError


_TIMEOUT_S = 1200  # one pass now does all the work; ~4 min for a 60 s clip on Render

# Render's free plan has 512 MB RAM; ffmpeg's defaults (decoder + x264 threads per host
# core, 40-frame lookahead at 1080x1920) peaked at ~1.2 GB and got the process OOM-killed.
# Single-threaded decode/encode + veryfast measured ~270 MB.
# ponytail: fixed low-memory settings, make them configurable if a bigger box wants speed.
_FFMPEG = ["ffmpeg", "-y", "-threads", "1"]
_X264 = ["-c:v", "libx264", "-preset", "veryfast", "-threads", "1"]

_TITLE_WRAP_CHARS = 24  # fits a 1080-wide frame at fontsize 60
_TITLE_MAX_LINES = 3
_TITLE_LINE_HEIGHT = 90


def _run(args: list[str], should_stop: Callable[[], None] | None = None) -> subprocess.CompletedProcess:
    """Runs a command. `should_stop` (raises to cancel) is polled every half
    second, so a cancelled run stops ffmpeg mid-render instead of waiting."""
    proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    deadline = time.monotonic() + _TIMEOUT_S
    try:
        while True:
            try:
                stdout, stderr = proc.communicate(timeout=0.5)
                break
            except subprocess.TimeoutExpired:
                if time.monotonic() > deadline:
                    raise RenderFailedError(f"Command timed out after {_TIMEOUT_S}s: {' '.join(args)}")
                if should_stop:
                    should_stop()
    except BaseException:
        proc.kill()
        proc.communicate()
        raise
    if proc.returncode != 0:
        stderr_tail = "\n".join(stderr.splitlines()[-20:])
        raise RenderFailedError(f"Command failed: {' '.join(args)}\n{stderr_tail}")
    return subprocess.CompletedProcess(args, proc.returncode, stdout, stderr)


def probe(path: Path) -> dict:
    result = _run(["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", str(path)])
    return json.loads(result.stdout)


def _escape_filter_path(path: Path) -> str:
    return str(path).replace("\\", "/").replace(":", "\\:")


def _vertical_filter(mode: Literal["crop", "pad_blur"]) -> str:
    """pad_blur (default) keeps the whole source frame visible, centered on a blurred copy of
    itself; crop fills the 9:16 frame but cuts off ~70% of a 16:9 source's width."""
    if mode == "crop":
        return "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920"
    # Background is blurred at 1/5 size then scaled up: same look, ~4x faster than
    # blurring at full 1080x1920 (matters on Render's fractional CPU).
    return (
        "split[bg][fg];"
        "[bg]scale=216:384:force_original_aspect_ratio=increase,crop=216:384,"
        "boxblur=6:2,scale=1080:1920[bg];"
        "[fg]scale=1080:1920:force_original_aspect_ratio=decrease[fg];"
        "[bg][fg]overlay=(W-w)/2:(H-h)/2"
    )


def _title_filters(title_text: str, work_dir: Path) -> list[str]:
    # The title comes from the user's topic. It is read from a file with
    # expansion off instead of being escaped into the filter string, so
    # quotes, commas, colons and % can't break the filter or vanish.
    # Long titles wrap; each line is drawn separately so every line is centered.
    filters = []
    lines = textwrap.wrap(" ".join(title_text.split()), _TITLE_WRAP_CHARS)[:_TITLE_MAX_LINES]
    for i, line in enumerate(lines):
        line_file = work_dir / f"title_{i}.txt"
        line_file.write_text(line, encoding="utf-8")
        filters.append(
            f"drawtext=textfile='{_escape_filter_path(line_file)}':expansion=none:"
            f"fontsize=60:fontcolor=white:x=(w-text_w)/2:y={80 + i * _TITLE_LINE_HEIGHT}:"
            "box=1:boxcolor=black@0.5:boxborderw=15"
        )
    return filters


def render_clip(
    src: Path,
    start_s: float,
    end_s: float,
    srt_path: Path,
    dest: Path,
    title_text: str | None = None,
    mode: Literal["crop", "pad_blur"] = "pad_blur",
    should_stop: Callable[[], None] | None = None,
) -> None:
    """Cut, vertical framing, burned captions and title in ONE ffmpeg pass.
    Three separate passes decoded and x264-encoded the video three times;
    one pass is about 2.5x faster for the same output."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    # Input seeking (-ss/-to before -i) restarts timestamps at 0, which is what
    # the SRT (written relative to the segment start) expects.
    # MarginV is in libass's 288-line script space: 55 lifts captions to just under the
    # centered video, clear of the Shorts/Reels/TikTok buttons covering the bottom.
    filters = [_vertical_filter(mode), f"subtitles='{_escape_filter_path(srt_path)}':force_style='MarginV=55'"]
    if title_text:
        filters += _title_filters(title_text, dest.parent)
    _run(
        [
            *_FFMPEG,
            "-ss", str(start_s),
            "-to", str(end_s),
            "-i", str(src),
            "-vf", ",".join(filters),
            *_X264,
            "-c:a", "aac",
            str(dest),
        ],
        should_stop=should_stop,
    )
