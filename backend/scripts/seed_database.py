"""Seed or reset the database with deterministic reference data.

Usage from the backend directory:
    python scripts/seed_database.py           # roles, departments, categories, SLA rules
    python scripts/seed_database.py --reset   # wipe that reference data (and users) first

Accounts are separate: create the first admin with scripts/create_admin.py and optional demo
accounts with scripts/seed_demo_users.py (both create the login in Supabase Auth).
"""

import argparse
import asyncio
import sys
import uuid
from pathlib import Path

from sqlalchemy import delete, func, select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import AsyncSessionLocal
from app.models import Category, Department, Role, SLARule, Ticket, User
from scripts.demo_users import NAMESPACE


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


async def seed_database(reset: bool = False, session_factory=AsyncSessionLocal) -> dict[str, int]:
    async with session_factory() as session:
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
        return {"roles": len(ROLE_DATA), "departments": len(DEPARTMENT_DATA), "categories": len(CATEGORY_DATA), "sla_rules": len(CATEGORY_DATA) * len(PRIORITY_SLA)}


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reset", action="store_true", help="Delete development reference data before seeding")
    args = parser.parse_args()
    counts = await seed_database(reset=args.reset)
    print("Seed complete:")
    for name, count in counts.items():
        print(f"  {name}: {count}")



if __name__ == "__main__":
    asyncio.run(main())