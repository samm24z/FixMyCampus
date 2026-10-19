"""College website knowledge base: chunking, noise filter, loading, hybrid search (real PostgreSQL, fake embedder)."""

import pytest
from sqlalchemy import func, select

from app.core.database import AsyncSessionLocal
from app.models.knowledge import KnowledgeChunk, KnowledgeDocument
from app.services import knowledge_service
from app.services.knowledge_service import chunk_document, is_noise
from tests.helpers import FakeEmbedder


def page(url="https://mvsrec.edu.in/p1", title="Page One", text="## Page One\nHello there.", sha="a" * 64, **extra) -> dict:
    return {"url": url, "title": title, "kind": "html", "section": "General", "text": text, "sha256": sha, "fetched_at": "2026-10-19T09:00:00+00:00", **extra}


async def load(rows) -> knowledge_service.IngestStats:
    async with AsyncSessionLocal() as db:
        return await knowledge_service.ingest(db, rows, FakeEmbedder())


async def count(model, *where) -> int:
    async with AsyncSessionLocal() as db:
        return await db.scalar(select(func.count()).select_from(model).where(*where))


def test_chunks_start_with_title_section_and_heading():
    chunks = chunk_document("Exam Branch", "Examinations", "## Contact\nEmail: exambranch@mvsrec.edu.in\n## Fees\nPay online.")
    assert [heading for _, heading in chunks] == ["Contact", "Fees"]
    assert chunks[0][0].startswith("Exam Branch (Examinations):\nContact\nEmail: exambranch")


def test_table_header_is_repeated_in_every_chunk():
    rows = "\n".join(f"{i} | Person {i} | Professor | {'x' * 60}" for i in range(1, 40))
    chunks = chunk_document("Faculty", "Faculty", f"## Staff\nS.No. | Name | Designation | Notes\n{rows}")
    assert len(chunks) > 2
    assert all("S.No. | Name | Designation | Notes" in text for text, _ in chunks)
    assert all(len(text) < 900 for text, _ in chunks)


def test_long_lines_are_split_and_documents_are_capped():
    chunks = chunk_document("Long", "General", "word " * 2000)
    assert len(chunks) > 5 and all(len(text) < 900 for text, _ in chunks)
    many = "\n".join(f"line {i} " + "y" * 600 for i in range(400))
    assert len(chunk_document("Big", "Document", many)) == knowledge_service.MAX_CHUNKS_PER_DOCUMENT


@pytest.mark.parametrize("row", [
    {"title": "SIH2020 SOFTWARE PROBLEMS", "url": "https://mvsrec.edu.in/images/ED-Cell/SIH/2020/x.pdf", "text": "x" * 900},
    {"title": "17 18", "url": "https://mvsrec.edu.in/images/Computers/TechMag/17-18.pdf", "text": "x" * 900},
    {"title": "Coming soon", "url": "https://mvsrec.edu.in/a", "text": "x" * 900},
    {"title": "* * * Previous year Question Papers - Click Here * * *", "url": "https://mvsrec.edu.in/b", "text": "short"},
])
def test_noise_is_recognised(row):
    assert is_noise(row)


def test_real_pages_are_not_noise():
    assert not is_noise({"title": "Exam Branch", "url": "https://mvsrec.edu.in/exam", "text": "x" * 900})
    assert not is_noise({"title": "Click here to register", "url": "https://mvsrec.edu.in/alumni", "text": "x" * 5000})


async def test_loader_skips_noise_and_duplicates():
    stats = await load([
        page(),
        page(url="https://mvsrec.edu.in/p2", title="Same text", sha="a" * 64),
        page(url="https://mvsrec.edu.in/images/ED-Cell/SIH/2020/p.pdf", title="Problems", sha="b" * 64),
    ])
    assert (stats.loaded, stats.noise) == (1, 2)
    assert await count(KnowledgeDocument) == 1


async def test_loader_skips_unchanged_replaces_changed_and_switches_off_missing():
    first = await load([page(), page(url="https://mvsrec.edu.in/p2", title="Two", text="## Two\nSecond page.", sha="c" * 64)])
    assert (first.loaded, first.unchanged, first.chunks) == (2, 0, 2)

    again = await load([page(), page(url="https://mvsrec.edu.in/p2", title="Two", text="## Two\nSecond page.", sha="c" * 64)])
    assert (again.loaded, again.unchanged) == (0, 2)
    assert await count(KnowledgeChunk) == 2

    changed = await load([page(text="## Page One\nNew words about parking.", sha="d" * 64)])
    assert (changed.loaded, changed.unchanged, changed.deactivated) == (1, 0, 1)
    assert await count(KnowledgeChunk) == 2  # page one's single passage was replaced, not added
    async with AsyncSessionLocal() as db:
        texts = (await db.scalars(select(KnowledgeChunk.chunk_text))).all()
        two = await db.scalar(select(KnowledgeDocument).where(KnowledgeDocument.url == "https://mvsrec.edu.in/p2"))
    assert any("parking" in t for t in texts) and not any("Hello there" in t for t in texts)
    assert two.is_active is False


async def test_search_finds_a_name_by_full_text_and_a_paraphrase_by_vector():
    await load([
        page(url="https://mvsrec.edu.in/hod", title="CSE Head of the Department", sha="1" * 64,
             text="## Head\nName : Dr. Akhil Khare Designation : Professor & HOD Email : hod_cse @mvsrec.edu.in"),
        page(url="https://mvsrec.edu.in/bus", title="Transport", sha="2" * 64,
             text="## Buses\nCollege buses run from Secunderabad and Uppal every morning."),
        *[page(url=f"https://mvsrec.edu.in/n{i}", title=f"Notice {i}", sha=f"{i:064d}", text=f"## Notice\nHoliday notice number {i} for staff.") for i in range(5, 30)],
    ])
    async with AsyncSessionLocal() as db:
        by_name = await knowledge_service.search(db, "Akhil Khare")
        assert by_name[0].url == "https://mvsrec.edu.in/hod"
        assert (await knowledge_service._text_ids(db, "Akhil Khare")) and not await knowledge_service._text_ids(db, "the of")
        by_meaning = await knowledge_service.search(db, "Which morning buses go from Uppal?")
        assert by_meaning[0].url == "https://mvsrec.edu.in/bus"
        vector_only = await knowledge_service._vector_ids(db, "morning buses Uppal")
        assert vector_only
    top = by_name[0]
    assert top.title == "CSE Head of the Department" and top.section == "General" and "Akhil Khare" in top.text


async def test_search_ignores_switched_off_pages():
    await load([page(title="Parking", text="## Parking\nParking permits are issued at the gate.")])
    await load([])  # the page is gone from the file
    async with AsyncSessionLocal() as db:
        assert await knowledge_service.search(db, "parking permits") == []


def test_stray_control_characters_from_pdfs_are_removed():
    chunks = chunk_document("Pdf\x00 title", "Document", "Partnering since \x00 2016\x0006\x0022 done")
    assert all("\x00" not in text for text, _ in chunks) and "2016" in chunks[0][0]


def test_department_heads_are_listed_from_the_contact_page_and_faculty_tables():
    rows = [
        {"url": knowledge_service.CONTACT_PAGE, "title": "Contact Us", "text": "Contact Us\nHEAD OF THE DEPARTMENTS\n"
         "Prof.Namasivvaya , Head ECE Dept.\nPhone No: 9866692214\nEmail: hod_ece@mvsrec.edu.in\n"
         "Head IT Dept. Dr. A V Krishna Prasad\nPhone No: 9912111742\nEmail: hod_it@mvsrec.edu.in"},
        {"url": "https://data.mvsrec.edu.in/faculty/faculty.php?option=ECE", "title": "ECE faculty",
         "text": "1 | Er. Nuli Namassivaya | Associate Professor & HOD | M.Tech | B.E(ECE)"},
    ]
    entries = {row["url"].split("#")[1]: row for row in knowledge_service.department_head_rows(rows)}
    assert set(entries) == {"hod-ece", "hod-it", "hods"}
    ece = entries["hod-ece"]["text"]
    assert "Head of Department (HOD) of Electronics and Communication Engineering" in ece
    assert "Prof.Namasivvaya" in ece and "Er. Nuli Namassivaya" in ece and "9866692214" in ece and "hod_ece@mvsrec.edu.in" in ece
    assert "is Dr. A V Krishna Prasad." in entries["hod-it"]["text"]
