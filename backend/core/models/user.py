"""User + auth payload models.

`User` is the public shape (safe to return from the API — no password). `UserInDB`
adds the password hash and is used only inside the auth/DB layers, never returned.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, EmailStr, Field

from core.models.base import TimestampedModel, UserRole, _new_id


class User(TimestampedModel):
    id: str = Field(default_factory=lambda: _new_id("user"))
    email: str
    full_name: Optional[str] = None
    title: Optional[str] = None            # e.g. "Product Marketing Lead"
    role: UserRole = UserRole.REP
    is_active: bool = True


class UserInDB(User):
    """Internal only — carries the password hash. Never serialize this to a client."""
    hashed_password: str


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    full_name: Optional[str] = None
    title: Optional[str] = None
    role: UserRole = UserRole.REP


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: User