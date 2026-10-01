"""Pytest configuration: an isolated, freshly migrated and seeded PostgreSQL test database.

Tests run against ``TEST_DATABASE_URL`` (default: ``fixmycampus_test`` on the local Docker
Postgres). The schema is dropped and rebuilt with Alembic at the start of every run, so the
database name must contain "test" - this guard stops the suite wiping a real database.
For a hosted database use a dedicated Neon branch/database, never the production one.
"""

import asyncio
import os
from pathlib import Path

from sqlalchemy.engine import make_url

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres_password@localhost:5432/fixmycampus_test",
)
if "test" not in (make_url(TEST_DATABASE_URL).database or ""):
    raise RuntimeError("TEST_DATABASE_URL must point at a database whose name contains 'test'")

# Must be set before the app (and its settings/engine) is imported.
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["MIGRATION_DATABASE_URL"] = ""
os.environ["ENVIRONMENT"] = "test"
os.environ["DEBUG"] = "False"
# Auth is tested with locally minted tokens, never against a real Supabase project.
os.environ["SUPABASE_URL"] = "https://test-project.supabase.co"
from tests.conftest_constants import TEST_JWT_SECRET  # noqa: E402
os.environ["SUPABASE_JWT_SECRET"] = TEST_JWT_SECRET
os.environ["SUPABASE_SERVICE_ROLE_KEY"] = "test-service-role-key"

import asyncpg  # noqa: E402
import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import select, text  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402
from sqlalchemy.pool import NullPool  # noqa: E402

from app.core.config import asyncpg_connect_args, normalise_async_url, settings  # noqa: E402
from app.core.database import engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Department, User  # noqa: E402
from app.services.supabase_admin import get_supabase_admin  # noqa: E402
from scripts.demo_users import DEMO_EMAILS, DEMO_USERS, demo_user_id  # noqa: E402
from scripts.seed_database import seed_database  # noqa: E402
from tests.helpers import FakeSupabaseAdmin, mint_token  # noqa: E402

BACKEND_DIR = Path(__file__).resolve().parents[1]


async def _create_database_if_missing() -> None:
    url = make_url(normalise_async_url(TEST_DATABASE_URL))
    ssl = url.query.get("ssl")
    try:
        conn = await asyncpg.connect(
            host=url.host, port=url.port or 5432, user=url.username, password=url.password,
            database="postgres", ssl=ssl if ssl else None,
        )
    except Exception:
        return  # e.g. a hosted database that already exists and forbids the maintenance connection
    try:
        exists = await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", url.database)
        if not exists:
            await conn.execute(f'CREATE DATABASE "{url.database}"')
    finally:
        await conn.close()


async def _reset_and_seed() -> None:
    # Belt and braces: backend/.env may hold hosted (Supabase) URLs. Everything this suite
    # does, including DROP SCHEMA, must land on the test database and nowhere else.
    for name, value in (("DATABASE_URL", settings.DATABASE_URL), ("alembic URL", settings.alembic_database_url)):
        if "test" not in (make_url(value).database or ""):
            raise RuntimeError(f"Refusing to reset: {name} does not point at a test database")
    await _create_database_if_missing()
    setup_engine = create_async_engine(
        normalise_async_url(TEST_DATABASE_URL), poolclass=NullPool,
        connect_args=asyncpg_connect_args(TEST_DATABASE_URL),
    )
    async with setup_engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
    await asyncio.get_running_loop().run_in_executor(None, _run_migrations)
    factory = async_sessionmaker(setup_engine, expire_on_commit=False)
    await seed_database(session_factory=factory)
    await _create_demo_profiles(factory)
    await setup_engine.dispose()


async def _create_demo_profiles(factory) -> None:
    """Application profiles only: no Supabase accounts exist in tests (tokens are minted)."""
    async with factory() as session:
        departments = {d.code: d for d in (await session.scalars(select(Department))).all()}
        for prefix, full_name, role, department_code in DEMO_USERS:
            session.add(User(
                id=demo_user_id(prefix), email=f"{prefix}@fixmycampus.dev", full_name=full_name, role=role,
                department_id=departments[department_code].id if department_code else None,
                is_active=True, is_verified=True,
            ))
        await session.commit()


def _run_migrations() -> None:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    command.upgrade(config, "head")


@pytest.fixture(scope="session", autouse=True)
def prepared_database() -> None:
    asyncio.run(_reset_and_seed())


@pytest_asyncio.fixture(autouse=True)
async def clean_operational_data():
    """Tickets, audit rows, and any non-demo users never leak between tests."""
    yield
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM audit_logs"))
        await conn.execute(text("DELETE FROM tickets"))
        await conn.execute(
            text("DELETE FROM users WHERE email <> ALL(:emails)").bindparams(emails=DEMO_EMAILS)
        )
    await engine.dispose()


@pytest_asyncio.fixture
async def async_client():
    """Async test client fixture."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        yield client


@pytest.fixture
def fake_supabase_admin():
    """Stand-in for the Supabase admin API (account creation / banning)."""
    fake = FakeSupabaseAdmin()
    app.dependency_overrides[get_supabase_admin] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_supabase_admin, None)


@pytest.fixture
def auth_headers():
    """``auth_headers(user_id, email)`` -> Authorization headers carrying a valid Supabase-style token."""

    def _headers(user_id, email: str, **claims) -> dict[str, str]:
        return {"Authorization": f"Bearer {mint_token(user_id, email, **claims)}"}

    return _headers


@pytest_asyncio.fixture
async def login(auth_headers):
    """``await login('staff')`` -> Authorization headers for that demo user."""

    async def _login(prefix: str) -> dict[str, str]:
        prefix = prefix.split("@")[0]
        return auth_headers(demo_user_id(prefix), f"{prefix}@fixmycampus.dev")

    return _login
