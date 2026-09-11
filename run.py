import argparse
import shutil
import sys

from content_engine.config import Settings
from content_engine.errors import PipelineError, UploadFailedError
from content_engine.pipeline import run_pipeline

VALID_PLATFORMS = {"youtube", "instagram", "tiktok"}


def check_setup() -> int:
    print("Checking setup...\n")
    ok = True

    try:
        settings = Settings.load()
        print("[OK]   .env loaded, required keys present")
    except PipelineError as e:
        print(f"[FAIL] {e}")
        return 1

    if shutil.which("ffmpeg") and shutil.which("ffprobe"):
        print("[OK]   ffmpeg/ffprobe found on PATH")
    else:
        print("[FAIL] ffmpeg/ffprobe not found on PATH. See README for install instructions.")
        ok = False

    if settings.client_secret_path.exists():
        print(f"[OK]   OAuth client secret found at {settings.client_secret_path}")
    elif settings.youtube_api_key:
        print("[SKIP] No OAuth client secret, but YOUTUBE_API_KEY is set (search only; upload still needs OAuth)")
    else:
        print(f"[FAIL] No OAuth client secret at {settings.client_secret_path} and no YOUTUBE_API_KEY set.")
        ok = False

    if settings.instagram_access_token and settings.instagram_business_account_id:
        if settings.instagram_public_video_base_url:
            print("[OK]   Instagram credentials and public video base URL are set")
        else:
            print("[SKIP] Instagram credentials set but INSTAGRAM_PUBLIC_VIDEO_BASE_URL is missing")
    else:
        print("[SKIP] Instagram not configured (optional - see README)")

    from content_engine.auth import tiktok_oauth

    if settings.tiktok_client_key and settings.tiktok_client_secret:
        if tiktok_oauth.load_token(settings.tiktok_token_path):
            print("[OK]   TikTok credentials and cached token found")
        else:
            print(
                "[SKIP] TikTok credentials set but not yet authorized - "
                "run `python run.py --tiktok-auth <redirect_uri>`"
            )
    else:
        print("[SKIP] TikTok not configured (optional - see README)")

    if not ok:
        print("\nSetup incomplete. Fix the items above before running a topic.")
        return 1

    print("\nAttempting a trivial YouTube search to confirm API access...")
    try:
        from content_engine.auth.google_oauth import ALL_SCOPES, get_youtube_client
        from content_engine.search.youtube_search import build_search_client, search_videos

        oauth_client = None
        if not settings.youtube_api_key:
            oauth_client = get_youtube_client(ALL_SCOPES, settings)
        client = build_search_client(settings.youtube_api_key, oauth_client)
        search_videos("test", max_results=1, client=client)
        print("[OK]   YouTube API search call succeeded")
    except PipelineError as e:
        print(f"[FAIL] YouTube API call failed: {e}")
        return 1

    print("\nSetup looks good.")
    return 0


def tiktok_auth(redirect_uri: str) -> int:
    from content_engine.auth import tiktok_oauth

    try:
        settings = Settings.load()
    except PipelineError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        return 1

    if not settings.tiktok_client_key or not settings.tiktok_client_secret:
        print("Set TIKTOK_CLIENT_KEY and TIKTOK_CLIENT_SECRET in .env first.", file=sys.stderr)
        return 1

    url = tiktok_oauth.build_authorization_url(settings.tiktok_client_key, redirect_uri)
    print("1. Open this URL in a browser and authorize the app:\n")
    print(f"   {url}\n")
    print(f"2. You'll be redirected to {redirect_uri}?code=...&state=...")
    print("   (TikTok requires an HTTPS redirect URI registered in your app - a tunnel")
    print("   like `ngrok http 8000` pointed at the dashboard works well for this.)\n")
    code = input("3. Paste the 'code' value from that URL here: ").strip()
    if not code:
        print("No code provided.", file=sys.stderr)
        return 1

    try:
        token_data = tiktok_oauth.exchange_code_for_token(
            settings.tiktok_client_key, settings.tiktok_client_secret, code, redirect_uri
        )
    except UploadFailedError as e:
        print(f"Token exchange failed: {e}", file=sys.stderr)
        return 1

    tiktok_oauth.save_token(settings.tiktok_token_path, token_data)
    print(f"\nSaved TikTok token to {settings.tiktok_token_path}. TikTok is ready to use.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Content Automation Engine")
    parser.add_argument("--topic", help="Topic of the day to generate a short from")
    parser.add_argument("--dry-run", action="store_true", help="Run the pipeline but skip uploading")
    parser.add_argument("--privacy", choices=["private", "unlisted", "public"], help="Override upload privacy status")
    parser.add_argument(
        "--platforms",
        nargs="+",
        choices=sorted(VALID_PLATFORMS),
        default=["youtube"],
        help="Platforms to upload to (default: youtube)",
    )
    parser.add_argument("--check-setup", action="store_true", help="Validate configuration and exit")
    parser.add_argument(
        "--tiktok-auth",
        metavar="REDIRECT_URI",
        help="One-time TikTok OAuth authorization (pass the HTTPS redirect URI registered in your app)",
    )
    args = parser.parse_args()

    if args.tiktok_auth:
        return tiktok_auth(args.tiktok_auth)

    if args.check_setup:
        return check_setup()

    if not args.topic:
        parser.error("--topic is required unless --check-setup or --tiktok-auth is used")

    try:
        settings = Settings.load()
    except PipelineError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        return 1

    try:
        result = run_pipeline(
            args.topic,
            settings,
            dry_run=args.dry_run,
            privacy_override=args.privacy,
            target_platforms=args.platforms,
        )
    except PipelineError as e:
        print(f"\nPipeline failed: {e}", file=sys.stderr)
        return 1

    print(f"\nRun {result.run_id} complete.")
    print(f"Source video: https://youtube.com/watch?v={result.source_video.video_id}")
    print(f"Clip: {result.clip_path}")
    print(f"Title: {result.metadata.title}")
    if result.uploads:
        for outcome in result.uploads:
            if outcome.result:
                print(f"Uploaded to {outcome.platform} ({outcome.result.privacy_status}): {outcome.result.url}")
            else:
                print(f"Upload to {outcome.platform} failed: {outcome.error}")
    else:
        print("Dry run: not uploaded.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
