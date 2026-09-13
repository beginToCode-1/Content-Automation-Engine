from datetime import datetime, timezone

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow, InstalledAppFlow
from googleapiclient.discovery import Resource, build

from content_engine.config import Settings
from content_engine.db import connected_accounts_repo, connection
from content_engine.errors import ConfigError

UPLOAD_SCOPE = "https://www.googleapis.com/auth/youtube.upload"
READONLY_SCOPE = "https://www.googleapis.com/auth/youtube.readonly"

# The cached token is shared across every caller in this app (search, upload,
# batch generation, self-upload), not per-operation. Always request the full
# union of scopes the app ever needs, regardless of what an individual caller
# asks for: requesting a narrower scope list here and then hitting a token
# refresh (e.g. because the access token expired) causes Google to issue a
# genuinely narrower access token and permanently downgrades the persisted
# token.json's real permissions until the next full re-auth - breaking any
# other caller that needs the wider scope, even though nothing about their
# own code changed. This bit us for real: a narrow-scope upload-only refresh
# silently broke search for every run afterward.
ALL_SCOPES = [READONLY_SCOPE, UPLOAD_SCOPE]


def get_youtube_client(scopes: list[str], settings: Settings) -> Resource:
    if not settings.client_secret_path.exists():
        raise ConfigError(
            f"OAuth client secret not found at {settings.client_secret_path}. "
            "See README for how to create a Google Cloud OAuth Desktop credential."
        )

    requested_scopes = sorted(set(scopes) | set(ALL_SCOPES))

    creds = None
    if settings.token_path.exists():
        creds = Credentials.from_authorized_user_file(str(settings.token_path), requested_scopes)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(settings.client_secret_path), requested_scopes)
            # open_browser=False: auto-launching a browser from this process doesn't
            # reach the user's visible desktop session, so print the URL instead -
            # the loopback server below still works fine over plain networking once
            # the user opens that URL in their own browser and completes consent.
            creds = flow.run_local_server(port=0, open_browser=False)
        settings.token_path.parent.mkdir(parents=True, exist_ok=True)
        settings.token_path.write_text(creds.to_json())

    return build("youtube", "v3", credentials=creds)


# ---------------------------------------------------------------------------
# Per-user "Connect YouTube" web flow - separate from everything above, which
# is the CLI's single global account (Desktop-app OAuth client, one shared
# config/token.json). This is a real "Web application" OAuth client: the
# browser is redirected to Google, Google redirects back to our own server
# with a code, and the resulting tokens are stored per-user in the
# connected_accounts table instead of one file on disk.
# ---------------------------------------------------------------------------


def _require_web_oauth_configured(settings: Settings) -> None:
    if not (settings.google_oauth_client_id and settings.google_oauth_client_secret and settings.google_oauth_redirect_uri):
        raise ConfigError(
            "GOOGLE_OAUTH_CLIENT_ID / GOOGLE_OAUTH_CLIENT_SECRET / GOOGLE_OAUTH_REDIRECT_URI "
            "are not set - the 'Connect YouTube' flow is not configured on this deployment."
        )


def _web_flow(settings: Settings) -> Flow:
    client_config = {
        "web": {
            "client_id": settings.google_oauth_client_id,
            "client_secret": settings.google_oauth_client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [settings.google_oauth_redirect_uri],
        }
    }
    flow = Flow.from_client_config(client_config, scopes=ALL_SCOPES)
    flow.redirect_uri = settings.google_oauth_redirect_uri
    return flow


def build_web_auth_url(settings: Settings, state: str) -> str:
    _require_web_oauth_configured(settings)
    flow = _web_flow(settings)
    # access_type=offline -> issue a refresh_token; prompt=consent -> issue one
    # every time (Google otherwise only grants a refresh_token on a user's very
    # first-ever consent for this client, which breaks reconnecting later).
    auth_url, _ = flow.authorization_url(
        access_type="offline", prompt="consent", state=state, include_granted_scopes="true"
    )
    return auth_url


def exchange_code_for_credentials(settings: Settings, code: str) -> Credentials:
    _require_web_oauth_configured(settings)
    flow = _web_flow(settings)
    flow.fetch_token(code=code)
    return flow.credentials


def fetch_channel_info(creds: Credentials) -> tuple[str, str]:
    """Returns (channel_id, channel_title) for the account these credentials belong to."""
    client = build("youtube", "v3", credentials=creds)
    response = client.channels().list(part="snippet", mine=True).execute()
    items = response.get("items", [])
    if not items:
        raise ConfigError("This Google account has no YouTube channel to connect.")
    channel = items[0]
    return channel["id"], channel["snippet"]["title"]


def expiry_to_iso(creds: Credentials) -> str | None:
    if creds.expiry is None:
        return None
    expiry = creds.expiry if creds.expiry.tzinfo else creds.expiry.replace(tzinfo=timezone.utc)
    return expiry.strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _iso_to_expiry(value: str | None):
    # google.oauth2.credentials.Credentials expects a naive UTC datetime here
    # (it compares against datetime.utcnow() internally) - strip the tzinfo
    # we add when storing, don't just pass the aware datetime through.
    if not value:
        return None
    dt = datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ")
    return dt.replace(tzinfo=None)


def get_youtube_client_for_account(account_id: str, settings: Settings) -> Resource:
    """Loads a specific connected account's stored credentials, refreshing (and
    persisting the refresh) if the access token has expired, then returns a
    ready-to-use YouTube API client for it."""
    pool = connection.get_pool()
    row = connected_accounts_repo.get_account(pool, account_id, settings.token_encryption_key)
    if row is None:
        raise ConfigError(f"Connected YouTube account {account_id} not found.")

    creds = Credentials(
        token=row["access_token"],
        refresh_token=row["refresh_token"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.google_oauth_client_id,
        client_secret=settings.google_oauth_client_secret,
        scopes=ALL_SCOPES,
        expiry=_iso_to_expiry(row["token_expiry"]),
    )

    if not creds.valid:
        if creds.refresh_token:
            creds.refresh(Request())
            connected_accounts_repo.update_tokens(
                pool,
                settings.token_encryption_key,
                account_id,
                access_token=creds.token,
                token_expiry=expiry_to_iso(creds),
                refresh_token=creds.refresh_token,
            )
        else:
            raise ConfigError(
                f"Connected YouTube account {account_id} has no refresh token and its access token "
                "expired - reconnect the account."
            )

    return build("youtube", "v3", credentials=creds)
