from unittest.mock import MagicMock, patch

from content_engine.auth.google_oauth import ALL_SCOPES, UPLOAD_SCOPE, get_youtube_client
from tests.test_pipeline_progress_callback import _fake_settings


def test_get_youtube_client_always_requests_the_full_scope_union(tmp_path):
    """Regression test for a real bug: requesting a narrower scope list than the
    app actually needs (e.g. just UPLOAD_SCOPE for an upload-only call site) and
    then hitting a token refresh permanently downgrades the persisted token's
    real Google-side permissions to that narrower set - breaking every other
    caller (like search, which needs READONLY_SCOPE) until a fresh full-scope
    auth happens. get_youtube_client must always request ALL_SCOPES regardless
    of what an individual caller passes in.
    """
    settings = _fake_settings(tmp_path)
    settings.client_secret_path.write_text("{}", encoding="utf-8")
    settings.token_path.write_text("{}", encoding="utf-8")

    fake_creds = MagicMock()
    fake_creds.valid = True

    with patch(
        "content_engine.auth.google_oauth.Credentials.from_authorized_user_file", return_value=fake_creds
    ) as mock_from_file, patch("content_engine.auth.google_oauth.build", return_value=MagicMock()):
        get_youtube_client([UPLOAD_SCOPE], settings)

    called_scopes = mock_from_file.call_args.args[1]
    assert set(called_scopes) == set(ALL_SCOPES)


def test_get_youtube_client_requests_full_scopes_on_fresh_auth(tmp_path):
    settings = _fake_settings(tmp_path)
    settings.client_secret_path.write_text("{}", encoding="utf-8")
    # no cached token.json - forces the fresh-auth branch

    fake_creds = MagicMock()
    fake_flow = MagicMock()
    fake_flow.run_local_server.return_value = fake_creds
    fake_creds.to_json.return_value = "{}"

    with patch(
        "content_engine.auth.google_oauth.InstalledAppFlow.from_client_secrets_file", return_value=fake_flow
    ) as mock_from_secrets, patch("content_engine.auth.google_oauth.build", return_value=MagicMock()):
        get_youtube_client([UPLOAD_SCOPE], settings)

    called_scopes = mock_from_secrets.call_args.args[1]
    assert set(called_scopes) == set(ALL_SCOPES)
