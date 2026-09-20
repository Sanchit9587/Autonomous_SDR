"""Password hashing (bcrypt) and JWT issuance/verification.

Uses the `bcrypt` library directly rather than passlib — recent passlib releases
break against modern bcrypt (they probe bcrypt.__about__ which no longer exists),
and a hackathon shouldn't fight that. bcrypt directly is simple and stable.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import bcrypt
import jwt  # PyJWT

_JWT_ALGORITHM = "HS256"
_DEFAULT_EXPIRE_MINUTES = 60 * 24  # 24h — fine for a hackathon


def _secret() -> str:
    secret = os.getenv("JWT_SECRET")
    if not secret:
        # Dev fallback so the app runs out of the box; set JWT_SECRET in prod.
        secret = "dev-insecure-secret-change-me"
    return secret


# --- passwords --------------------------------------------------------------
def hash_password(plain: str) -> str:
    # bcrypt has a 72-byte input limit; encode and truncate defensively.
    pw = plain.encode("utf-8")[:72]
    return bcrypt.hashpw(pw, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8")[:72], hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# --- tokens -----------------------------------------------------------------
def create_access_token(*, user_id: str, email: str, role: str, expires_minutes: int = _DEFAULT_EXPIRE_MINUTES) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": user_id,
        "email": email,
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=expires_minutes),
    }
    return jwt.encode(payload, _secret(), algorithm=_JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[dict[str, Any]]:
    """Return the claims dict, or None if the token is invalid/expired."""
    try:
        return jwt.decode(token, _secret(), algorithms=[_JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None