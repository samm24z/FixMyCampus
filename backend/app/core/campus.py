"""The MVSR campus layout: the one list of places the app, the chatbot and the campus guide all use.

To add detail later (classrooms, labs, floors), add places here or extend ``description`` and ``aliases``.
Only put facts the college has confirmed: the chatbot repeats them.
"""

import re
from dataclasses import dataclass
from typing import Optional

BLOCK, FACILITY = "block", "facility"


@dataclass(frozen=True)
class Place:
    key: str
    name: str
    kind: str
    description: str
    aliases: tuple[str, ...] = ()


PLACES: tuple[Place, ...] = (
    Place(
        "as-block", "AS&H Block (First-year block)", BLOCK,
        "The AS&H Block (Applied Sciences and Humanities), also called the First-year block, has two buildings: AS1 and AS2. "
        "All first-year students, of every branch, have their classes here.",
        ("as&h block", "as&h", "s&h block", "ash block", "first year block", "first-year block", "first year building",
         "applied sciences and humanities"),
    ),
    Place(
        "as1", "AS1", BLOCK,
        "AS1 is one of the two buildings of the AS&H Block (the First-year block). "
        "First-year students of every branch have their classes in the AS&H Block.",
        ("as1", "as-1", "as 1"),
    ),
    Place(
        "as2", "AS2 (Exam Branch)", BLOCK,
        "AS2 is the other building of the AS&H Block (the First-year block), and is also known as the Exam Branch. "
        "Most student exams are held here, and the other exam- and marks-related offices are here too.",
        ("as2", "as-2", "as 2", "exam branch", "examination branch"),
    ),
    Place(
        "cse-block", "CSE Block", BLOCK,
        "CSE and the CSE-Allied branches (AIML, IoT, DS and CSIT) have their classes in the CSE Block.",
        ("cse block", "cse building", "computer science block"),
    ),
    Place(
        "mechanical-block", "Mechanical Block", BLOCK,
        "Mechanical Engineering and Electrical (EEE) students have their classes in the Mechanical Block.",
        ("mechanical block", "mech block", "mechanical building", "eee block", "electrical block"),
    ),
    Place(
        "civil-block", "Civil Block", BLOCK,
        "Civil Engineering and Information Technology (IT) students have their classes in the Civil Block. "
        "It is also the main administrative block, with the Principal's office. MBA and M.Tech students also have their classes here.",
        ("civil block", "civil building", "it block", "admin block", "administrative block", "administration block",
         "principal's office", "principal office", "mba block", "m.tech block"),
    ),
    Place(
        "ece-block", "ECE Block", BLOCK,
        "ECE students have their classes in the ECE Block.",
        ("ece block", "ece building", "electronics block"),
    ),
    Place("canteen", "Canteen", FACILITY, "The campus canteen. The Indoor Sports Room is on top of the canteen building.", ("canteen", "cafeteria")),
    Place("library", "Library", FACILITY, "The college library.", ("library",)),
    Place("placement-cell", "Placement Cell", FACILITY, "The college Placement Cell.", ("placement cell",)),
    Place("ground", "Ground (Playground)", FACILITY, "The campus playground.", ("playground", "play ground", "sports ground")),
    Place("basketball-ground", "Basketball Ground", FACILITY, "The campus basketball ground.", ("basketball ground", "basketball court", "basketball")),
    Place("parking-area", "Parking Area", FACILITY, "The campus parking area.", ("parking area", "parking lot", "parking")),
    Place(
        "indoor-sports-room", "Indoor Sports Room", FACILITY,
        "The Indoor Sports Room is on top of the canteen building.",
        ("indoor sports room", "indoor sports"),
    ),
    Place("boys-hostel", "Boys' Hostel", FACILITY, "The college hostel for boys.", ("boys hostel", "boys' hostel")),
    Place("girls-hostel", "Girls' Hostel", FACILITY, "The college hostel for girls.", ("girls hostel", "girls' hostel")),
)


def _normal(text: str) -> str:
    """Lower case, one kind of apostrophe removed, so "Principal’s office" and "principals office" agree."""
    return " ".join(re.sub(r"['’`]", "", text.lower()).split())


def _pattern(term: str) -> re.Pattern:
    return re.compile(rf"(?<![a-z0-9]){re.escape(_normal(term))}(?![a-z0-9])")


_TERMS: list[tuple[re.Pattern, int, Place]] = sorted(
    ((_pattern(term), len(_normal(term)), place) for place in PLACES for term in (place.name, *place.aliases)),
    key=lambda item: -item[1],
)


def match_place(text: str) -> Optional[Place]:
    """The place a free text names by its name or an alias; the longest match wins."""
    text = _normal(text)
    best, best_length = None, 0
    for pattern, length, place in _TERMS:
        if length > best_length and pattern.search(text):
            best, best_length = place, length
    return best


def same_place(first: str, second: str) -> bool:
    """Whether two ticket locations are the same campus place (automatic grouping needs this)."""
    a, b = match_place(first or ""), match_place(second or "")
    if a or b:
        return a is not None and b is not None and a.key == b.key
    return bool(_normal(first or "")) and _normal(first or "") == _normal(second or "")


def compose_location(place_name: str, detail: str = "") -> str:
    """"CSE Block, Room 204", or just "CSE Block"."""
    return ", ".join(part for part in (place_name.strip(), detail.strip()) if part)
