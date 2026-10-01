"""Create demo accounts (one per role) in Supabase Auth plus their application profiles.

Usage from the backend directory:
    python scripts/seed_demo_users.py --yes

These are real, working logins in your Supabase project. The password is taken from the
DEMO_USER_PASSWORD environment variable, or a random one is generated and printed once.
Remove the accounts (Admin page, or the Supabase dashboard) before real users arrive.
Safe to rerun: existing accounts are reused and their role/department refreshed.
"""

import argparse
import asyncio
import os
import secrets
import sys
from pathlib import Path

from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import AsyncSessionLocal
from app.models import User
from app.services.supabase_admin import get_supabase_admin
from scripts.demo_users import DEMO_USERS, departments_by_code


async def seed_demo_users(password: str) -> list[str]:
    auth = get_supabase_admin()
    lines = []
    async with AsyncSessionLocal() as session:
        departments = await departments_by_code(session)
        if not departments:
            raise RuntimeError("No departments found; run scripts/seed_database.py first.")
        for prefix, full_name, role, department_code in DEMO_USERS:
            email = f"{prefix}@fixmycampus.dev"
            auth_id = await auth.find_user_id(email)
            outcome = "reused"
            if auth_id is None:
                auth_id = await auth.create_user(email=email, password=password, full_name=full_name, role=role)
                outcome = "created"
            user = await session.scalar(select(User).where(User.id == auth_id))
            department_id = departments[department_code].id if department_code else None
            if user is None:
                session.add(User(id=auth_id, email=email, full_name=full_name, role=role,
                                 department_id=department_id, is_active=True, is_verified=True))
            else:
                user.role, user.department_id, user.is_active = role, department_id, True
            lines.append(f"  {email:<32} {role:<12} {outcome}")
        await session.commit()
    return lines


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--yes", action="store_true", help="Confirm you want working demo logins in this Supabase project")
    args = parser.parse_args()
    if not args.yes:
        sys.exit("Refusing to run without --yes: this creates real logins in your Supabase project.")
    password = os.environ.get("DEMO_USER_PASSWORD") or secrets.token_urlsafe(12)
    for line in asyncio.run(seed_demo_users(password)):
        print(line)
    print(f"\nPassword for newly created accounts: {password}")
    print("(Accounts that already existed keep their old password.)")


if __name__ == "__main__":
    main()
