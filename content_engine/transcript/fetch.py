import json
import tempfile
from pathlib import Path

import yt_dlp
from youtube_transcript_api import CouldNotRetrieveTranscript, YouTubeTranscriptApi

from content_engine.download.yt_dlp_downloader import add_cookies
from content_engine.errors import NoTranscriptAvailableError
from content_engine.models import TranscriptLine

def _parse_json3(data: dict) -> list[TranscriptLine]:
    """Parses YouTube's json3 captions. Unlike VTT, json3 lists each phrase once:
    auto-caption VTT repeats every line 2-3 times (rolling display) and adds
    10 ms "snapshot" cues, which duplicated text in captions, scoring and Gemini.
    Events flagged aAppend are just line breaks in the rolling display."""
    phrases = []
    for event in data.get("events", []):
        if event.get("aAppend") or not event.get("segs"):
            continue
        text = " ".join("".join(seg.get("utf8", "") for seg in event["segs"]).split())
        if text:
            phrases.append((event.get("tStartMs", 0) / 1000.0, event.get("dDurationMs", 0) / 1000.0, text))

    lines: list[TranscriptLine] = []
    for i, (start, duration, text) in enumerate(phrases):
        # Auto-caption events stay on screen until the next-but-one starts; end
        # each phrase when the next begins so caption timings don't overlap.
        if i + 1 < len(phrases):
            duration = min(duration, max(phrases[i + 1][0] - start, 0.0))
        lines.append(TranscriptLine(text=text, start=start, duration=duration))
    return lines


def _fetch_via_ytdlp(video_id: str) -> list[TranscriptLine]:
    url = f"https://www.youtube.com/watch?v={video_id}"
    with tempfile.TemporaryDirectory() as tmp_dir:
        outtmpl = str(Path(tmp_dir) / "subs.%(ext)s")
        ydl_opts = {
            "skip_download": True,
            "writeautomaticsub": True,
            "writesubtitles": True,
            "subtitleslangs": ["en"],
            "subtitlesformat": "json3",
            "outtmpl": outtmpl,
            "quiet": True,
            "noprogress": True,
        }
        add_cookies(ydl_opts, Path(tmp_dir))
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
        except yt_dlp.utils.DownloadError as e:
            raise NoTranscriptAvailableError(f"yt-dlp subtitle fallback failed for {video_id}: {e}") from e

        sub_files = list(Path(tmp_dir).glob("subs*.json3"))
        if not sub_files:
            raise NoTranscriptAvailableError(f"No subtitles found for video {video_id} via yt-dlp fallback")
        return _parse_json3(json.loads(sub_files[0].read_text(encoding="utf-8")))


def get_transcript(video_id: str) -> list[TranscriptLine]:
    try:
        fetched = YouTubeTranscriptApi().fetch(video_id)
        return [TranscriptLine(text=s.text, start=s.start, duration=s.duration) for s in fetched]
    except CouldNotRetrieveTranscript:
        # Base class of every "couldn't get it" error: disabled, not found,
        # RequestBlocked/IpBlocked (Render's datacenter IP), PoTokenRequired,
        # YouTubeRequestFailed... yt-dlp with cookies is tried for all of them.
        pass

    lines = _fetch_via_ytdlp(video_id)
    if not lines:
        raise NoTranscriptAvailableError(f"No transcript available for video {video_id}")
    return lines
