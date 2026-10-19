"""The campus chat assistant: answers from the college website and proposes actions.

One model call per message. Everything the model proposes is checked here against the user's real
permissions and the sources actually found: the page runs an action only after a click, through
the normal ticket endpoints. Any model failure falls back to listing the best-matching pages.
"""

import asyncio
import logging
import re
import time
import uuid
from collections import deque
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ai.assistant_llm import GeminiAssistantService
from ai.interfaces import BaseAssistantService
from ai.keyword_service import match_category, match_priority
from ai.schemas import AssistantReply
from app.core import campus, permissions as policy
from app.core.config import settings
from app.core.exceptions import AppException
from app.models.enums import AuditActionEnum, PriorityEnum
from app.models.ticket import Ticket
from app.models.user import User
from app.schemas.assistant import (
    AddCommentAction, AssistantChatRequest, AssistantChatResponse, AssistantSource, ChatTurn,
    ContactAction, OpenLinkAction, ReportProblemAction, TicketAction,
)
from app.schemas.ticket import CATEGORY_VALUES, TicketFilter
from app.services import knowledge_service, ticket_service
from app.services.audit_service import record_audit

logger = logging.getLogger("app.assistant")

MAX_SOURCES = 6
MAX_TICKETS = 10
MAX_ACTIONS = 3
MAX_HISTORY_TURNS = 8
MAX_HISTORY_CHARS = 4000
FALLBACK_TEXT = "I can't write a full answer right now, but these parts of the college website look relevant:"
FALLBACK_NO_SOURCES = "I can't answer right now. Please try again in a moment."
RATE_LIMIT_TEXT = "You're sending messages quickly; try again in a minute"

_llm: Optional[BaseAssistantService] = None
_recent: dict[uuid.UUID, deque] = {}


def get_llm() -> Optional[BaseAssistantService]:
    global _llm
    if _llm is None and settings.GEMINI_API_KEY:
        _llm = GeminiAssistantService(
            settings.GEMINI_API_KEY, settings.GEMINI_MODEL, settings.ASSISTANT_TIMEOUT_SECONDS, places=[p.name for p in campus.PLACES]
        )
    return _llm if settings.GEMINI_API_KEY else None


def set_llm(service: Optional[BaseAssistantService]) -> None:
    global _llm
    _llm = service


def reset_rate_limits() -> None:
    _recent.clear()


def check_rate_limit(user: User) -> None:
    now = time.monotonic()
    stamps = _recent.setdefault(user.id, deque())
    while stamps and now - stamps[0] > 60:
        stamps.popleft()
    if len(stamps) >= settings.ASSISTANT_MESSAGES_PER_MINUTE:
        raise AppException(RATE_LIMIT_TEXT, 429, "RATE_LIMITED")
    stamps.append(now)


# ------------------------------------------------------------------ prompt inputs

def trim_history(history: list[ChatTurn]) -> list[dict]:
    """The newest turns that fit in the limits, oldest first."""
    kept, used = [], 0
    for turn in reversed(history[-MAX_HISTORY_TURNS:]):
        text = turn.text.strip()
        if not text or used + len(text) > MAX_HISTORY_CHARS:
            break
        kept.append({"role": turn.role, "text": text})
        used += len(text)
    return kept[::-1]


def _can(user: User, ticket: Ticket) -> list[str]:
    options = []
    if policy.can_confirm_resolution(user, ticket):
        options.append("confirm_fixed")
    if policy.can_reopen(user, ticket):
        options.append("reopen_ticket")
    if policy.can_withdraw(user, ticket):
        options.append("cancel_ticket")
    if policy.can_comment(user, ticket):
        options.append("add_comment")
    return options


async def _own_tickets(db: AsyncSession, user: User) -> list[Ticket]:
    """Only tickets this user reported: nobody else's ever reach the prompt or the actions."""
    tickets, _, _ = await ticket_service.list_tickets(db, user, TicketFilter(mine=True), 1, MAX_TICKETS)
    return [t for t in tickets if t.created_by == user.id]


def _ticket_lines(user: User, tickets: list[Ticket]) -> list[dict]:
    return [
        {"ticket_number": t.ticket_number, "title": t.title[:100], "status": t.status.replace("_", " ").lower(), "can": _can(user, t)}
        for t in tickets
    ]


# ------------------------------------------------------------------ checking the model's actions

def _digits(value: str) -> str:
    return re.sub(r"\D", "", value)


_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_PHONE = re.compile(r"\+?\d[\d\s\-()]{5,}\d")


def _published_emails(passages: list[knowledge_service.Passage]) -> set[str]:
    found = set()
    for passage in passages:
        found.update(m.lower() for m in _EMAIL.findall(re.sub(r"\s*@\s*", "@", passage.text)))  # the site writes "hod_cse @mvsrec.edu.in"
    return found


def _published_phones(passages: list[knowledge_service.Passage]) -> dict[str, str]:
    """Last 10 digits -> the number as the website writes it."""
    found: dict[str, str] = {}
    for passage in passages:
        for match in _PHONE.findall(passage.text):
            digits = _digits(match)
            if len(digits) >= 6:
                found.setdefault(digits[-10:], match.strip())
    return found


def _clean(value: object, limit: int) -> str:
    return " ".join(str(value or "").split())[:limit]


_ROOM = re.compile(r"\broom\s*(?:no\.?\s*)?[a-z]?-?\d{1,4}[a-z]?\b|\b(?:ground|\d{1,2}(?:st|nd|rd|th)|first|second|third|fourth)\s+floor\b", re.I)


def _location(proposed: object, message: str) -> str:
    """The model's location, or one read from the message: a known place first, then any room or floor it names."""
    location = _clean(proposed, 255)
    place = campus.match_place(message)
    if location:
        return campus.compose_location(place.name, location)[:255] if place and campus.match_place(location) is None else location
    detail = ", ".join(dict.fromkeys(m.group(0)[0].upper() + m.group(0)[1:] for m in _ROOM.finditer(message)))
    return campus.compose_location(place.name if place else "", detail)[:255]


def _category(proposed: object, *texts: str) -> str:
    """The model's category; the keyword rules when it is missing, invalid or just Other; Other only if nothing matches."""
    if proposed in CATEGORY_VALUES and proposed != "Other":
        return str(proposed)
    return match_category(" ".join(texts))[0]


def validate_actions(
    user: User, proposals: list[dict], passages: list[knowledge_service.Passage], tickets: list[Ticket], message: str
) -> list:
    emails, phones = _published_emails(passages), _published_phones(passages)
    urls = {p.url for p in passages}
    by_number = {t.ticket_number.upper(): t for t in tickets}
    actions: list = []
    for proposal in proposals:
        kind = proposal.get("type")
        action = None
        if kind == "report_problem":
            title = _clean(proposal.get("title"), 255) or _clean(message, 80)
            description = _clean(proposal.get("description"), 2000) or _clean(message, 2000)
            priority = str(proposal.get("priority") or "").upper()
            if len(title) >= 5 and len(description) >= 10:
                action = ReportProblemAction(
                    title=title, description=description,
                    category=_category(proposal.get("category"), title, description, message),
                    location=_location(proposal.get("location"), message),
                    priority=PriorityEnum(priority) if priority in PriorityEnum.__members__ else PriorityEnum.MEDIUM,
                )
        elif kind in ("confirm_fixed", "reopen_ticket", "cancel_ticket", "add_comment"):
            ticket = by_number.get(str(proposal.get("ticket_number") or "").strip().upper())
            if ticket is not None and kind in _can(user, ticket):
                if kind == "add_comment":
                    text = str(proposal.get("text") or "").strip()[:5000]
                    if text:
                        action = AddCommentAction(ticket_number=ticket.ticket_number, ticket_title=ticket.title, text=text)
                else:
                    action = TicketAction(type=kind, ticket_number=ticket.ticket_number, ticket_title=ticket.title)
        elif kind == "contact":
            email = re.sub(r"\s+", "", str(proposal.get("email") or "")).lower()
            phone_digits = _digits(str(proposal.get("phone") or ""))[-10:]
            email = email if email in emails else None
            phone = phones.get(phone_digits) if len(phone_digits) >= 6 else None
            if email or phone:
                action = ContactAction(label=_clean(proposal.get("label"), 80) or "Contact", email=email, phone=phone)
        elif kind == "open_link":
            url = str(proposal.get("url") or "").strip()
            if url in urls:
                action = OpenLinkAction(label=_clean(proposal.get("label"), 80) or "Open the page", url=url)
        if action is not None and action not in actions:
            actions.append(action)
    return actions[:MAX_ACTIONS]


_PROBLEM_CUES = re.compile(
    r"\b(broken|not working|isn'?t working|doesn'?t work|stopped working|out of order|damaged|crack\w*|leak\w*|overflow\w*|"
    r"dirty|smell\w*|spark\w*|flicker\w*|fault\w*|no (water|power|electricity|wifi|internet)|problem|complain\w*)\b",
    re.I,
)


def _looks_like_problem(message: str) -> bool:
    return bool(_PROBLEM_CUES.search(message))


def _fallback_report(message: str) -> Optional[ReportProblemAction]:
    """When the model is unavailable: a ready-to-edit report card if the message reads like a problem."""
    if not _looks_like_problem(message):
        return None
    text = _clean(message, 2000)
    return ReportProblemAction(
        title=text[:80] if len(text) >= 5 else "Problem on campus",
        description=text if len(text) >= 10 else f"{text} (sent from the assistant)",
        category=_category(None, message),
        location=_location("", message),
        priority=PriorityEnum(match_priority(message)[0]),
    )


# ------------------------------------------------------------------ chat

WRITE_ACTIONS = {"report_problem", "confirm_fixed", "reopen_ticket", "cancel_ticket", "add_comment"}
CLAIMED_DONE = re.compile(
    r"\bI(?: have|'ve)? (?:already )?(?:created|submitted|raised|filed|sent|logged|reopened|confirmed|cancelled|canceled|added)\b",
    re.IGNORECASE,
)


def _sources(passages: list[knowledge_service.Passage], numbers: list[int]) -> list[AssistantSource]:
    return [
        AssistantSource(n=n, title=passages[n - 1].title, url=passages[n - 1].url, section=passages[n - 1].section)
        for n in numbers
    ]


def _fallback(passages: list[knowledge_service.Passage], message: str) -> AssistantChatResponse:
    shown, seen = [], set()
    for n, passage in enumerate(passages, start=1):
        if passage.url not in seen and len(shown) < 3:
            seen.add(passage.url)
            shown.append(n)
    report = _fallback_report(message)
    return AssistantChatResponse(
        answer=FALLBACK_TEXT if shown else FALLBACK_NO_SOURCES,
        sources=_sources(passages, shown), actions=[report] if report else [], status="fallback",
    )


async def _ask(llm: BaseAssistantService, message: str, passages, tickets, history) -> Optional[AssistantReply]:
    sources = [{"n": n, "title": p.title, "url": p.url, "text": p.text} for n, p in enumerate(passages, start=1)]
    try:
        return await asyncio.wait_for(
            llm.reply(message, sources, tickets, history), timeout=settings.ASSISTANT_TIMEOUT_SECONDS + 2
        )
    except Exception as exc:  # timeouts, rate limits, bad replies: all fall back
        logger.warning("Assistant model failed (%s); showing sources only", exc or type(exc).__name__)
        return None


async def chat(db: AsyncSession, user: User, payload: AssistantChatRequest) -> AssistantChatResponse:
    check_rate_limit(user)
    message = payload.message.strip()
    history = trim_history(payload.history)
    previous = next((turn["text"] for turn in reversed(history) if turn["role"] == "user"), "")
    passages = (await knowledge_service.search(db, f"{message} {previous}".strip(), MAX_SOURCES))
    tickets = await _own_tickets(db, user)

    llm = get_llm()
    reply = await _ask(llm, message, passages, _ticket_lines(user, tickets), history) if llm else None
    if reply is None:
        response = _fallback(passages, message)
    else:
        actions = validate_actions(user, reply.actions, passages, tickets, message)
        answer = reply.answer[:3000]
        if any(action.type in WRITE_ACTIONS for action in actions):
            answer = CLAIMED_DONE.sub("I've prepared", answer)  # nothing happens until the person clicks
        # Show the sources the answer points to with [n]. Without markers, trust the cited list,
        # except when only an action was prepared (the model tends to cite unrelated passages then).
        marked = [int(n) for group in re.findall(r"\[([\d,\s]+)\]", answer) for n in re.findall(r"\d+", group)]
        wanted = marked or ([] if any(a.type in WRITE_ACTIONS for a in actions) else reply.cited)
        cited = [n for n in dict.fromkeys(wanted) if 1 <= n <= len(passages)]
        response = AssistantChatResponse(answer=answer, sources=_sources(passages, cited), actions=actions, status=reply.status)
    record_audit(
        db, user=user, action=AuditActionEnum.ASSISTANT_CHAT, entity_type="assistant_chat", entity_id=uuid.uuid4(),
        new_values={"message_length": len(message), "status": response.status},
    )
    await db.commit()
    return response
