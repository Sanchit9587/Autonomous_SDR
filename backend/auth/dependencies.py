"""FastAPI auth dependencies.

get_current_user: decodes the Bearer token, loads the user, 401s if invalid.
require_role(...): returns a dependency that 403s unless the user has one of the
allowed roles. require_manager / require_rep are convenience wrappers.
"""
from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from auth.security import decode_access_token
from core.db import repository as repo
from core.db.engine import get_session
from core.models.base import UserRole
from core.models.user import User

_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    session: AsyncSession = Depends(get_session),
) -> User:
    if creds is None or not creds.credentials:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated", {"WWW-Authenticate": "Bearer"})
    claims = decode_access_token(creds.credentials)
    if claims is None or "sub" not in claims:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token", {"WWW-Authenticate": "Bearer"})
    user = await repo.get_user(session, claims["sub"])
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found or inactive")
    return user


def require_role(*allowed: UserRole):
    async def _guard(user: User = Depends(get_current_user)) -> User:
        # Admin passes every role gate.
        if user.role == UserRole.ADMIN or user.role in allowed:
            return user
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            f"Requires role: {', '.join(r.value for r in allowed)} (you are '{user.role.value}')",
        )
    return _guard


require_manager = require_role(UserRole.MANAGER)
require_rep = require_role(UserRole.REP)