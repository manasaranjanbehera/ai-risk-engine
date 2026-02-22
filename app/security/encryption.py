"""AES-based encryption wrapper. Use env key; fail if key missing. No global state."""

import base64
import os
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from app.security.exceptions import EncryptionError

# Fernet uses AES-128-CBC; we derive a key from the raw secret if needed.
DEFAULT_SALT = b"ai_risk_engine_encryption_v1"


def _derive_key(secret: str, salt: bytes = DEFAULT_SALT) -> bytes:
    """Derive a 32-byte key for Fernet from a variable-length secret."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=480000,
    )
    return base64.urlsafe_b64encode(kdf.derive(secret.encode("utf-8")))


class EncryptionService:
    """
    AES-based encryption (Fernet). Use environment key; fail if key missing.
    No global state — key is passed in (from env in production).
    """

    def __init__(self, key: Optional[str] = None) -> None:
        """
        key: raw secret (e.g. from ENCRYPTION_KEY env). If None/empty, read from
        os.environ["ENCRYPTION_KEY"]. Raises EncryptionError if key missing.
        """
        raw = key or os.environ.get("ENCRYPTION_KEY")
        if not raw or not raw.strip():
            raise EncryptionError(
                "Encryption key is required. Set ENCRYPTION_KEY in environment."
            )
        self._fernet = Fernet(_derive_key(raw.strip()))

    def encrypt(self, data: str) -> str:
        """Encrypt string; return base64-encoded ciphertext."""
        try:
            encrypted = self._fernet.encrypt(data.encode("utf-8"))
            return base64.urlsafe_b64encode(encrypted).decode("ascii")
        except Exception as e:
            raise EncryptionError(f"Encryption failed: {e}") from e

    def decrypt(self, data: str) -> str:
        """Decrypt base64-encoded ciphertext. Raises EncryptionError if wrong key/corrupt."""
        try:
            raw = base64.urlsafe_b64decode(data.encode("ascii"))
            decrypted = self._fernet.decrypt(raw)
            return decrypted.decode("utf-8")
        except InvalidToken as e:
            raise EncryptionError("Decryption failed: invalid or wrong key") from e
        except Exception as e:
            raise EncryptionError(f"Decryption failed: {e}") from e
