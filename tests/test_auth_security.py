import jwt
import pytest

from content_engine.auth.security import create_access_token, decode_access_token, hash_password, verify_password


def test_hash_password_is_not_plaintext():
    hashed = hash_password("correct horse battery staple")
    assert hashed != "correct horse battery staple"


def test_verify_password_accepts_correct_password():
    hashed = hash_password("correct horse battery staple")
    assert verify_password("correct horse battery staple", hashed) is True


def test_verify_password_rejects_wrong_password():
    hashed = hash_password("correct horse battery staple")
    assert verify_password("wrong password", hashed) is False


def test_verify_password_rejects_malformed_hash():
    assert verify_password("anything", "not-a-real-bcrypt-hash") is False


def test_create_and_decode_access_token_round_trips_claims():
    token = create_access_token("secret", "user-1", "a@example.com", "admin")
    payload = decode_access_token("secret", token)

    assert payload["sub"] == "user-1"
    assert payload["email"] == "a@example.com"
    assert payload["role"] == "admin"


def test_decode_access_token_rejects_wrong_secret():
    token = create_access_token("secret", "user-1", "a@example.com", "admin")
    with pytest.raises(jwt.PyJWTError):
        decode_access_token("a-different-secret", token)


def test_decode_access_token_rejects_expired_token(monkeypatch):
    import content_engine.auth.security as security_module
    from datetime import timedelta

    monkeypatch.setattr(security_module, "ACCESS_TOKEN_TTL", timedelta(seconds=-1))
    token = create_access_token("secret", "user-1", "a@example.com", "admin")

    with pytest.raises(jwt.PyJWTError):
        decode_access_token("secret", token)
