"""Close RESOLVED tickets the reporter has not answered within AUTO_CLOSE_RESOLVED_AFTER_DAYS days.

The API server does this on a timer by itself. Use this one-shot run from cron on hosts where the
server sleeps (set AUTO_CLOSE_INTERVAL_MINUTES=0 there).

Usage from the backend directory:
    python scripts/close_resolved_tickets.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import AsyncSessionLocal
from app.services.ticket_service import auto_close_resolved_tickets


async def main() -> int:
    async with AsyncSessionLocal() as session:
        return await auto_close_resolved_tickets(session)


if __name__ == "__main__":
    print(f"Closed {asyncio.run(main())} resolved ticket(s).")
