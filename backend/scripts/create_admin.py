"""Create or ensure admin staff user. Usage: python -m scripts.create_admin"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from marina_service.auth.password import hash_password
from marina_service.database import async_session_factory
from marina_service.models.enums import UserRole
from marina_service.models.staff_user import StaffUser


async def ensure_admin_user(
    db: AsyncSession,
    email: str,
    password: str,
    *,
    first_name: str = "Admin",
    last_name: str = "User",
) -> bool:
    """Create admin if missing. Returns True when a new user was created."""
    email = email.strip().lower()
    r = await db.execute(select(StaffUser).where(StaffUser.email == email))
    if r.scalar_one_or_none():
        return False
    db.add(
        StaffUser(
            email=email,
            password_hash=hash_password(password),
            first_name=first_name,
            last_name=last_name,
            role=UserRole.ADMIN.value,
            is_active=True,
        )
    )
    await db.commit()
    return True


async def main() -> None:
    email = os.environ.get("ADMIN_EMAIL", "admin@example.com")
    password = os.environ.get("ADMIN_PASSWORD", "changeme123")
    async with async_session_factory() as db:
        created = await ensure_admin_user(db, email, password)
        if created:
            print("Created admin:", email)
        else:
            print("Admin already exists:", email)


if __name__ == "__main__":
    asyncio.run(main())
