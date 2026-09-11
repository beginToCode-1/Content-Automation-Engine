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
    assert "drawtext=" in filter_str
    assert "My Title" in filter_str


def test_run_raises_render_failed_error_on_nonzero_exit():
    failing_result = MagicMock()
    failing_result.returncode = 1
    failing_result.stderr = "some ffmpeg error"
    with patch("subprocess.run", return_value=failing_result):
        with pytest.raises(RenderFailedError):
            ffmpeg_ops._run(["ffmpeg", "-bad-flag"])
