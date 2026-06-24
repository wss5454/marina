"""Database migrations and test-user seeding."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Literal

from alembic import command
from alembic.config import Config
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from marina_service.auth.password import hash_password
from marina_service.config import get_settings
from marina_service.models.boat import Boat
from marina_service.models.customer import Customer
from marina_service.models.enums import UserRole
from marina_service.models.staff_user import StaffUser

_BACKEND_ROOT = Path(__file__).resolve().parents[2]


class UserSeedResult(BaseModel):
    email: str | None = None
    status: Literal["created", "already_exists", "skipped"]
    detail: str | None = None


class BootstrapResult(BaseModel):
    ok: bool
    migrations: Literal["applied", "failed", "skipped"]
    migration_detail: str | None = None
    admin: UserSeedResult
    customer: UserSeedResult


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


async def ensure_test_customer(
    db: AsyncSession,
    email: str,
    password: str,
    *,
    first_name: str = "Test",
    last_name: str = "Customer",
    boat_make: str = "Sea Ray",
    boat_model: str = "Sundancer",
    boat_year: int = 2020,
) -> bool:
    """Create a claimed customer (and one boat) if missing. Returns True when created."""
    email = email.strip().lower()
    r = await db.execute(select(Customer).where(Customer.email == email))
    if r.scalar_one_or_none():
        return False

    customer = Customer(
        email=email,
        password_hash=hash_password(password),
        first_name=first_name,
        last_name=last_name,
        account_claimed=True,
        is_active=True,
    )
    db.add(customer)
    await db.flush()
    db.add(
        Boat(
            customer_id=customer.id,
            make=boat_make,
            model=boat_model,
            year=boat_year,
        )
    )
    await db.commit()
    return True


def _run_alembic_upgrade() -> None:
    settings = get_settings()
    cfg = Config(str(_BACKEND_ROOT / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", settings.database_url_sync)
    command.upgrade(cfg, "head")


async def run_migrations() -> tuple[Literal["applied", "failed"], str | None]:
    try:
        await asyncio.to_thread(_run_alembic_upgrade)
        return "applied", None
    except Exception as exc:  # noqa: BLE001 — surface migration errors to caller
        return "failed", str(exc)


async def seed_test_users(db: AsyncSession) -> tuple[UserSeedResult, UserSeedResult]:
    admin_email = os.environ.get("ADMIN_EMAIL", "").strip()
    admin_password = os.environ.get("ADMIN_PASSWORD", "")
    if admin_email and admin_password:
        if await ensure_admin_user(db, admin_email, admin_password):
            admin = UserSeedResult(email=admin_email, status="created")
        else:
            admin = UserSeedResult(email=admin_email, status="already_exists")
    else:
        admin = UserSeedResult(
            status="skipped",
            detail="Set ADMIN_EMAIL and ADMIN_PASSWORD environment variables.",
        )

    customer_email = os.environ.get("TEST_CUSTOMER_EMAIL", "").strip()
    customer_password = os.environ.get("TEST_CUSTOMER_PASSWORD", "")
    if customer_email and customer_password:
        created = await ensure_test_customer(
            db,
            customer_email,
            customer_password,
            first_name=os.environ.get("TEST_CUSTOMER_FIRST_NAME", "Test"),
            last_name=os.environ.get("TEST_CUSTOMER_LAST_NAME", "Customer"),
            boat_make=os.environ.get("TEST_CUSTOMER_BOAT_MAKE", "Sea Ray"),
            boat_model=os.environ.get("TEST_CUSTOMER_BOAT_MODEL", "Sundancer"),
            boat_year=int(os.environ.get("TEST_CUSTOMER_BOAT_YEAR", "2020")),
        )
        customer = UserSeedResult(
            email=customer_email,
            status="created" if created else "already_exists",
        )
    else:
        customer = UserSeedResult(
            status="skipped",
            detail="Set TEST_CUSTOMER_EMAIL and TEST_CUSTOMER_PASSWORD environment variables.",
        )

    return admin, customer


async def run_bootstrap(
    db: AsyncSession,
    *,
    run_db_migrations: bool = True,
) -> BootstrapResult:
    migration_status: Literal["applied", "failed", "skipped"] = "skipped"
    migration_detail: str | None = None

    if run_db_migrations:
        migration_status, migration_detail = await run_migrations()
        if migration_status == "failed":
            return BootstrapResult(
                ok=False,
                migrations=migration_status,
                migration_detail=migration_detail,
                admin=UserSeedResult(status="skipped", detail="Migrations failed."),
                customer=UserSeedResult(status="skipped", detail="Migrations failed."),
            )

    admin, customer = await seed_test_users(db)
    return BootstrapResult(
        ok=True,
        migrations=migration_status,
        migration_detail=migration_detail,
        admin=admin,
        customer=customer,
    )
