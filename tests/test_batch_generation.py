from unittest.mock import MagicMock, patch

from content_engine.models import (
    ClipMetadata,
    DownloadResult,
    TranscriptLine,
    TranscriptSegment,
    VideoCandidate,
)
from content_engine.pipeline import generate_clips_for_topic
from tests.test_pipeline_progress_callback import _fake_settings


def _video(video_id):
    return VideoCandidate(
        video_id=video_id, title=f"video {video_id}", description="", channel="c", published_at="", duration_s=200
    )


def _segment(start_s):
    return TranscriptSegment(
        start_s=start_s, end_s=start_s + 30, text="stoic text", lines=[TranscriptLine("stoic text", start_s, 30)], score=0.9
    )


def test_generate_clips_for_topic_produces_videos_times_clips(tmp_path):
    settings = _fake_settings(tmp_path)
    videos = [_video("v1"), _video("v2")]
    segments = [_segment(0), _segment(60), _segment(120)]

    ready_clips = []

    with patch.multiple(
        "content_engine.pipeline",
        build_search_client=MagicMock(return_value=MagicMock()),
        search_videos=MagicMock(return_value=videos),
        select_top=MagicMock(return_value=videos),
        download_video=MagicMock(
            return_value=DownloadResult(video_path=tmp_path / "source.mp4", info_json_path=tmp_path / "i.json", duration_s=200)
        ),
        get_transcript=MagicMock(return_value=[TranscriptLine("stoic text", 0, 200)]),
        select_top_segments=MagicMock(return_value=segments),
        build_clip=MagicMock(return_value=tmp_path / "clip.mp4"),
        generate_metadata=MagicMock(return_value=ClipMetadata(title="t", description="d")),
    ):
        clips = generate_clips_for_topic(
            "stoic philosophy",
            settings,
            batch_id="batch1",
            videos_count=2,
            clips_per_video=3,
            on_clip_ready=lambda clip, v, c: ready_clips.append((v, c)),
        )

    assert len(clips) == 6  # 2 videos x 3 clips
    assert len(ready_clips) == 6
    assert ready_clips[0] == (1, 1)
    assert ready_clips[3] == (2, 1)

    video_ranks = {c.video_rank for c in clips}
    assert video_ranks == {1, 2}
    for video_rank in (1, 2):
        clip_ranks = sorted(c.clip_rank for c in clips if c.video_rank == video_rank)
        assert clip_ranks == [1, 2, 3]


def test_generate_clips_for_topic_on_clip_ready_failure_does_not_abort(tmp_path):
    settings = _fake_settings(tmp_path)
    videos = [_video("v1")]
    segments = [_segment(0)]

    def bad_callback(clip, v, c):
        raise RuntimeError("boom")

    with patch.multiple(
        "content_engine.pipeline",
        build_search_client=MagicMock(return_value=MagicMock()),
        search_videos=MagicMock(return_value=videos),
        select_top=MagicMock(return_value=videos),
        download_video=MagicMock(
            return_value=DownloadResult(video_path=tmp_path / "source.mp4", info_json_path=tmp_path / "i.json", duration_s=200)
        ),
        get_transcript=MagicMock(return_value=[TranscriptLine("stoic text", 0, 200)]),
        select_top_segments=MagicMock(return_value=segments),
        build_clip=MagicMock(return_value=tmp_path / "clip.mp4"),
        generate_metadata=MagicMock(return_value=ClipMetadata(title="t", description="d")),
    ):
        clips = generate_clips_for_topic(
            "stoic philosophy", settings, batch_id="batch1", videos_count=1, clips_per_video=1,
            on_clip_ready=bad_callback,
        )

    assert len(clips) == 1


def test_one_failing_video_does_not_stop_the_rest_of_the_batch(tmp_path):
    from content_engine.errors import NoTranscriptAvailableError

    settings = _fake_settings(tmp_path)
    videos = [_video("v1"), _video("v2")]

    def transcript(video_id):
        if video_id == "v1":
            raise NoTranscriptAvailableError("no captions")
        return [TranscriptLine("stoic text", 0, 200)]

    with patch.multiple(
        "content_engine.pipeline",
        build_search_client=MagicMock(return_value=MagicMock()),
        search_videos=MagicMock(return_value=videos),
        select_top=MagicMock(return_value=videos),
        download_video=MagicMock(
            return_value=DownloadResult(video_path=tmp_path / "source.mp4", info_json_path=tmp_path / "i.json", duration_s=200)
        ),
        get_transcript=MagicMock(side_effect=transcript),
        select_top_segments=MagicMock(return_value=[_segment(0)]),
        build_clip=MagicMock(return_value=tmp_path / "clip.mp4"),
        generate_metadata=MagicMock(return_value=ClipMetadata(title="t", description="d")),
    ):
        clips = generate_clips_for_topic("stoic", settings, batch_id="b1", videos_count=2, clips_per_video=1)

    assert [c.video_rank for c in clips] == [2]
    assert not (settings.work_dir / "b1" / "video1_source").exists()  # source removed


def test_batch_raises_when_every_video_fails(tmp_path):
    import pytest

    from content_engine.errors import NoTranscriptAvailableError

    with patch.multiple(
        "content_engine.pipeline",
        build_search_client=MagicMock(return_value=MagicMock()),
        search_videos=MagicMock(return_value=[_video("v1")]),
        select_top=MagicMock(return_value=[_video("v1")]),
        download_video=MagicMock(side_effect=NoTranscriptAvailableError("nope")),
    ):
        with pytest.raises(NoTranscriptAvailableError):
            generate_clips_for_topic("stoic", _fake_settings(tmp_path), batch_id="b1", videos_count=1, clips_per_video=1)
