"""Create or promote the first administrator.

Usage from the backend directory:
    python scripts/create_admin.py --email you@campus.edu --name "Your Name"

Easiest: sign up through the app first, then run this to promote that account (no password needed).
If the email has no Supabase account yet, one is created and you are asked for a password
(or set CREATE_ADMIN_PASSWORD); it is never accepted as a command-line argument.
Reference data must be seeded first (python scripts/seed_database.py).
"""

import argparse
import asyncio
import getpass
import os
import sys
from pathlib import Path

from sqlalchemy import func, select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import AsyncSessionLocal
from app.models import Department, User
from app.models.enums import RoleEnum
from app.services.supabase_admin import get_supabase_admin


def ask_password() -> str:
    password = os.environ.get("CREATE_ADMIN_PASSWORD") or getpass.getpass("New admin password (min 12 chars): ")
    if len(password) < 12:
        sys.exit("Password must be at least 12 characters.")
    return password


async def create_admin(email: str, full_name: str) -> str:
    email = email.lower()
    async with AsyncSessionLocal() as session:
        department = await session.scalar(select(Department).where(Department.code == "GENERAL"))
        department_id = department.id if department else None
        user = await session.scalar(select(User).where(func.lower(User.email) == email))
        if user is not None:
            user.role, user.is_active, user.department_id = RoleEnum.ADMIN.value, True, user.department_id or department_id
            outcome = "promoted to ADMIN"
        else:
            auth = get_supabase_admin()
            auth_id = await auth.find_user_id(email)
            if auth_id is None:
                auth_id = await auth.create_user(
                    email=email, password=ask_password(), full_name=full_name, role=RoleEnum.ADMIN.value
                )
                outcome = "created in Supabase and made ADMIN"
            else:
                outcome = "existing Supabase account made ADMIN"
            session.add(User(id=auth_id, email=email, full_name=full_name, role=RoleEnum.ADMIN.value,
                             department_id=department_id, is_active=True, is_verified=True))
        await session.commit()
        return outcome


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", required=True)
    args = parser.parse_args()
    print(f"{args.email}: {asyncio.run(create_admin(args.email, args.name))}")


if __name__ == "__main__":
    main()
