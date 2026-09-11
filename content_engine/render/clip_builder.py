from pathlib import Path

from content_engine.models import TranscriptSegment
from content_engine.render import ffmpeg_ops

# Filename convention every consumer relies on: the dashboard's /media route and
# the Instagram uploader both locate a run's finished clip via
# <work_dir>/<run_id>/CLIP_FILENAME rather than looking it up in the database,
# so this must stay in sync with the path build_clip() actually writes to.
CLIP_FILENAME = "clip_captioned.mp4"


def _format_srt_timestamp(seconds: float) -> str:
    total_ms = max(int(round(seconds * 1000)), 0)
    hours, rem = divmod(total_ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, ms = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


def _build_srt(segment: TranscriptSegment) -> str:
    entries = []
    for i, line in enumerate(segment.lines, start=1):
        start = line.start - segment.start_s
        end = start + line.duration
        entries.append(
            f"{i}\n{_format_srt_timestamp(start)} --> {_format_srt_timestamp(end)}\n{line.text}\n"
        )
    return "\n".join(entries)


def build_clip(
    source_video: Path,
    segment: TranscriptSegment,
    work_dir: Path,
    title_overlay: str | None = None,
) -> Path:
    work_dir.mkdir(parents=True, exist_ok=True)

    raw_clip = work_dir / "clip_raw.mp4"
    ffmpeg_ops.cut(source_video, segment.start_s, segment.end_s, raw_clip)

    vertical_clip = work_dir / "clip_vertical.mp4"
    ffmpeg_ops.to_vertical(raw_clip, vertical_clip)

    srt_path = work_dir / "segment.srt"
    srt_path.write_text(_build_srt(segment), encoding="utf-8")

    final_clip = work_dir / CLIP_FILENAME
    ffmpeg_ops.burn_captions(vertical_clip, srt_path, final_clip, title_text=title_overlay)

    return final_clip
