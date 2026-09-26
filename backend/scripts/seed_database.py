"""Seed or reset the development database with deterministic reference data.

Usage from the backend directory:
    python scripts/seed_database.py
    python scripts/seed_database.py --reset

The demo passwords are development-only and must never be reused elsewhere.
"""

import argparse
import asyncio
import sys
import uuid
from pathlib import Path

from sqlalchemy import delete, func, select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import AsyncSessionLocal
from app.core.security import get_password_hash
from app.models import Category, Department, Role, SLARule, Ticket, User


DEMO_PASSWORD = "FixMyCampus-Dev-2026!"
NAMESPACE = uuid.UUID("3d3f5c49-6b2e-4e6b-95c4-8bb1c75f9d31")

ROLE_DATA = [
    ("Student", "STUDENT"),
    ("Faculty", "FACULTY"),
    ("Staff", "STAFF"),
    ("Coordinator", "COORDINATOR"),
    ("Administrator", "ADMIN"),
]

DEPARTMENT_DATA = [
    ("IT Department", "IT"),
    ("Electrical Maintenance", "ELECTRICAL"),
    ("Sanitation", "SANITATION"),
    ("Plumbing / Water", "PLUMBING"),
    ("Academic Facilities", "ACADEMIC"),
    ("Civil Maintenance", "CIVIL"),
    ("General Administration", "GENERAL"),
]

CATEGORY_DATA = [
    ("IT / Network", "IT_NETWORK", "IT"),
    ("Electrical", "ELECTRICAL", "ELECTRICAL"),
    ("Sanitation", "SANITATION", "SANITATION"),
    ("Water / Plumbing", "WATER_PLUMBING", "PLUMBING"),
    ("Classroom Equipment", "CLASSROOM_EQUIPMENT", "ACADEMIC"),
    ("Civil Maintenance", "CIVIL_MAINTENANCE", "CIVIL"),
    ("Academic Facilities", "ACADEMIC_FACILITIES", "ACADEMIC"),
    ("Other", "OTHER", "GENERAL"),
]

PRIORITY_SLA = {"LOW": (168, 144), "MEDIUM": (72, 48), "HIGH": (24, 12), "CRITICAL": (4, 2)}


def stable_id(kind: str, value: str) -> uuid.UUID:
    return uuid.uuid5(NAMESPACE, f"{kind}:{value}")


async def reset_database(session) -> None:
    ticket_count = await session.scalar(select(func.count()).select_from(Ticket))
    if ticket_count:
        raise RuntimeError(
            "Refusing --reset because the database contains operational tickets. "
            "Use a disposable database or remove operational data explicitly."
        )
    for model in (SLARule, Category, User, Department, Role):
        await session.execute(delete(model))
    await session.commit()


async def seed_database(reset: bool = False) -> dict[str, int]:
    async with AsyncSessionLocal() as session:
        if reset:
            await reset_database(session)
        elif await session.scalar(select(func.count()).select_from(Role)):
            raise RuntimeError("Reference data already exists; rerun with --reset on a disposable development database.")

        roles: dict[str, Role] = {}
        for name, code in ROLE_DATA:
            role = Role(id=stable_id("role", code), name=name, code=code, description=f"Development {name} role", permissions={})
            session.add(role)
            roles[code] = role

        departments: dict[str, Department] = {}
        for name, code in DEPARTMENT_DATA:
            department = Department(id=stable_id("department", code), name=name, code=code, is_active=True)
            session.add(department)
            departments[code] = department
        await session.flush()

        for name, code, department_code in CATEGORY_DATA:
            session.add(Category(
                id=stable_id("category", code),
                name=name,
                code=code,
                default_department_id=departments[department_code].id,
                is_active=True,
            ))

        for name, role_code in ROLE_DATA:
            email = f"{role_code.lower()}@fixmycampus.dev"
            session.add(User(
                id=stable_id("user", role_code),
                email=email,
                password_hash=get_password_hash(DEMO_PASSWORD),
                full_name=f"Demo {name}",
                role=role_code,
                department_id=(
                    departments["IT"].id
                    if role_code == "COORDINATOR"
                    else departments["GENERAL"].id
                    if role_code == "ADMIN"
                    else None
                ),
                is_active=True,
                is_verified=True,
            ))

        for category_name, _, department_code in CATEGORY_DATA:
            for priority, (target_hours, escalation_hours) in PRIORITY_SLA.items():
                session.add(SLARule(
                    id=stable_id("sla", f"{category_name}:{priority}"),
                    category=category_name,
                    priority=priority,
                    department_id=departments[department_code].id,
                    target_resolution_hours=target_hours,
                    escalation_threshold_hours=escalation_hours,
                    is_active=True,
                ))

        await session.commit()
        return {"roles": len(ROLE_DATA), "departments": len(DEPARTMENT_DATA), "categories": len(CATEGORY_DATA), "users": len(ROLE_DATA), "sla_rules": len(CATEGORY_DATA) * len(PRIORITY_SLA)}


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reset", action="store_true", help="Delete development reference data before seeding")
    args = parser.parse_args()
    counts = await seed_database(reset=args.reset)
    print("Seed complete:")
    for name, count in counts.items():
        print(f"  {name}: {count}")
    print(f"Development demo password for all demo users: {DEMO_PASSWORD}")


if __name__ == "__main__":
    asyncio.run(main())