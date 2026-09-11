import re
import tempfile
from pathlib import Path

import yt_dlp
from youtube_transcript_api import NoTranscriptFound, TranscriptsDisabled, YouTubeTranscriptApi

from content_engine.errors import NoTranscriptAvailableError
from content_engine.models import TranscriptLine

_VTT_TIMESTAMP_RE = re.compile(
    r"(\d{2}):(\d{2}):(\d{2})\.(\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})\.(\d{3})"
)


def _timestamp_to_seconds(h: str, m: str, s: str, ms: str) -> float:
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0


def _parse_vtt(vtt_text: str) -> list[TranscriptLine]:
    lines = vtt_text.splitlines()
    result: list[TranscriptLine] = []
    i = 0
    while i < len(lines):
        match = _VTT_TIMESTAMP_RE.search(lines[i])
        if match:
            start = _timestamp_to_seconds(*match.groups()[0:4])
            end = _timestamp_to_seconds(*match.groups()[4:8])
            i += 1
            text_parts = []
            while i < len(lines) and lines[i].strip():
                cleaned = re.sub(r"<[^>]+>", "", lines[i]).strip()
                if cleaned:
                    text_parts.append(cleaned)
                i += 1
            text = " ".join(text_parts)
            if text:
                result.append(TranscriptLine(text=text, start=start, duration=max(end - start, 0.0)))
        else:
            i += 1

    deduped: list[TranscriptLine] = []
    for line in result:
        if deduped and deduped[-1].text == line.text:
            continue
        deduped.append(line)
    return deduped


def _fetch_via_ytdlp(video_id: str) -> list[TranscriptLine]:
    url = f"https://www.youtube.com/watch?v={video_id}"
    with tempfile.TemporaryDirectory() as tmp_dir:
        outtmpl = str(Path(tmp_dir) / "subs.%(ext)s")
        ydl_opts = {
            "skip_download": True,
            "writeautomaticsub": True,
            "writesubtitles": True,
            "subtitleslangs": ["en"],
            "subtitlesformat": "vtt",
            "outtmpl": outtmpl,
            "quiet": True,
            "noprogress": True,
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
        except yt_dlp.utils.DownloadError as e:
            raise NoTranscriptAvailableError(f"yt-dlp subtitle fallback failed for {video_id}: {e}") from e

        vtt_files = list(Path(tmp_dir).glob("subs*.vtt"))
        if not vtt_files:
            raise NoTranscriptAvailableError(f"No subtitles found for video {video_id} via yt-dlp fallback")
        return _parse_vtt(vtt_files[0].read_text(encoding="utf-8"))


def get_transcript(video_id: str) -> list[TranscriptLine]:
    try:
        fetched = YouTubeTranscriptApi().fetch(video_id)
        return [TranscriptLine(text=s.text, start=s.start, duration=s.duration) for s in fetched]
    except (TranscriptsDisabled, NoTranscriptFound):
        pass  # expected: fall through to the yt-dlp fallback below

    lines = _fetch_via_ytdlp(video_id)
    if not lines:
        raise NoTranscriptAvailableError(f"No transcript available for video {video_id}")
    return lines
