"""Replace browser-validation tickets with a deterministic Review-1 demo dataset.

Usage from the backend directory:
    python scripts/seed_demo_data.py

This is development-only data. It removes only the two known browser smoke-test
records and their dependent records, then creates four synthetic campus tickets.
It does not alter the schema, migration history, application code, or reference data.
"""

import asyncio
import sys
import uuid
from pathlib import Path

from sqlalchemy import delete, select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import AsyncSessionLocal
from app.models import (
    Department,
    Ticket,
    TicketStatusHistory,
    User,
)
from app.models.enums import TicketStatusEnum


NAMESPACE = uuid.UUID("3d3f5c49-6b2e-4e6b-95c4-8bb1c75f9d31")
VALIDATION_TICKET_NUMBERS = {"TICK-2026-0001", "TICK-2026-0002"}
DEMO_TICKETS = [
    {
        "key": "wifi-c-block",
        "ticket_number": "TICK-2026-0101",
        "title": "WiFi not working in C Block",
        "description": "Students cannot connect to the campus WiFi in C Block since this morning, affecting normal access to the learning portal.",
        "category": "IT / Network",
        "location": "C Block, first floor",
        "priority": "HIGH",
        "status": TicketStatusEnum.NEW.value,
        "department_code": "IT",
    },
    {
        "key": "projector-c204",
        "ticket_number": "TICK-2026-0102",
        "title": "Projector not working in C-204",
        "description": "The classroom projector powers on but displays no image from the instructor workstation during scheduled lectures.",
        "category": "Classroom Equipment",
        "location": "C-204",
        "priority": "MEDIUM",
        "status": TicketStatusEnum.IN_PROGRESS.value,
        "department_code": "ACADEMIC",
    },
    {
        "key": "water-lab",
        "ticket_number": "TICK-2026-0103",
        "title": "Water leakage near laboratory",
        "description": "Water is leaking from a pipe near the laboratory entrance and has made part of the corridor floor wet.",
        "category": "Water / Plumbing",
        "location": "Science Block, laboratory corridor",
        "priority": "HIGH",
        "status": TicketStatusEnum.RESOLVED.value,
        "department_code": "PLUMBING",
    },
    {
        "key": "classroom-fan",
        "ticket_number": "TICK-2026-0104",
        "title": "Classroom fan not working",
        "description": "One ceiling fan is not operating in the classroom, making afternoon teaching uncomfortable for students and faculty.",
        "category": "Electrical",
        "location": "A-105",
        "priority": "MEDIUM",
        "status": TicketStatusEnum.REOPENED.value,
        "department_code": "ELECTRICAL",
    },
]


def stable_id(kind: str, value: str) -> uuid.UUID:
    return uuid.uuid5(NAMESPACE, f"{kind}:{value}")


async def seed_demo_data() -> dict[str, int]:
    async with AsyncSessionLocal() as session:
        validation_tickets = await session.scalars(
            select(Ticket).where(Ticket.ticket_number.in_(VALIDATION_TICKET_NUMBERS))
        )
        removed = 0
        for ticket in validation_tickets.all():
            await session.delete(ticket)
            removed += 1
        await session.flush()

        student = await session.scalar(select(User).where(User.email == "student@fixmycampus.dev"))
        coordinator = await session.scalar(select(User).where(User.email == "coordinator@fixmycampus.dev"))
        staff = await session.scalar(select(User).where(User.email == "staff@fixmycampus.dev"))
        if student is None or coordinator is None or staff is None:
            raise RuntimeError("Seed reference users are missing; run seed_database.py --reset first.")

        departments = {
            department.code: department
            for department in (await session.scalars(select(Department))).all()
        }
        required_departments = {item["department_code"] for item in DEMO_TICKETS}
        missing = required_departments - departments.keys()
        if missing:
            raise RuntimeError(f"Missing seed departments: {', '.join(sorted(missing))}")

        created = 0
        for item in DEMO_TICKETS:
            ticket = await session.scalar(
                select(Ticket).where(Ticket.ticket_number == item["ticket_number"])
            )
            department = departments[item["department_code"]]
            if ticket is None:
                ticket = Ticket(
                    id=stable_id("demo-ticket", item["key"]),
                    ticket_number=item["ticket_number"],
                    title=item["title"],
                    description=item["description"],
                    category=item["category"],
                    priority=item["priority"],
                    location=item["location"],
                    status=item["status"],
                    created_by=student.id,
                    confirmed_department_id=department.id,
                    assigned_to=staff.id if item["status"] in {TicketStatusEnum.IN_PROGRESS.value, TicketStatusEnum.RESOLVED.value} else None,
                    resolved_at=None,
                    reopened_at=None,
                    suggested_category=None,
                    confirmed_category=None,
                    suggested_department_id=None,
                    ai_confidence=None,
                    embedding=None,
                )
                if item["status"] == TicketStatusEnum.RESOLVED.value:
                    from datetime import datetime, timedelta, timezone
                    ticket.resolved_at = datetime.now(timezone.utc) - timedelta(days=1)
                if item["status"] == TicketStatusEnum.REOPENED.value:
                    from datetime import datetime, timedelta, timezone
                    ticket.reopened_at = datetime.now(timezone.utc) - timedelta(hours=3)
                session.add(ticket)
                await session.flush()
                session.add(TicketStatusHistory(
                    id=stable_id("demo-history", item["key"]),
                    ticket_id=ticket.id,
                    changed_by=coordinator.id,
                    from_status=None,
                    to_status=item["status"],
                    remarks="Synthetic Review-1 demonstration record.",
                ))
                created += 1

        await session.commit()
        return {"removed_validation_tickets": removed, "demo_tickets": created}


async def main() -> None:
    counts = await seed_demo_data()
    print("Demo seed complete:")
    for name, count in counts.items():
        print(f"  {name}: {count}")
    print("AI fields remain empty; all records are synthetic development data.")


if __name__ == "__main__":
    asyncio.run(main())
