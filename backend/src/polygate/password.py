"""Password hashing and browser-session helpers for the admin console."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1
SALT_BYTES = 16
SESSION_TTL_SECONDS = 7 * 24 * 60 * 60
MIN_PASSWORD_LENGTH = 8


def _encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def hash_password(password: str) -> str:
    """Return a salted scrypt hash suitable for durable storage."""
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"password must be at least {MIN_PASSWORD_LENGTH} characters")
    salt = secrets.token_bytes(SALT_BYTES)
    digest = hashlib.scrypt(
        password.encode(),
        salt=salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
    )
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${_encode(salt)}${_encode(digest)}"


def verify_password(password: str, encoded: str) -> bool:
    """Verify a password against a stored scrypt hash in constant time."""
    try:
        scheme, n, r, p, salt, digest = encoded.split("$")
        if scheme != "scrypt":
            return False
        expected = hashlib.scrypt(
            password.encode(),
            salt=_decode(salt),
            n=int(n),
            r=int(r),
            p=int(p),
        )
        return hmac.compare_digest(expected, _decode(digest))
    except (ValueError, TypeError):
        return False


def new_session_token() -> str:
    """Return a high-entropy bearer token for one browser session."""
    return secrets.token_urlsafe(32)


def session_digest(token: str) -> str:
    """Hash a session token before storing or looking it up."""
    return hashlib.sha256(token.encode()).hexdigest()
