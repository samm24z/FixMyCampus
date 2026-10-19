"""Collect the public text of mvsrec.edu.in for the chatbot's knowledge base.

Reads the college website politely (robots.txt, one request a second, a clear user
agent), keeps each page's main text with headings, lists and tables, and pulls the text
out of PDFs the site links to. Faculty tables on data.mvsrec.edu.in are included.

Usage from the backend directory:
    python scripts/crawl_college_site.py --out ../data/knowledge/mvsrec

Writes ``pages.jsonl`` (one document per line) and ``crawl_report.md``. Rerun to refresh.
"""

import argparse
import hashlib
import html as htmllib
import io
import json
import re
import sys
import time
from collections import Counter, deque
from datetime import datetime, timezone
from pathlib import Path
from urllib import robotparser
from urllib.parse import parse_qs, urlencode, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup, NavigableString, Tag
from pypdf import PdfReader

MAIN_HOST = "mvsrec.edu.in"
DATA_HOST = "data.mvsrec.edu.in"
START = f"https://{MAIN_HOST}/"
USER_AGENT = "FixMyCampus-knowledge-crawler/1.0 (MVSR student capstone project; polite, 1 req/s)"
# data.mvsrec.edu.in is mostly reports and course outcomes; only the faculty lists help students.
DATA_PAGES = re.compile(r"^/faculty/faculty\.php$")
SKIP_PARAMS = {"option": {"com_users", "com_mailto", "com_search", "com_contact"}, "tmpl": {"component"},
               "format": {"pdf", "feed", "raw"}, "print": {"1"}, "task": None}
SKIP_EXTENSIONS = (".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".zip", ".rar", ".doc", ".docx",
                   ".xls", ".xlsx", ".ppt", ".pptx", ".mp4", ".mp3", ".css", ".js", ".ico")
MIN_TEXT = 80


def normalise(url: str) -> str | None:
    """One canonical URL per page, or None when it should not be crawled."""
    parts = urlparse(url)
    if parts.scheme not in ("http", "https"):
        return None
    host = parts.netloc.lower().removeprefix("www.")
    path = re.sub(r"/{2,}", "/", parts.path or "/").replace("\\", "/")
    if host not in (MAIN_HOST, DATA_HOST) or path.lower().endswith(SKIP_EXTENSIONS):
        return None
    query = parse_qs(parts.query)
    for key, bad in SKIP_PARAMS.items():
        if key in query and (bad is None or set(query[key]) & bad):
            return None
    if host == DATA_HOST and not DATA_PAGES.match(path):
        return None
    query.pop("Itemid", None)  # Joomla menu position: same article, different id
    clean = urlencode(sorted((k, v[0]) for k, v in query.items()))
    return f"https://{host}{path}" + (f"?{clean}" if clean else "")


def is_pdf(url: str) -> bool:
    return urlparse(url).path.lower().endswith(".pdf")


def tidy(text: str) -> str:
    return " ".join(text.replace("\xa0", " ").split())


def table_lines(table: Tag) -> list[str]:
    lines = []
    for row in table.find_all("tr"):
        cells = [tidy(cell.get_text(" ")) for cell in row.find_all(["th", "td"])]
        cells = [c for c in cells if c]
        if cells:
            lines.append(" | ".join(cells))
    return lines


def block_text(node: Tag) -> list[str]:
    """Headings, paragraphs, lists and tables as plain lines, in reading order."""
    lines: list[str] = []
    for child in node.children:
        if isinstance(child, NavigableString):
            if tidy(child):
                lines.append(tidy(child))
            continue
        if not isinstance(child, Tag) or child.name in ("script", "style", "noscript", "form", "nav", "iframe"):
            continue
        if child.name == "table":
            lines.extend(table_lines(child))
        elif child.name in ("h1", "h2", "h3", "h4", "h5", "h6"):
            if tidy(child.get_text(" ")):
                lines.append("## " + tidy(child.get_text(" ")))
        elif child.name == "li":
            if tidy(child.get_text(" ")):
                lines.append("- " + tidy(child.get_text(" ")))
        elif child.find(["table", "h1", "h2", "h3", "h4", "li", "p", "div"]):
            lines.extend(block_text(child))
        elif tidy(child.get_text(" ")):
            lines.append(tidy(child.get_text(" ")))
    return lines


def uncloak_emails(soup: BeautifulSoup) -> None:
    """Joomla hides addresses behind a script; put the real address back as text."""
    for span in soup.select("span[id^=cloak]"):
        script = span.find_next_sibling("script")
        match = re.search(r"var addy_text\w*\s*=\s*((?:'[^']*'\s*\+?\s*)+)", script.string or "") if script else None
        if match:
            span.replace_with(htmllib.unescape("".join(re.findall(r"'([^']*)'", match.group(1)))))
            script.decompose()


def pick_title(lines: list[str], fallback: str) -> str:
    heading = next((line[3:] for line in lines if line.startswith("## ")), None)
    first = next((line for line in lines if len(re.findall(r"[A-Za-z]", line)) >= 3), None)
    title = heading or first or fallback
    return title[:100].rstrip(" :-") or fallback


def extract_html(url: str, html: str) -> tuple[str, str, list[str]]:
    soup = BeautifulSoup(html, "html.parser")
    uncloak_emails(soup)
    links = [a["href"] for a in soup.find_all("a", href=True)]
    main = (soup.select_one("article.uk-article") or soup.select_one(".tm-article-content")
            or soup.select_one(".tm-main") or soup.body or soup)
    lines, seen = [], set()
    for line in block_text(main):
        if line not in seen and not re.fullmatch(r"[-–—\s|>×*]+", line):
            seen.add(line)
            lines.append(line)
    page_title = tidy(soup.title.get_text()) if soup.title else url
    return pick_title(lines, page_title), "\n".join(lines), links


def extract_pdf(data: bytes) -> tuple[str, int]:
    reader = PdfReader(io.BytesIO(data))
    pages = [tidy(page.extract_text() or "") for page in reader.pages[:60]]
    return "\n".join(p for p in pages if p), len(reader.pages)


def section_of(url: str, title: str) -> str:
    if DATA_HOST in url:
        return "Faculty"
    if is_pdf(url):
        return "Document"
    words = title.lower()
    for name, keys in [
        ("Departments", ("department", "hod", "laborator", "faculty", "cse", "ece", "eee", "civil", "mechanical", "automobile", "mba")),
        ("Admissions & Fees", ("admission", "fee", "eligib", "scholarship")),
        ("Examinations & Academics", ("exam", "syllabus", "calendar", "question paper", "result", "academic")),
        ("Facilities", ("hostel", "transport", "library", "canteen", "health", "computer center", "sports")),
        ("Committees & Welfare", ("committee", "ragging", "grievance", "women", "welfare", "cell", "nss", "ncc", "club")),
        ("Placements", ("placement", "internship", "compan", "training")),
        ("About & Administration", ("about", "vision", "mission", "principal", "chairman", "society", "governing", "profile", "contact")),
    ]:
        if any(k in words for k in keys):
            return name
    return "General"


def crawl(out: Path, max_pages: int, max_pdfs: int, max_pdf_mb: int, delay: float) -> None:
    out.mkdir(parents=True, exist_ok=True)
    robots = robotparser.RobotFileParser(f"https://{MAIN_HOST}/robots.txt")
    robots.read()
    queue, queued = deque([START]), {normalise(START)}
    docs, failures, empty, hashes = [], [], [], set()
    fetched = pdfs = 0
    started = time.time()
    with httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=25, follow_redirects=True) as client:
        while queue and fetched < max_pages:
            url = queue.popleft()
            if MAIN_HOST in urlparse(url).netloc and DATA_HOST not in url and not robots.can_fetch(USER_AGENT, url):
                continue
            if is_pdf(url):
                if pdfs >= max_pdfs:
                    continue
                pdfs += 1
            time.sleep(delay)
            fetched += 1
            try:
                response = client.get(url)
                response.raise_for_status()
            except httpx.HTTPError as exc:
                failures.append((url, type(exc).__name__))
                continue
            kind = "pdf" if is_pdf(url) or "pdf" in response.headers.get("content-type", "") else "html"
            try:
                if kind == "pdf":
                    if len(response.content) > max_pdf_mb * 1024 * 1024:
                        failures.append((url, "too large"))
                        continue
                    text, page_count = extract_pdf(response.content)
                    title = Path(urlparse(url).path).stem.replace("-", " ").replace("_", " ")
                    links = []
                else:
                    if "html" not in response.headers.get("content-type", "html"):
                        continue
                    title, text, links = extract_html(url, response.text)
                    page_count = None
            except Exception as exc:  # a broken page or PDF must not stop the crawl
                failures.append((url, f"unreadable: {type(exc).__name__}"))
                continue
            for href in links:
                target = normalise(urljoin(str(response.url), href.strip()))
                if target and target not in queued:
                    queued.add(target)
                    queue.append(target)
            if len(text) < MIN_TEXT:
                empty.append((url, title, kind))
                continue
            digest = hashlib.sha256(text.encode()).hexdigest()
            if digest in hashes:
                continue
            hashes.add(digest)
            docs.append({
                "url": url, "title": title, "kind": kind, "section": section_of(url, title),
                "text": text, "chars": len(text), "pdf_pages": page_count,
                "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "sha256": digest,
            })
            if fetched % 25 == 0:
                print(f"{fetched} fetched, {len(docs)} kept, {len(queue)} queued", flush=True)

    with open(out / "pages.jsonl", "w", encoding="utf-8") as f:
        for doc in docs:
            f.write(json.dumps(doc, ensure_ascii=False) + "\n")
    write_report(out, docs, failures, empty, fetched, len(queue), time.time() - started)
    print(f"Done: {len(docs)} documents ({sum(d['chars'] for d in docs):,} characters) from {fetched} requests.")


def write_report(out: Path, docs, failures, empty, fetched, left, seconds) -> None:
    by_section = Counter(d["section"] for d in docs)
    lines = [
        "# mvsrec.edu.in knowledge base: crawl report", "",
        f"- Crawled: {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC in {seconds / 60:.0f} min ({fetched} requests, {left} links not visited)",
        f"- Kept: {len(docs)} documents, {sum(d['chars'] for d in docs):,} characters "
        f"({sum(d['kind'] == 'html' for d in docs)} pages, {sum(d['kind'] == 'pdf' for d in docs)} PDFs)",
        f"- Skipped as empty or near-empty (images, scanned PDFs, link lists): {len(empty)}",
        f"- Failed: {len(failures)}", "", "## Documents by section", "",
        "| Section | Documents | Characters |", "| --- | --- | --- |",
    ]
    for section, count in by_section.most_common():
        lines.append(f"| {section} | {count} | {sum(d['chars'] for d in docs if d['section'] == section):,} |")
    lines += ["", "## Documents", "", "| Section | Title | Kind | Characters | URL |", "| --- | --- | --- | --- | --- |"]
    for d in sorted(docs, key=lambda d: (d["section"], d["title"].lower())):
        lines.append(f"| {d['section']} | {d['title'][:70].replace('|', '/')} | {d['kind']} | {d['chars']:,} | {d['url']} |")
    lines += ["", "## Empty or image-only (no usable text)", ""]
    lines += [f"- {kind}: {title[:70]} ({url})" for url, title, kind in empty] or ["- none"]
    lines += ["", "## Failed", ""]
    lines += [f"- {url}: {why}" for url, why in failures] or ["- none"]
    (out / "crawl_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, default=Path("../data/knowledge/mvsrec"))
    parser.add_argument("--max-pages", type=int, default=700)
    parser.add_argument("--max-pdfs", type=int, default=120)
    parser.add_argument("--max-pdf-mb", type=int, default=20)
    parser.add_argument("--delay", type=float, default=1.0, help="seconds between requests")
    args = parser.parse_args()
    try:
        crawl(args.out, args.max_pages, args.max_pdfs, args.max_pdf_mb, args.delay)
    except KeyboardInterrupt:
        sys.exit("Stopped.")
