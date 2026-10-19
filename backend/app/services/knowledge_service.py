"""The college website text the assistant answers from: cutting pages into passages, loading them, searching them.

Search is hybrid: vector similarity (finds paraphrases) and full-text search (finds names, emails and
codes the embedding model blurs), merged by reciprocal rank fusion. Only active pages are searched.
"""

import hashlib
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterable, Optional

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ai.interfaces import BaseEmbeddingService
from app.core import campus
from app.models.knowledge import KnowledgeChunk, KnowledgeDocument
from app.services import suggestion_service

logger = logging.getLogger("app.knowledge")

CHUNK_CHARS = 700  # MiniLM reads about 256 tokens
MAX_CHUNKS_PER_DOCUMENT = 120
EMBED_BATCH = 64
CANDIDATES = 20
RRF_K = 60

NOISE_PATTERNS = [re.compile(p, re.I) for p in (
    r"/SIH/", r"hackathon", r"problem[- _]statements?", r"annual[- _]reports?", r"/TechMag/", r"group[_ -]?photo", r"news-?letter",
)]
_SENTENCE = re.compile(r"(?<=[.!?])\s+")
_ROW = " | "
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")  # PDFs carry stray NULs that PostgreSQL rejects


def is_noise(row: dict) -> bool:
    """Pages that would only crowd out real answers: contest problem lists, magazines, empty stubs."""
    title, url, size = row.get("title") or "", row.get("url") or "", len(row.get("text") or "")
    if any(p.search(url) or p.search(title) for p in NOISE_PATTERNS):
        return True
    if title.strip().lower() == "coming soon":
        return True
    return size < 400 and "click here" in title.lower()


def _split_long(line: str, limit: int) -> list[str]:
    """Break an over-long line at sentence ends, then at spaces."""
    pieces, current = [], ""
    for sentence in _SENTENCE.split(line):
        for word in sentence.split(" "):
            while len(word) > limit:  # a single endless token: cut it
                pieces.append(word[:limit])
                word = word[limit:]
            if current and len(current) + len(word) + 1 > limit:
                pieces.append(current)
                current = word
            else:
                current = f"{current} {word}".strip()
    if current:
        pieces.append(current)
    return pieces


def _is_header(row: str) -> bool:
    return len(row) <= 200 and not any(ch.isdigit() for ch in row)


def chunk_document(title: str, section: str, body: str) -> list[tuple[str, str]]:
    """Return (passage, heading) pairs of about CHUNK_CHARS characters.

    Passages start with "Title (Section):" and the heading they sit under; table passages repeat the
    table's header row so a row keeps its column names.
    """
    title, section = _CONTROL.sub("", title), _CONTROL.sub("", section)
    prefix = f"{title} ({section}):"
    lines = [line.strip() for line in _CONTROL.sub("", body).splitlines() if line.strip()]
    chunks: list[tuple[str, str]] = []
    heading, table_header, in_table = "", "", False
    pending: list[str] = []

    def flush() -> None:
        if not pending:
            return
        head = [prefix]
        if heading and heading != title:
            head.append(heading)
        if table_header and pending[0] != table_header:
            head.append(table_header)
        chunks.append(("\n".join(head + pending), heading))
        pending.clear()

    def size() -> int:
        return sum(len(line) + 1 for line in pending) + len(table_header) + len(prefix) + len(heading)

    for index, line in enumerate(lines):
        if line.startswith("## "):
            flush()
            heading, table_header, in_table = line[3:].strip()[:160], "", False
            continue
        is_row = _ROW in line
        if is_row and not in_table:
            in_table = True
            table_header = line if _is_header(line) and index + 1 < len(lines) and _ROW in lines[index + 1] else ""
        elif not is_row:
            in_table, table_header = False, ""
        for piece in _split_long(line, CHUNK_CHARS - 100) if len(line) > CHUNK_CHARS - 100 else [line]:
            if pending and size() + len(piece) + 1 > CHUNK_CHARS:
                flush()
            pending.append(piece)
    flush()
    return chunks[:MAX_CHUNKS_PER_DOCUMENT]


@dataclass
class IngestStats:
    loaded: int = 0
    unchanged: int = 0
    noise: int = 0
    deactivated: int = 0
    chunks: int = 0
    noise_titles: list[str] = field(default_factory=list)


def _parse_time(value: Optional[str]) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(value) if value else None
    except ValueError:
        return None


async def _embed_all(embedder: BaseEmbeddingService, texts: list[str]) -> list[Optional[list[float]]]:
    vectors: list[Optional[list[float]]] = []
    for start in range(0, len(texts), EMBED_BATCH):
        vectors.extend(await embedder.embed_many(texts[start:start + EMBED_BATCH]))
    return vectors


# Department heads are spread over the contact page and each faculty table, worded "Head ECE Dept."
# or "Professor & HoD"; short generated entries make "who is the head of ECE?" findable.
DEPARTMENTS = {  # code: (full name, short name, email prefix on the contact page)
    "CE": ("Civil Engineering", "Civil", "hod_civil"),
    "CSE": ("Computer Science and Engineering", "CSE", "hod_cse"),
    "CSE-A": ("CSE Allied (CSE specialisations)", "CSE Allied", "hod_cseallied"),
    "ECE": ("Electronics and Communication Engineering", "ECE", "hod_ece"),
    "EEE": ("Electrical and Electronics Engineering", "EEE", "hod_eee"),
    "IT": ("Information Technology", "IT", "hod_it"),
    "ME": ("Mechanical Engineering", "Mechanical", "hod_mech"),
    "AE": ("Automobile Engineering", "Automobile", "hod_auto"),
    "ASH": ("Applied Sciences and Humanities (S&H)", "S&H", "hod_sh"),
    "MBA": ("Business Administration (MBA)", "MBA", "hod_mba"),
}
CONTACT_PAGE = "https://mvsrec.edu.in/index.php?id=684&option=com_content&view=article"


def _contact_heads(rows: list[dict]) -> dict[str, dict]:
    """Name, phone and email of each head, from the contact page's 'HEAD OF THE DEPARTMENTS' block."""
    page = next((r for r in rows if r.get("url") == CONTACT_PAGE), None)
    text = (page or {}).get("text", "")
    start = text.find("HEAD OF THE DEPARTMENTS")
    if start < 0:
        return {}
    heads, entry = {}, []
    for line in text[start:].split("\n")[1:]:
        entry.append(line.strip())
        email = re.search(r"(hod_[a-z]+)\s*@\s*mvsrec\.edu\.in", line, re.I)
        if not email:
            continue
        phone = next((re.sub(r"^.*?:\s*", "", e) for e in entry if e.lower().startswith("phone")), "")
        first = entry[0]
        name = (re.sub(r"^Head\b.*?Dept\.?\s*", "", first, flags=re.I) if re.match(r"head\b", first, re.I)
                else re.sub(r",?\s*Head\b.*$", "", first, flags=re.I)).strip(" ,")
        heads[email.group(1).lower()] = {"name": name or entry[0], "phone": phone, "email": f"{email.group(1).lower()}@mvsrec.edu.in"}
        entry = []
    return heads


def _faculty_heads(rows: list[dict]) -> dict[str, tuple[str, str, str]]:
    """(name, designation, faculty page url) of the HoD row in each department's faculty table."""
    heads = {}
    for row in rows:
        code = re.search(r"faculty\.php\?option=([A-Za-z-]+)$", row.get("url", ""))
        if not code:
            continue
        for line in (row.get("text") or "").split("\n"):
            cells = [c.strip() for c in line.split(_ROW)]
            if len(cells) > 2 and re.search(r"\bho\s*d\b", cells[2], re.I):
                heads[code.group(1).upper()] = (cells[1], cells[2], row["url"])
                break
    return heads


def department_head_rows(rows: list[dict]) -> list[dict]:
    """One generated entry per department head, built only from what the website publishes."""
    contacts, faculty = _contact_heads(rows), _faculty_heads(rows)
    generated, summary = [], []
    for code, (full, short, prefix) in DEPARTMENTS.items():
        contact, listed = contacts.get(prefix), faculty.get(code)
        if not contact and not listed:
            continue
        name = contact["name"] if contact else listed[0]
        lines = [f"## Head of the {short} department: {full}",
                 f"The Head of Department (HOD) of {full} ({short} department) is {name}."]
        if listed:
            lines.append(f"The department's faculty list names {listed[0]} as {listed[1]}.")
        if contact and contact["phone"]:
            lines.append(f"Phone No: {contact['phone']}")
        if contact:
            lines.append(f"Email: {contact['email']}")
        text_body = "\n".join(lines)
        summary.append(f"- {short} ({full}): {name}" + (f", {contact['email']}" if contact else ""))
        generated.append({
            "url": f"{CONTACT_PAGE}#hod-{code.lower()}" if contact else f"{listed[2]}#hod",
            "title": f"Head of the {short} department", "kind": "html", "section": "Departments", "text": text_body,
            "fetched_at": next((r.get("fetched_at") for r in rows if r.get("url") == CONTACT_PAGE), None),
            "sha256": hashlib.sha256(text_body.encode()).hexdigest(),
        })
    if summary:
        text_body = "## Heads of all departments (HODs)\n" + "\n".join(summary)
        generated.append({
            "url": f"{CONTACT_PAGE}#hods", "title": "Heads of all departments", "kind": "html", "section": "Departments",
            "text": text_body, "fetched_at": None, "sha256": hashlib.sha256(text_body.encode()).hexdigest(),
        })
    return generated


CAMPUS_GUIDE = "/campus-guide"  # an in-app page: the campus layout is not on the college website


def _generated(url: str, title: str, section: str, text_body: str) -> dict:
    return {
        "url": url, "title": title, "kind": "html", "section": section, "text": text_body,
        "fetched_at": None, "sha256": hashlib.sha256(text_body.encode()).hexdigest(),
    }


def campus_guide_rows() -> list[dict]:
    """An overview plus one entry per block and facility, from app.core.campus; names and aliases make "where is ..." findable."""
    overview = ["## Campus guide: blocks and facilities", "Where things are on the MVSR Engineering College campus, and which block each branch has its classes in."]
    for kind, heading in ((campus.BLOCK, "Blocks"), (campus.FACILITY, "Other places")):
        overview.append(f"## {heading}")
        overview += [f"- {place.name}: {place.description}" for place in campus.PLACES if place.kind == kind]
    generated = [_generated(f"{CAMPUS_GUIDE}#overview", "Campus guide: blocks and facilities", "Campus guide", "\n".join(overview))]
    for place in campus.PLACES:
        lines = [f"## {place.name}", place.description, f"Also called: {', '.join(place.aliases)}."]
        generated.append(_generated(f"{CAMPUS_GUIDE}#{place.key}", f"Campus guide: {place.name}", "Campus guide", "\n".join(lines)))
    return generated


async def ingest(db: AsyncSession, rows: Iterable[dict], embedder: Optional[BaseEmbeddingService] = None) -> IngestStats:
    """Load crawled pages. Unchanged pages are skipped, changed ones get new passages, vanished ones go inactive."""
    embedder = embedder or suggestion_service.get_embedder()
    stats = IngestStats()
    existing = {doc.url: doc for doc in (await db.scalars(select(KnowledgeDocument).where(KnowledgeDocument.url.is_not(None)))).all()}
    seen_urls: set[str] = set()
    seen_hashes: set[str] = set()
    rows = list(rows)
    rows += department_head_rows(rows)
    rows += campus_guide_rows()
    for row in rows:
        url = row["url"]
        doc = existing.get(url)
        digest = row.get("sha256")
        if is_noise(row) or (digest and digest in seen_hashes):
            stats.noise += 1
            stats.noise_titles.append(row.get("title", url)[:60])
            continue  # left out of seen_urls: a page that became noise is deactivated below
        seen_urls.add(url)
        if digest:
            seen_hashes.add(digest)
        if doc is not None and doc.is_active and doc.source_sha256 == digest:
            stats.unchanged += 1
            continue
        passages = chunk_document(row.get("title") or url, row.get("section") or "General", row.get("text") or "")
        if not passages:
            continue
        vectors = await _embed_all(embedder, [passage for passage, _ in passages])
        if doc is None:
            doc = existing[url] = KnowledgeDocument(url=url, title="", category="")
            db.add(doc)
        else:
            await db.execute(delete(KnowledgeChunk).where(KnowledgeChunk.document_id == doc.id))
        doc.title = _CONTROL.sub("", row.get("title") or url)[:255]
        doc.category = _CONTROL.sub("", row.get("section") or "General")[:100]
        doc.kind, doc.source_sha256, doc.fetched_at = row.get("kind"), digest, _parse_time(row.get("fetched_at"))
        doc.is_active = True
        await db.flush()
        db.add_all(
            KnowledgeChunk(document_id=doc.id, chunk_index=i, chunk_text=passage, embedding=vector, metadata_json={"heading": heading})
            for i, ((passage, heading), vector) in enumerate(zip(passages, vectors))
        )
        await db.commit()
        stats.loaded += 1
        stats.chunks += len(passages)
    for url, doc in existing.items():
        if url not in seen_urls and doc.is_active:
            doc.is_active = False
            stats.deactivated += 1
    await db.commit()
    return stats


@dataclass
class Passage:
    chunk_id: str
    text: str
    title: str
    url: str
    section: str


_STOP = re.compile(r"[^a-z0-9]+")
MAX_PER_DOCUMENT = 2  # so one long page cannot fill every slot
PDF_WEIGHT = 0.7  # people and contacts live on web pages; the many syllabus PDFs would crowd them out
# Students say "CSE" and "HOD"; the pages spell them out.
_SHORT_FORMS = {
    "cse": "computer science and engineering", "ece": "electronics and communication engineering",
    "eee": "electrical and electronics engineering", "mech": "mechanical engineering", "hod": "head of the department",
    "hods": "head of the department", "coe": "controller of examinations", "mba": "business management",
}


def expand_short_forms(query: str) -> str:
    words = _STOP.split(query.lower())
    extra = [_SHORT_FORMS[w] for w in dict.fromkeys(words) if w in _SHORT_FORMS]
    if re.search(r"\bit (dept|department)\b", query.lower()):
        extra.append("information technology")
    return f"{query} {' '.join(extra)}" if extra else query


def _tsquery(query: str) -> str:
    """OR the words together: a long question rarely has every word in one passage."""
    words = dict.fromkeys(w for w in _STOP.split(query.lower()) if len(w) > 1)
    return " | ".join(words)


_ACTIVE = "d.is_active AND d.url IS NOT NULL"


async def _vector_ids(db: AsyncSession, query: str, limit: int = CANDIDATES) -> list:
    try:
        vector = await suggestion_service.get_embedder().embed(query)
    except Exception:
        logger.warning("Could not embed the question; using text search only", exc_info=True)
        return []
    rows = await db.execute(
        text(
            "SELECT c.id FROM knowledge_chunks c JOIN knowledge_documents d ON d.id = c.document_id "
            f"WHERE {_ACTIVE} AND c.embedding IS NOT NULL "
            "ORDER BY c.embedding <=> CAST(CAST(:v AS text) AS vector) LIMIT :n"
        ),
        {"v": suggestion_service._vector_text(vector), "n": limit},
    )
    return [row.id for row in rows]


async def _text_ids(db: AsyncSession, query: str, limit: int = CANDIDATES) -> list:
    ts = _tsquery(query)
    if not ts:
        return []
    rows = await db.execute(
        text(
            "SELECT c.id FROM knowledge_chunks c JOIN knowledge_documents d ON d.id = c.document_id, "
            "to_tsquery('english', :q) AS q "
            f"WHERE {_ACTIVE} AND c.search_vector @@ q ORDER BY ts_rank(c.search_vector, q, 1) DESC LIMIT :n"
        ),
        {"q": ts, "n": limit},
    )
    return [row.id for row in rows]


async def search(db: AsyncSession, query: str, k: int = 6) -> list[Passage]:
    """The k best passages for ``query``, best first (at most MAX_PER_DOCUMENT from one page)."""
    query = expand_short_forms(query)
    scores: dict = {}
    for ranked in (await _vector_ids(db, query), await _text_ids(db, query)):
        for rank, chunk_id in enumerate(ranked):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (RRF_K + rank + 1)
    if not scores:
        return []
    rows = await db.execute(
        select(
            KnowledgeChunk.id, KnowledgeChunk.chunk_text, KnowledgeDocument.id.label("doc_id"), KnowledgeDocument.title,
            KnowledgeDocument.url, KnowledgeDocument.category, KnowledgeDocument.kind,
        )
        .join(KnowledgeDocument, KnowledgeDocument.id == KnowledgeChunk.document_id)
        .where(KnowledgeChunk.id.in_(list(scores)))
    )
    by_id = {row.id: row for row in rows}
    for chunk_id, row in by_id.items():
        if row.kind == "pdf":
            scores[chunk_id] *= PDF_WEIGHT
    passages, per_document = [], {}
    for chunk_id in sorted(by_id, key=lambda chunk_id: -scores[chunk_id]):
        row = by_id[chunk_id]
        if per_document.get(row.doc_id, 0) >= MAX_PER_DOCUMENT:
            continue
        per_document[row.doc_id] = per_document.get(row.doc_id, 0) + 1
        passages.append(Passage(str(row.id), row.chunk_text, row.title, row.url, row.category))
        if len(passages) == k:
            break
    return passages
