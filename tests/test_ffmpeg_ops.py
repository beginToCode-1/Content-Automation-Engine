import sys
import time
from unittest.mock import patch

import pytest

from content_engine.errors import RenderFailedError, RunCancelledError
from content_engine.render import ffmpeg_ops


def _render_args(tmp_path, **kwargs):
    with patch.object(ffmpeg_ops, "_run") as run:
        ffmpeg_ops.render_clip(tmp_path / "src.mp4", 10.0, 40.0, tmp_path / "seg.srt", tmp_path / "out.mp4", **kwargs)
    return run.call_args[0][0]


def test_render_clip_is_one_ffmpeg_pass_that_cuts_frames_and_captions(tmp_path):
    args = _render_args(tmp_path)
    assert args[0] == "ffmpeg"
    assert args[args.index("-ss") + 1] == "10.0" and args[args.index("-to") + 1] == "40.0"
    assert args.index("-ss") < args.index("-i")  # input seeking: SRT times start at 0
    vf = args[args.index("-vf") + 1]
    assert "force_original_aspect_ratio=decrease" in vf and "overlay" in vf  # full frame by default
    assert "subtitles=" in vf
    assert args[-1] == str(tmp_path / "out.mp4")


def test_render_clip_crop_mode_uses_crop_filter(tmp_path):
    vf = (args := _render_args(tmp_path, mode="crop"))[args.index("-vf") + 1]
    assert "crop=1080:1920" in vf


def test_render_clip_title_is_read_from_files_with_expansion_off(tmp_path):
    vf = (args := _render_args(tmp_path, title_text="My Title"))[args.index("-vf") + 1]
    assert "drawtext=textfile=" in vf and "expansion=none" in vf
    assert (tmp_path / "title_0.txt").read_text(encoding="utf-8") == "My Title"


def test_render_clip_wraps_long_titles_one_drawtext_per_line(tmp_path):
    title = "best productivity tips for remote software engineers"
    vf = (args := _render_args(tmp_path, title_text=title))[args.index("-vf") + 1]
    assert vf.count("drawtext=") == 3
    lines = [(tmp_path / f"title_{i}.txt").read_text(encoding="utf-8") for i in range(3)]
    assert " ".join(lines) == title
    assert all(len(line) <= 24 for line in lines)


def test_run_raises_render_failed_error_on_nonzero_exit():
    with pytest.raises(RenderFailedError, match="boom"):
        ffmpeg_ops._run([sys.executable, "-c", "import sys; sys.stderr.write('boom'); sys.exit(1)"])


def test_run_kills_the_process_as_soon_as_cancelled():
    def cancel():
        raise RunCancelledError("Run cancelled by user")

    started = time.monotonic()
    with pytest.raises(RunCancelledError):
        ffmpeg_ops._run([sys.executable, "-c", "import time; time.sleep(30)"], should_stop=cancel)
    assert time.monotonic() - started < 5


def test_build_clip_passes_cancel_check_to_ffmpeg(tmp_path):
    from content_engine.models import TranscriptLine, TranscriptSegment
    from content_engine.render import clip_builder

    def cancel():
        raise RunCancelledError("Run cancelled by user")

    seg = TranscriptSegment(0, 10, "t", [TranscriptLine("t", 0, 10)], 1.0)
    with patch.object(clip_builder.ffmpeg_ops, "render_clip") as render:
        clip_builder.build_clip(tmp_path / "s.mp4", seg, tmp_path, check_cancelled=cancel)
    assert render.call_args.kwargs["should_stop"] is cancel
