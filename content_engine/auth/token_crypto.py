from cryptography.fernet import Fernet, InvalidToken


def encrypt_token(key: str, plaintext: str) -> str:
    return Fernet(key.encode("utf-8")).encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_token(key: str, ciphertext: str) -> str:
    """Raises cryptography.fernet.InvalidToken if `key` doesn't match the key
    the value was encrypted with (e.g. TOKEN_ENCRYPTION_KEY rotated) - callers
    should treat that as "this connected account needs to be reconnected"."""
    return Fernet(key.encode("utf-8")).decrypt(ciphertext.encode("utf-8")).decode("utf-8")


__all__ = ["encrypt_token", "decrypt_token", "InvalidToken"]
