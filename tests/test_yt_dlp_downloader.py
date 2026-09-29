from unittest.mock import MagicMock, patch

from content_engine.download import yt_dlp_downloader

COOKIES = "# Netscape HTTP Cookie File\n"


def _run_download(dest_dir):
    """Runs download_video with yt-dlp faked out; returns the opts it got and
    whether the cookies copy was readable while yt-dlp ran."""
    seen = {}

    def factory(opts):
        seen["opts"] = opts
        ydl = MagicMock()
        ydl.__enter__.return_value = ydl

        def extract_info(url, download):
            if "cookiefile" in opts:
                seen["cookies_during_run"] = open(opts["cookiefile"]).read()
            (dest_dir / "source.mp4").write_bytes(b"")
            return {"duration": 12}

        ydl.extract_info.side_effect = extract_info
        return ydl

    with patch.object(yt_dlp_downloader.yt_dlp, "YoutubeDL", side_effect=factory):
        result = yt_dlp_downloader.download_video("abc", dest_dir)
    return seen, result


def test_cookies_file_is_copied_passed_and_removed(tmp_path, monkeypatch):
    secret = tmp_path / "secret_cookies.txt"
    secret.write_text(COOKIES)
    monkeypatch.setenv("YTDLP_COOKIES_FILE", str(secret))
    dest = tmp_path / "run"

    seen, result = _run_download(dest)

    assert seen["opts"]["cookiefile"] == str(dest / "cookies.txt")
    assert seen["cookies_during_run"] == COOKIES
    assert not (dest / "cookies.txt").exists()
    assert secret.read_text() == COOKIES
    assert result.duration_s == 12.0


def test_no_cookies_option_when_unset(tmp_path, monkeypatch):
    monkeypatch.delenv("YTDLP_COOKIES_FILE", raising=False)

    seen, _ = _run_download(tmp_path / "run")

    assert "cookiefile" not in seen["opts"]
