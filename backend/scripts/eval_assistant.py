"""Measure the assistant on hand-written questions (data/knowledge/eval_questions.json).

Usage from the backend directory:
    python scripts/eval_assistant.py --retrieval-only          # searching only, no Google calls
    python scripts/eval_assistant.py                           # also asks Gemini (needs GEMINI_API_KEY)

Reports hit@6 (a right page is among the six passages found), fact@6 (the key fact is in them), and with
Gemini the share of answers that contain the key fact and cite a right page. Uses the database DATABASE_URL names.
"""

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import AsyncSessionLocal
from app.services import assistant_service, knowledge_service

K = 6
DEFAULT_QUESTIONS = Path(__file__).resolve().parents[2] / "data" / "knowledge" / "eval_questions.json"


def normalise(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"\s*@\s*", "@", text)).lower()


async def main(questions_path: Path, retrieval_only: bool, pause: float) -> None:
    questions = json.loads(questions_path.read_text(encoding="utf-8"))
    llm = None if retrieval_only else assistant_service.get_llm()
    if not retrieval_only and llm is None:
        print("No GEMINI_API_KEY set: running retrieval only.\n")
    rows, misses = [], []
    async with AsyncSessionLocal() as db:
        for item in questions:
            passages = await knowledge_service.search(db, item["question"], K)
            expected = set(item["urls"])
            hit = any(p.url.split('#')[0] in expected for p in passages)
            fact = any(normalise(item["fact"]) in normalise(p.text) for p in passages)
            answered = cited = None
            if llm is not None:
                sources = [{"n": n, "title": p.title, "url": p.url, "text": p.text} for n, p in enumerate(passages, start=1)]
                try:
                    reply = await llm.reply(item["question"], sources, [], [])
                    answered = normalise(item["fact"]) in normalise(reply.answer)
                    cited = any(1 <= n <= len(passages) and passages[n - 1].url.split('#')[0] in expected for n in reply.cited)
                except Exception as exc:
                    answered = cited = False
                    print(f"  model failed on {item['question']!r}: {exc}")
                await asyncio.sleep(pause)
            rows.append((item["question"], hit, fact, answered, cited))
            if not hit:
                misses.append(item["question"])

    mark = lambda value: "-" if value is None else ("yes" if value else "NO")
    width = max(len(r[0]) for r in rows)
    print(f"{'Question':<{width}}  hit@{K}  fact@{K}  answer  cites")
    for question, hit, fact, answered, cited in rows:
        print(f"{question:<{width}}  {mark(hit):<6}  {mark(fact):<7}  {mark(answered):<6}  {mark(cited)}")
    total = len(rows)
    print(f"\nQuestions: {total}")
    print(f"Retrieval hit@{K}: {sum(r[1] for r in rows)}/{total} ({100 * sum(r[1] for r in rows) / total:.0f}%)")
    print(f"Key fact in the top {K} passages: {sum(r[2] for r in rows)}/{total}")
    if llm is not None:
        print(f"Answers containing the key fact: {sum(bool(r[3]) for r in rows)}/{total}")
        print(f"Answers citing a right page: {sum(bool(r[4]) for r in rows)}/{total}")
    if misses:
        print("\nMissed:")
        for question in misses:
            print(f"  - {question}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--questions", type=Path, default=DEFAULT_QUESTIONS)
    parser.add_argument("--retrieval-only", action="store_true", help="skip the model: no Google calls")
    parser.add_argument("--pause", type=float, default=4.0, help="seconds between model calls (free-tier limits)")
    args = parser.parse_args()
    asyncio.run(main(args.questions, args.retrieval_only, args.pause))
