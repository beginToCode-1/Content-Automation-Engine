from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import Resource, build

from content_engine.config import Settings
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
