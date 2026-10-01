"""Demo accounts shared by the seed scripts and the test suite."""

import uuid
from pathlib import Path
import sys

from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models import Department, User

NAMESPACE = uuid.UUID("3d3f5c49-6b2e-4e6b-95c4-8bb1c75f9d31")

# (email prefix, full name, role, department code). Staff must belong to a department:
# ticket visibility for staff depends on it.
DEMO_USERS = [
    ("student", "Demo Student", "STUDENT", None),
    ("student2", "Demo Student Two", "STUDENT", None),
    ("faculty", "Demo Faculty", "FACULTY", None),
    ("staff", "Demo Staff", "STAFF", "IT"),
    ("staff2", "Demo Staff Electrical", "STAFF", "ELECTRICAL"),
    ("coordinator", "Demo Coordinator", "COORDINATOR", "GENERAL"),
    ("admin", "Demo Administrator", "ADMIN", "GENERAL"),
]
DEMO_EMAILS = [f"{prefix}@fixmycampus.dev" for prefix, *_ in DEMO_USERS]


def demo_user_id(prefix: str) -> uuid.UUID:
    """Deterministic id used when profiles are created without a Supabase account (tests)."""
    return uuid.uuid5(NAMESPACE, f"user:{prefix.upper()}")


async def departments_by_code(session) -> dict[str, Department]:
    return {d.code: d for d in (await session.scalars(select(Department))).all()}
