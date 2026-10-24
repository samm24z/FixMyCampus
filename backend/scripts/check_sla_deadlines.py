"""Send "due soon" and "overdue" alerts for open tickets, and delete old read notifications.

The API server does this on a timer by itself. Use this one-shot run from cron on hosts where the
server sleeps (set AUTO_CLOSE_INTERVAL_MINUTES=0 there).

Usage from the backend directory:
    python scripts/check_sla_deadlines.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import AsyncSessionLocal
from app.services import notification_service, sla_service


async def main() -> str:
    async with AsyncSessionLocal() as session:
        warned, breached = await sla_service.check_deadlines(session)
        purged = await notification_service.purge_old(session)
    return f"Sent {warned} due-soon and {breached} overdue alert(s); deleted {purged} old notification(s)."


if __name__ == "__main__":
    print(asyncio.run(main()))
