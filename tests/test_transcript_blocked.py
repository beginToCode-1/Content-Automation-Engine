from unittest.mock import MagicMock, patch

from youtube_transcript_api import RequestBlocked

from content_engine.transcript import fetch

VTT = "WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nhello world\n"


def test_blocked_ip_falls_back_to_ytdlp_with_cookies(tmp_path, monkeypatch):
    secret = tmp_path / "secret_cookies.txt"
    secret.write_text("# Netscape HTTP Cookie File\n")
    monkeypatch.setenv("YTDLP_COOKIES_FILE", str(secret))
    seen = {}

    def factory(opts):
        seen["opts"] = opts
        ydl = MagicMock()
        ydl.__enter__.return_value = ydl
        ydl.download.side_effect = lambda urls: open(opts["outtmpl"].replace("%(ext)s", "en.vtt"), "w").write(VTT)
        return ydl

    api = MagicMock()
    api.return_value.fetch.side_effect = RequestBlocked("abc")
    with patch.object(fetch, "YouTubeTranscriptApi", api), patch.object(fetch.yt_dlp, "YoutubeDL", side_effect=factory):
        lines = fetch.get_transcript("abc")

    assert [l.text for l in lines] == ["hello world"]
    assert seen["opts"]["cookiefile"].endswith("cookies.txt")
