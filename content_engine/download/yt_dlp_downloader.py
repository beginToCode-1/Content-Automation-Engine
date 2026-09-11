from pathlib import Path

import yt_dlp

from content_engine.errors import DownloadFailedError
from content_engine.models import DownloadResult


def download_video(video_id: str, dest_dir: Path) -> DownloadResult:
    dest_dir.mkdir(parents=True, exist_ok=True)
    url = f"https://www.youtube.com/watch?v={video_id}"
    outtmpl = str(dest_dir / "source.%(ext)s")

    ydl_opts = {
        "format": "bv*[height<=1080]+ba/b[height<=1080]",
        "outtmpl": outtmpl,
        "merge_output_format": "mp4",
        "writeinfojson": True,
        "quiet": True,
        "noprogress": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
    except yt_dlp.utils.DownloadError as e:
        raise DownloadFailedError(f"Failed to download video {video_id}: {e}") from e

    video_path = dest_dir / "source.mp4"
    info_json_path = dest_dir / "source.info.json"
    if not video_path.exists():
        raise DownloadFailedError(f"Expected downloaded file not found at {video_path}")

    return DownloadResult(
        video_path=video_path,
        info_json_path=info_json_path,
        duration_s=float(info.get("duration") or 0.0),
    )
