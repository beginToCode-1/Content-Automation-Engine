from datetime import timezone

from tests.test_api_users import _auth_headers, _register, client  # noqa: F401  (fixture)


def _admin(client):
    return _auth_headers(_register(client, "admin@example.com")["access_token"])


def test_once_schedule_with_offset_is_stored_in_utc(client, pg_pool):
    res = client.post(
        "/api/schedule",
        headers=_admin(client),
        json={"topic": "t", "recurrence": "once", "platforms": ["tiktok"], "scheduled_time": "2026-10-05T09:00:00+05:00"},
    )
    assert res.status_code == 201, res.text
    with pg_pool.connection() as conn:
        row = conn.execute("SELECT scheduled_time FROM scheduled_topics WHERE id=%s", (res.json()["id"],)).fetchone()
    stored = row["scheduled_time"].astimezone(timezone.utc)
    assert (stored.hour, stored.minute) == (4, 0)


def test_schedule_rejects_unknown_platform(client):
    res = client.post(
        "/api/schedule",
        headers=_admin(client),
        json={"topic": "t", "recurrence": "daily", "platforms": ["bogus"], "daily_time": "09:00"},
    )
    assert res.status_code == 400


def test_overlong_topic_is_rejected(client):
    res = client.post(
        "/api/schedule",
        headers=_admin(client),
        json={"topic": "x" * 201, "recurrence": "daily", "platforms": ["tiktok"], "daily_time": "09:00"},
    )
    assert res.status_code == 400
