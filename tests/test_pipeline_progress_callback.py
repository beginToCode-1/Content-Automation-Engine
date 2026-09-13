import os
from unittest.mock import MagicMock, patch

from content_engine.config import Settings
from content_engine.models import (
    ClipMetadata,
    DownloadResult,
    TranscriptLine,
    TranscriptSegment,
    UploadResult,
    VideoCandidate,
)
from content_engine.pipeline import run_pipeline


def _fake_settings(tmp_path):
    return Settings(
        gemini_api_key="fake-key",
        gemini_model="gemini-3.6-flash",
        youtube_api_key="fake-youtube-key",
        upload_privacy_status="private",
        log_level="INFO",
        work_dir=tmp_path,
        client_secret_path=tmp_path / "client_secret.json",
        token_path=tmp_path / "token.json",
        dashboard_host="127.0.0.1",
        dashboard_port=8000,
        dashboard_max_workers=2,
        database_url=os.environ["DATABASE_URL"],
        scheduler_poll_interval_s=30,
        instagram_access_token=None,
        instagram_business_account_id=None,
        instagram_graph_api_version="v21.0",
        instagram_public_video_base_url=None,
        tiktok_client_key=None,
        tiktok_client_secret=None,
        tiktok_token_path=tmp_path / "tiktok_token.json",
        batch_default_stagger_minutes=180,
        batch_max_videos=5,
        batch_max_clips_per_video=5,
        notifications_enabled=False,
        notify_desktop_enabled=True,
        notify_email_enabled=True,
        notify_email_to=None,
        smtp_host="smtp.gmail.com",
        smtp_port=587,
        smtp_username=None,
        smtp_password=None,
        smtp_from_address=None,
    )


def _patch_stages(tmp_path):
    video = VideoCandidate(
        video_id="abc123",
        title="A stoic video",
        description="desc",
        channel="chan",
        published_at="2026-01-01T00:00:00Z",
        duration_s=120.0,
    )
    clip_path = tmp_path / "clip_captioned.mp4"
    clip_path.write_bytes(b"fake video bytes")
    segment = TranscriptSegment(
        start_s=0.0, end_s=30.0, text="stoic text", lines=[TranscriptLine("stoic text", 0.0, 30.0)], score=0.9
    )
    metadata = ClipMetadata(title="Stoic Short #Shorts", description="desc", hashtags=["stoicism"])

    return patch.multiple(
        "content_engine.pipeline",
        build_search_client=MagicMock(return_value=MagicMock()),
        search_videos=MagicMock(return_value=[video]),
        select_best=MagicMock(return_value=video),
        download_video=MagicMock(
            return_value=DownloadResult(video_path=tmp_path / "source.mp4", info_json_path=tmp_path / "i.json", duration_s=120.0)
        ),
        get_transcript=MagicMock(return_value=[TranscriptLine("stoic text", 0.0, 30.0)]),
        select_best_segment=MagicMock(return_value=segment),
        build_clip=MagicMock(return_value=clip_path),
        generate_metadata=MagicMock(return_value=metadata),
    )


def test_on_progress_fires_for_each_stage(tmp_path):
    settings = _fake_settings(tmp_path)
    events = []

    with _patch_stages(tmp_path):
        result = run_pipeline(
            "stoic philosophy", settings, dry_run=True, on_progress=lambda stage, msg: events.append(stage)
        )

    assert result.metadata.title == "Stoic Short #Shorts"
    fired_stages = set(events)
    assert {"search", "download", "transcript", "segment", "render", "metadata", "upload"}.issubset(fired_stages)


def test_on_progress_exception_does_not_abort_pipeline(tmp_path):
    settings = _fake_settings(tmp_path)

    def bad_callback(stage, msg):
        raise RuntimeError("callback exploded")

    with _patch_stages(tmp_path):
        result = run_pipeline("stoic philosophy", settings, dry_run=True, on_progress=bad_callback)

    assert result.run_id
    assert result.upload is None
