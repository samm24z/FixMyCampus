"""Suggested category, priority and department for new reports, and spotting repeat reports.

Everything here fails soft: a ticket is created whatever Gemini or the embedder do. A person
always makes the final choice; suggestions only pre-fill it (changes are audited as AI_OVERRIDE).
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from ai.embedding_service import MiniLMEmbedder
from ai.gemini_service import GeminiSuggestionService
from ai.interfaces import BaseEmbeddingService, BaseSuggestionService
from ai.keyword_service import KeywordSuggestionService
from ai.schemas import TicketSuggestion
from app.core import campus, permissions as policy
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.exceptions import ConflictException, ForbiddenException
from app.models.department import Category
from app.models.enums import PriorityEnum
from app.models.ticket import Ticket, TicketDuplicate
from app.models.user import User
from app.schemas.ticket import TicketTriageUpdate
from app.schemas.ticket_detail import TicketDetailRead
from app.services import group_service, ticket_service

logger = logging.getLogger("app.suggestions")

MAX_CANDIDATES = 5
_embedder: Optional[BaseEmbeddingService] = None
_gemini: Optional[BaseSuggestionService] = None


def get_embedder() -> BaseEmbeddingService:
    global _embedder
    if _embedder is None:
        _embedder = MiniLMEmbedder(settings.AI_EMBEDDING_MODEL)
    return _embedder


def set_embedder(embedder: Optional[BaseEmbeddingService]) -> None:
    global _embedder
    _embedder = embedder


def get_gemini() -> Optional[BaseSuggestionService]:
    global _gemini
    if _gemini is None and settings.GEMINI_API_KEY:
        _gemini = GeminiSuggestionService(settings.GEMINI_API_KEY, settings.GEMINI_MODEL, settings.GEMINI_TIMEOUT_SECONDS)
    return _gemini if settings.GEMINI_API_KEY else None


def set_gemini(service: Optional[BaseSuggestionService]) -> None:
    global _gemini
    _gemini = service


async def suggest(title: str, description: str, location: str) -> TicketSuggestion:
    """Gemini when it is configured and answers; the keyword rules otherwise."""
    gemini = get_gemini()
    if gemini is not None:
        try:
            return await asyncio.wait_for(
                gemini.suggest(title, description, location), timeout=settings.GEMINI_TIMEOUT_SECONDS + 2
            )
        except Exception as exc:  # timeouts, rate limits, bad replies: all fall back
            logger.warning("Gemini suggestion failed (%s); using keyword rules", exc or type(exc).__name__)
    return await KeywordSuggestionService().suggest(title, description, location)


def _vector_text(vector: list[float]) -> str:
    return "[" + ",".join(f"{x:.6f}" for x in vector) + "]"


async def analyze_ticket(ticket_id: UUID) -> None:
    """Fill in suggestions and look for repeat reports. Runs after the response is sent; never raises."""
    if not (settings.AI_SUGGESTIONS_ENABLED or settings.AI_EMBEDDINGS_ENABLED):
        return
    try:
        async with AsyncSessionLocal() as db:
            vector = await _save_suggestions(db, ticket_id)
            if vector:
                try:
                    await _group_similar(db, ticket_id, vector)
                except Exception:
                    await db.rollback()
                    logger.exception("Looking for repeat reports failed for %s", ticket_id)
    except Exception:
        logger.exception("Analysing ticket %s failed", ticket_id)
        await _mark_failed(ticket_id)


async def _mark_failed(ticket_id: UUID) -> None:
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(update(Ticket).where(Ticket.id == ticket_id).values(ai_status="failed"))
            await db.commit()
    except Exception:
        logger.exception("Could not record the failure for %s", ticket_id)


async def _save_suggestions(db: AsyncSession, ticket_id: UUID) -> Optional[list[float]]:
    """Store suggestions and the embedding; returns the embedding (None if it could not be made)."""
    ticket = await db.get(Ticket, ticket_id)
    if ticket is None:
        return None
    if settings.AI_SUGGESTIONS_ENABLED:
        suggestion = await suggest(ticket.title, ticket.description, ticket.location)
        ticket.suggested_category = suggestion.category
        ticket.suggested_priority = suggestion.priority
        ticket.suggested_department_id = await db.scalar(
            select(Category.default_department_id).where(Category.name == suggestion.category)
        )
        ticket.ai_confidence, ticket.ai_reason, ticket.ai_source = suggestion.confidence, suggestion.reason, suggestion.source
        ticket.ai_status, ticket.ai_analyzed_at = "done", datetime.now(timezone.utc)
    vector = None
    if settings.AI_EMBEDDINGS_ENABLED:
        try:
            vector = await get_embedder().embed(f"{ticket.title}. {ticket.description} {ticket.location}")
        except Exception:
            logger.warning("Could not embed ticket %s; skipping repeat-report check", ticket_id, exc_info=True)
    if vector:
        await db.execute(
            text("UPDATE tickets SET embedding = CAST(CAST(:v AS text) AS vector) WHERE id = :id"),
            {"v": _vector_text(vector), "id": ticket_id},
        )
    await db.commit()
    return vector


async def _group_similar(db: AsyncSession, ticket_id: UUID, vector: list[float]) -> None:
    """List open tickets that look like this one; join the main ticket when one is nearly identical."""
    rows = (await db.execute(
        text(
            "SELECT id, 1 - (embedding <=> CAST(CAST(:v AS text) AS vector)) AS similarity FROM tickets "
            "WHERE id <> :id AND embedding IS NOT NULL AND status NOT IN ('RESOLVED', 'CLOSED') "
            "ORDER BY embedding <=> CAST(CAST(:v AS text) AS vector) LIMIT 15"
        ),
        {"v": _vector_text(vector), "id": ticket_id},
    )).all()
    similar = {row.id: float(row.similarity) for row in rows if row.similarity >= settings.AI_SIMILARITY_THRESHOLD}
    if not similar:
        return
    ticket = await db.scalar(
        select(Ticket).where(Ticket.id == ticket_id).with_for_update().execution_options(populate_existing=True)
    )
    others = {t.id: t for t in (await db.scalars(select(Ticket).where(Ticket.id.in_(similar)))).all()}
    own_group = ticket.parent_ticket_id or ticket.id
    best: Optional[tuple[Ticket, TicketDuplicate, float]] = None
    kept = 0
    for other_id, similarity in sorted(similar.items(), key=lambda item: -item[1]):
        other = others.get(other_id)
        if other is None or (other.parent_ticket_id or other.id) == own_group or kept >= MAX_CANDIDATES:
            continue
        older, newer = sorted((ticket, other), key=lambda t: (t.created_at, str(t.id)))
        link = await group_service.find_link(db, older.id, newer.id)
        if link is None:
            link = TicketDuplicate(
                primary_ticket_id=older.id, duplicate_ticket_id=newer.id, similarity_score=similarity,
                detected_by="AI_AUTO", is_verified=False,
            )
            db.add(link)
        elif not group_service.is_reviewed(link):
            link.similarity_score = similarity
        else:
            continue
        kept += 1
        # Same wording in a different place may be a different problem: those go to a coordinator.
        if (best is None and older is other and similarity >= settings.AI_AUTO_GROUP_THRESHOLD
                and campus.same_place(ticket.location, other.location)):
            best = (other, link, similarity)
    await db.flush()
    standalone = ticket.parent_ticket_id is None and ticket.report_count == 1
    if best and standalone and ticket.status in policy.GROUPABLE_STATUSES:
        main, link, similarity = best
        await group_service.join_group(db, ticket, main, None, link=link, similarity=similarity)
    await db.commit()


async def request_refresh(db: AsyncSession, user: User, ticket_ref: str) -> TicketDetailRead:
    """Mark the suggestions as being redone; the route then runs ``analyze_ticket`` in the background."""
    ticket = await ticket_service.get_ticket_for_user(db, user, ticket_ref, for_update=True)
    if not policy.can_review_suggestions(user):
        raise ForbiddenException("Only coordinators and admins can refresh suggestions")
    if not (settings.AI_SUGGESTIONS_ENABLED or settings.AI_EMBEDDINGS_ENABLED):
        raise ConflictException("Suggestions are turned off")
    ticket.ai_status = "pending"
    await db.commit()
    return await ticket_service._detail_after_commit(db, user, ticket.id)


async def accept_suggestions(db: AsyncSession, user: User, ticket_ref: str) -> TicketDetailRead:
    """Apply the suggested category, priority and department the same way a coordinator's edit would."""
    ticket = await ticket_service.get_ticket_for_user(db, user, ticket_ref)
    if not policy.can_review_suggestions(user):
        raise ForbiddenException("Only coordinators and admins can use suggestions")
    if ticket.ai_status != "done" or not ticket.suggested_category:
        raise ConflictException("There are no suggestions to use yet")
    changes: dict = {"category": ticket.suggested_category}
    if ticket.suggested_priority:
        changes["priority"] = PriorityEnum(ticket.suggested_priority)
    if ticket.suggested_department_id:
        changes["confirmed_department_id"] = ticket.suggested_department_id
    return await ticket_service.update_triage(db, user, ticket_ref, TicketTriageUpdate(**changes))
