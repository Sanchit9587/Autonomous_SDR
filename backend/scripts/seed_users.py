"""Seed demo users so you can log into both apps immediately.

Run from backend/:  python -m scripts.seed_users

Creates (idempotent — skips any that already exist):
  manager  ava@sdrhq.io    / demo1234   (Manager app — Ava Chen)
  rep      mark@sdrhq.io   / demo1234   (Rep app — Mark Anders)
  admin    admin@sdrhq.io  / demo1234
Change these before any real deployment.
"""
from __future__ import annotations

import asyncio

from dotenv import load_dotenv

from auth.security import hash_password
from core.db import repository as repo
from core.db.engine import SessionLocal
from core.models.base import UserRole
from core.models.user import UserInDB

load_dotenv()

_DEMO_USERS = [
    ("ava@sdrhq.io", "demo1234", "Ava Chen", "Product Marketing Lead", UserRole.MANAGER),
    ("mark@sdrhq.io", "demo1234", "Mark Anders", "Sales Representative", UserRole.REP),
    ("admin@sdrhq.io", "demo1234", "Admin", "Administrator", UserRole.ADMIN),
]


async def main() -> None:
    async with SessionLocal() as session:
        for email, password, full_name, title, role in _DEMO_USERS:
            if await repo.get_user_by_email(session, email):
                print(f"skip (exists): {email}")
                continue
            user = UserInDB(
                email=email, full_name=full_name, title=title, role=role,
                hashed_password=hash_password(password),
            )
            await repo.save_user(session, user)
            print(f"created {role.value}: {email} / {password}")
        await session.commit()


if __name__ == "__main__":
    asyncio.run(main())