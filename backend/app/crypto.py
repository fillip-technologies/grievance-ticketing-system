"""Encryption at rest for org-supplied secrets: SMTP/IMAP passwords and Gemini API keys.

Uses Fernet (AES-128-CBC + HMAC) from `cryptography`. The key comes from
settings.encryption_key; if that's left unset, one is deterministically derived from
jwt_secret so local/dev setups keep working with zero extra config — but that's a
fallback, not a recommendation: set ENCRYPTION_KEY explicitly in production.

Decryption is backward-compatible with pre-encryption plaintext rows: a value that
isn't valid Fernet ciphertext is returned as-is instead of raising, so existing
installs upgrading onto this module don't lose access to already-stored credentials.
The next time that value is saved it gets encrypted like everything else.
"""

import base64
import hashlib
import logging

from cryptography.fernet import Fernet, InvalidToken

from .config import get_settings

logger = logging.getLogger("grievance_desk.crypto")
settings = get_settings()


def _derive_key_from(secret: str) -> bytes:
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def _build_cipher() -> Fernet:
    key = settings.encryption_key.strip()
    if key:
        return Fernet(key.encode("utf-8"))
    logger.warning(
        "ENCRYPTION_KEY is not set — deriving an encryption key from JWT_SECRET. "
        "Set an explicit ENCRYPTION_KEY in production so stored credentials survive a JWT_SECRET rotation."
    )
    return Fernet(_derive_key_from(settings.jwt_secret))


_cipher = _build_cipher()


def encrypt(plaintext: str | None) -> str:
    if not plaintext:
        return ""
    return _cipher.encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt(value: str | None) -> str:
    if not value:
        return ""
    try:
        return _cipher.decrypt(value.encode("utf-8")).decode("utf-8")
    except (InvalidToken, ValueError):
        # Not Fernet ciphertext — either legacy plaintext from before encryption was added,
        # or an empty/malformed value. Return as-is rather than losing the credential.
        return value
