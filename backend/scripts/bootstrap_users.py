"""Idempotent test user seeding from environment variables."""

import os

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from marina_service.auth.password import hash_password
from marina_service.models.boat import Boat
from marina_service.models.customer import Customer
from scripts.create_admin import ensure_admin_user


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


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
    existing = r.scalar_one_or_none()
    if existing:
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


async def run_bootstrap(db: AsyncSession) -> None:
    if not _env_bool("BOOTSTRAP_USERS"):
        print("Bootstrap skipped (set BOOTSTRAP_USERS=true to enable).")
        return

    admin_email = os.environ.get("ADMIN_EMAIL", "").strip()
    admin_password = os.environ.get("ADMIN_PASSWORD", "")
    if admin_email and admin_password:
        if await ensure_admin_user(db, admin_email, admin_password):
            print("Bootstrap: created admin", admin_email)
        else:
            print("Bootstrap: admin already exists", admin_email)
    else:
        print("Bootstrap: skipping admin (ADMIN_EMAIL and ADMIN_PASSWORD required).")

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
        if created:
            print("Bootstrap: created test customer", customer_email)
        else:
            print("Bootstrap: test customer already exists", customer_email)
    else:
        print("Bootstrap: skipping customer (TEST_CUSTOMER_EMAIL and TEST_CUSTOMER_PASSWORD required).")
