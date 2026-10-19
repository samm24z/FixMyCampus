"""Load the crawled college website (pages.jsonl) into the knowledge base the assistant searches.

Usage from the backend directory:
    python scripts/build_knowledge_base.py --input ../data/knowledge/mvsrec/pages.jsonl

Safe to rerun: unchanged pages are skipped, changed pages get new passages, and pages that are
gone from the file (or now count as noise) are switched off. The database is the one DATABASE_URL names.
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import AsyncSessionLocal
from app.services import knowledge_service


def read_pages(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


async def main(input_path: Path) -> None:
    rows = read_pages(input_path)
    async with AsyncSessionLocal() as db:
        stats = await knowledge_service.ingest(db, rows)
    print(f"Pages in file: {len(rows)}")
    print(f"Loaded: {stats.loaded} ({stats.chunks} passages)")
    print(f"Skipped as unchanged: {stats.unchanged}")
    print(f"Skipped as noise or duplicates: {stats.noise}")
    print(f"Switched off (no longer in the file): {stats.deactivated}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--input", type=Path, required=True, help="pages.jsonl from crawl_college_site.py")
    args = parser.parse_args()
    asyncio.run(main(args.input))
