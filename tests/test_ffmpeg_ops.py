from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from content_engine.errors import RenderFailedError
from content_engine.render import ffmpeg_ops


def _ok_result():
    result = MagicMock()
    result.returncode = 0
    result.stdout = "{}"
    result.stderr = ""
    return result


def test_cut_invokes_ffmpeg_with_expected_args(tmp_path):
    src = tmp_path / "src.mp4"
    dest = tmp_path / "out.mp4"
    with patch("subprocess.run", return_value=_ok_result()) as mock_run:
        ffmpeg_ops.cut(src, 10.0, 40.0, dest)

    args = mock_run.call_args[0][0]
    assert args[0] == "ffmpeg"
    assert "-ss" in args and "10.0" in args
    assert "-to" in args and "40.0" in args
    assert str(dest) == args[-1]


def test_to_vertical_crop_mode_uses_crop_filter(tmp_path):
    src = tmp_path / "src.mp4"
    dest = tmp_path / "out.mp4"
    with patch("subprocess.run", return_value=_ok_result()) as mock_run:
        ffmpeg_ops.to_vertical(src, dest, mode="crop")

    args = mock_run.call_args[0][0]
    vf_index = args.index("-vf")
    assert "crop=1080:1920" in args[vf_index + 1]


def test_to_vertical_defaults_to_full_frame_on_blurred_background(tmp_path):
    with patch("subprocess.run", return_value=_ok_result()) as mock_run:
        ffmpeg_ops.to_vertical(tmp_path / "src.mp4", tmp_path / "out.mp4")

    args = mock_run.call_args[0][0]
    vf = args[args.index("-vf") + 1]
    assert "force_original_aspect_ratio=decrease" in vf and "overlay" in vf


def test_burn_captions_includes_subtitles_and_title_filters(tmp_path):
    src = tmp_path / "src.mp4"
    srt = tmp_path / "seg.srt"
    dest = tmp_path / "out.mp4"
    with patch("subprocess.run", return_value=_ok_result()) as mock_run:
        ffmpeg_ops.burn_captions(src, srt, dest, title_text="My Title")

    args = mock_run.call_args[0][0]
    vf_index = args.index("-vf")
    filter_str = args[vf_index + 1]
    assert "subtitles=" in filter_str
    assert "drawtext=textfile=" in filter_str and "expansion=none" in filter_str
    assert (tmp_path / "title_0.txt").read_text(encoding="utf-8") == "My Title"


def test_burn_captions_wraps_long_titles_one_drawtext_per_line(tmp_path):
    with patch("subprocess.run", return_value=_ok_result()) as mock_run:
        ffmpeg_ops.burn_captions(
            tmp_path / "src.mp4", tmp_path / "seg.srt", tmp_path / "out.mp4",
            title_text="best productivity tips for remote software engineers",
        )
    filter_str = mock_run.call_args[0][0][mock_run.call_args[0][0].index("-vf") + 1]
    assert filter_str.count("drawtext=") == 3
    lines = [(tmp_path / f"title_{i}.txt").read_text(encoding="utf-8") for i in range(3)]
    assert " ".join(lines) == "best productivity tips for remote software engineers"
    assert all(len(line) <= 24 for line in lines)


def test_run_raises_render_failed_error_on_nonzero_exit():
    failing_result = MagicMock()
    failing_result.returncode = 1
    failing_result.stderr = "some ffmpeg error"
    with patch("subprocess.run", return_value=failing_result):
        with pytest.raises(RenderFailedError):
            ffmpeg_ops._run(["ffmpeg", "-bad-flag"])


def test_build_clip_stops_between_ffmpeg_passes_when_cancelled(tmp_path):
    import pytest

    from content_engine.errors import RunCancelledError
    from content_engine.models import TranscriptLine, TranscriptSegment
    from content_engine.render import clip_builder

    def cancel():
        raise RunCancelledError("Run cancelled by user")

    seg = TranscriptSegment(0, 10, "t", [TranscriptLine("t", 0, 10)], 1.0)
    with patch.object(clip_builder.ffmpeg_ops, "cut") as cut, patch.object(
        clip_builder.ffmpeg_ops, "to_vertical"
    ) as vertical:
        with pytest.raises(RunCancelledError):
            clip_builder.build_clip(tmp_path / "s.mp4", seg, tmp_path, check_cancelled=cancel)
    cut.assert_called_once()
    vertical.assert_not_called()
