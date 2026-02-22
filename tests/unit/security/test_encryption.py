"""Security tests: encryption round-trip; encryption fails with wrong key."""

import os
from unittest.mock import patch

import pytest

from app.security.encryption import EncryptionService
from app.security.exceptions import EncryptionError


def test_encryption_round_trip_works():
    """Encrypt then decrypt returns original. Use explicit key (no global state)."""
    key = "test-secret-key-at-least-32-chars-long-for-aes"
    svc = EncryptionService(key=key)
    plain = "sensitive data"
    encrypted = svc.encrypt(plain)
    assert encrypted != plain
    decrypted = svc.decrypt(encrypted)
    assert decrypted == plain


def test_encryption_fails_with_wrong_key():
    """Decrypting with a different key raises EncryptionError."""
    key1 = "test-secret-key-at-least-32-chars-long-for-aes"
    key2 = "other-secret-key-at-least-32-chars-long-for-aes"
    svc1 = EncryptionService(key=key1)
    encrypted = svc1.encrypt("secret")
    svc2 = EncryptionService(key=key2)
    with pytest.raises(EncryptionError) as exc_info:
        svc2.decrypt(encrypted)
    assert (
        "wrong" in str(exc_info.value.message).lower()
        or "invalid" in str(exc_info.value.message).lower()
        or "decrypt" in str(exc_info.value.message).lower()
    )


def test_encryption_fails_if_key_missing():
    """Service raises EncryptionError when key is missing (no key passed, env unset)."""
    with patch.dict(os.environ, {"ENCRYPTION_KEY": ""}, clear=False):
        with pytest.raises(EncryptionError) as exc_info:
            EncryptionService(key=None)
        msg = str(exc_info.value.message)
        assert "ENCRYPTION_KEY" in msg or "required" in msg.lower()


def test_encryption_empty_key_raises():
    """Empty string key raises."""
    with pytest.raises(EncryptionError):
        EncryptionService(key="")
