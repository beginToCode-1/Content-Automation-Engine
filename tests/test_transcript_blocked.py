from unittest.mock import MagicMock, patch

from youtube_transcript_api import RequestBlocked

from content_engine.transcript import fetch

JSON3 = '{"events": [{"tStartMs": 1000, "dDurationMs": 1000, "segs": [{"utf8": "hello world"}]}]}'


def test_blocked_ip_falls_back_to_ytdlp_with_cookies(tmp_path, monkeypatch):
    secret = tmp_path / "secret_cookies.txt"
    secret.write_text("# Netscape HTTP Cookie File\n")
    monkeypatch.setenv("YTDLP_COOKIES_FILE", str(secret))
    seen = {}

    def factory(opts):
        seen["opts"] = opts
        ydl = MagicMock()
        ydl.__enter__.return_value = ydl
        ydl.download.side_effect = lambda urls: open(opts["outtmpl"].replace("%(ext)s", "en.json3"), "w").write(JSON3)
        return ydl

    api = MagicMock()
    api.return_value.fetch.side_effect = RequestBlocked("abc")
    with patch.object(fetch, "YouTubeTranscriptApi", api), patch.object(fetch.yt_dlp, "YoutubeDL", side_effect=factory):
        lines = fetch.get_transcript("abc")

    assert [l.text for l in lines] == ["hello world"]
    assert seen["opts"]["cookiefile"].endswith("cookies.txt")


def test_parse_json3_auto_captions_gives_each_phrase_once_in_order():
    import json
    from pathlib import Path

    data = json.loads((Path(__file__).parent / "fixtures" / "auto_captions_sample.json3").read_text(encoding="utf-8"))
    lines = fetch._parse_json3(data)

    texts = [l.text for l in lines]
    assert texts[:3] == ["in this video we're going to go over a", "basic", "introduction slash overview of College"]
    assert len(texts) == len(set(texts))  # no rolling-display duplicates
    assert lines[0].start == 1.199
    assert all(a.start + a.duration <= b.start + 1e-9 for a, b in zip(lines, lines[1:]))  # no overlaps


def test_any_transcript_api_failure_falls_back_to_ytdlp():
    from youtube_transcript_api import PoTokenRequired

    api = MagicMock()
    api.return_value.fetch.side_effect = PoTokenRequired("abc")
    with patch.object(fetch, "YouTubeTranscriptApi", api), patch.object(
        fetch, "_fetch_via_ytdlp", return_value=["sentinel"]
    ) as fallback:
        assert fetch.get_transcript("abc") == ["sentinel"]
    fallback.assert_called_once_with("abc")
