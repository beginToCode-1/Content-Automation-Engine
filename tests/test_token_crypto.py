from cryptography.fernet import Fernet, InvalidToken
import pytest

from content_engine.auth.token_crypto import decrypt_token, encrypt_token


def _key() -> str:
    return Fernet.generate_key().decode("utf-8")


def test_encrypt_produces_different_ciphertext_than_plaintext():
    key = _key()
    ciphertext = encrypt_token(key, "my-secret-refresh-token")
    assert ciphertext != "my-secret-refresh-token"


def test_decrypt_round_trips():
    key = _key()
    ciphertext = encrypt_token(key, "my-secret-refresh-token")
    assert decrypt_token(key, ciphertext) == "my-secret-refresh-token"


def test_decrypt_with_wrong_key_raises():
    ciphertext = encrypt_token(_key(), "my-secret-refresh-token")
    with pytest.raises(InvalidToken):
        decrypt_token(_key(), ciphertext)
