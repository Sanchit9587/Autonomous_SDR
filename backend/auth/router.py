"""Auth endpoints: login (open), me (any authenticated user), register (admin only)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import get_current_user, require_role
from auth.security import create_access_token, hash_password, verify_password
from core.db import repository as repo
from core.db.engine import get_session
from core.models.base import UserRole
from core.models.user import LoginRequest, TokenResponse, User, UserCreate, UserInDB

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, session: AsyncSession = Depends(get_session)) -> TokenResponse:
    user_in_db = await repo.get_user_by_email(session, body.email)
    if user_in_db is None or not verify_password(body.password, user_in_db.hashed_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")
    if not user_in_db.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account is inactive")

    token = create_access_token(user_id=user_in_db.id, email=user_in_db.email, role=user_in_db.role.value)
    public = User.model_validate(user_in_db.model_dump(exclude={"hashed_password"}))
    return TokenResponse(access_token=token, user=public)


@router.get("/me", response_model=User)
async def me(user: User = Depends(get_current_user)) -> User:
    return user


@router.get("/users", response_model=list[User])
async def list_users(
    session: AsyncSession = Depends(get_session),
    _user: User = Depends(require_role(UserRole.MANAGER)),
) -> list[User]:
    """List users (Manager/Admin) — powers the campaign Team member picker."""
    return await repo.list_users(session)


@router.post("/register", response_model=User)
async def register(
    body: UserCreate,
    session: AsyncSession = Depends(get_session),
    _admin: User = Depends(require_role(UserRole.ADMIN)),
) -> User:
    """Admin-only. First users are created via scripts/seed_users.py."""
    existing = await repo.get_user_by_email(session, body.email)
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "A user with that email already exists")
    user = UserInDB(
        email=body.email, full_name=body.full_name, title=body.title, role=body.role,
        hashed_password=hash_password(body.password),
    )
    await repo.save_user(session, user)
    return User.model_validate(user.model_dump(exclude={"hashed_password"}))