"""Password hashing + JWT encoding/decoding.

Boring, role-aware JWT auth. The token claims layout is intentionally
minimal — adding fields later is an additive change.

Claims:
    sub  user id (str)
    role one of viewer/analyst/admin
    exp  unix timestamp
    iat  unix timestamp
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import bcrypt
from jose import JWTError, jwt

from app.core.config import get_settings

# bcrypt has a hard 72-byte limit on the secret; longer inputs are truncated
# explicitly so the behaviour is predictable. The rest of the password is
# discarded — which is what passlib used to do silently, but newer bcrypt
# rejects rather than truncates, so we make the choice up front.
_BCRYPT_MAX = 72


def _encode(password: str) -> bytes:
    return password.encode("utf-8")[:_BCRYPT_MAX]


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(_encode(plain), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_encode(plain), hashed.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(*, user_id: int, role: str, ttl_minutes: int | None = None) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    exp = now + timedelta(minutes=ttl_minutes or settings.jwt_ttl_minutes)
    payload = {
        "sub": str(user_id),
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_alg)


class TokenDecodeError(Exception):
    """Raised when a JWT is malformed, expired, or signed with the wrong key."""


def decode_access_token(token: str) -> dict:
    settings = get_settings()
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_alg])
    except JWTError as exc:
        raise TokenDecodeError(str(exc)) from exc
