"""Password hashing and session cookies."""

from __future__ import annotations

import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from argon2.low_level import Type

# OWASP's minimum memory target for argon2id is 19 MiB.
_HASHER = PasswordHasher(
    time_cost=2,
    memory_cost=19456,
    parallelism=1,
    hash_len=32,
    salt_len=16,
    type=Type.ID,
)

SESSION_COOKIE = "folio_session"
SESSION_DAYS = 14


def hash_password(password: str) -> str:
    """Hash a password with argon2id."""
    return _HASHER.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    """Return whether the password matches the stored argon2id hash."""
    try:
        return _HASHER.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def new_session_token() -> str:
    """Return a new unguessable session token."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Return the SHA-256 hex digest stored for a session token."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def session_expiry() -> str:
    """Return an ISO timestamp for when a new session expires."""
    moment = datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS)
    return moment.isoformat()


def cookie_secure() -> bool:
    """Return whether the session cookie should set the Secure flag."""
    return os.environ.get("FOLIO_COOKIE_SECURE", "0").strip().lower() in {
        "1",
        "true",
        "yes",
    }
