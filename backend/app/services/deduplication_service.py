"""Deduplication and grievance clustering service.

Provides real-time similarity detection, automatic duplicate linking upon ticket creation,
and administrative merging of duplicate complaints across campus blocks.
"""

import re
import uuid
from typing import List, Optional, Set
from uuid import UUID

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core import permissions as policy
from app.core.exceptions import ConflictException, ForbiddenException, NotFoundException
from app.models.enums import AuditActionEnum, TicketStatusEnum
from app.models.ticket import Ticket, TicketComment, TicketDuplicate, TicketStatusHistory
from app.models.user import User
from app.schemas.ticket_detail import (
    DuplicateCandidateResult,
    DuplicateClusterItem,
    MergedDuplicateReport,
    TicketDetailRead,
)
from app.services.audit_service import record_audit

STOPWORDS: Set[str] = {
    "a", "an", "the", "and", "or", "is", "are", "was", "were", "to", "in", "at",
    "of", "for", "on", "with", "by", "from", "it", "this", "that", "there", "has",
    "have", "had", "my", "our", "me", "we", "not", "no", "please", "kindly", "help",
    "working", "work", "works", "issue", "issues", "problem", "problems",
    "broken", "damage", "damaged", "repair", "repairs", "fix", "fixed",
    "room", "hall", "floor", "block", "dept", "department", "complaint", "student"
}


# Specific equipment and facility domain taxonomies to prevent cross-appliance false duplicates
EQUIPMENT_DOMAINS = {
    # AV / Presentation Display
    "projector": "av_display",
    "projecter": "av_display",
    "projecktor": "av_display",
    "screen": "av_display",
    "scrren": "av_display",
    "scren": "av_display",
    "display": "av_display",
    "monitor": "av_display",
    "hdmi": "av_display",
    "vga": "av_display",
    # Audio
    "speaker": "av_audio",
    "speakers": "av_audio",
    "mic": "av_audio",
    "microphone": "av_audio",
    "audio": "av_audio",
    # Ventilation & Air Cooling
    "fan": "cooling",
    "fans": "cooling",
    "cooler": "cooling",
    "coolers": "cooling",
    "ac": "cooling",
    "airconditioner": "cooling",
    "ventilation": "cooling",
    # Lighting & Electrical Wiring
    "light": "lighting",
    "lights": "lighting",
    "bulb": "lighting",
    "bulbs": "lighting",
    "tube": "lighting",
    "tubelight": "lighting",
    "tubelights": "lighting",
    "switch": "electrical_power",
    "socket": "electrical_power",
    "plug": "electrical_power",
    "wire": "electrical_power",
    "wiring": "electrical_power",
    # Network & Connectivity
    "wifi": "network",
    "wi": "network",
    "fi": "network",
    "internet": "network",
    "lan": "network",
    "router": "network",
    "ethernet": "network",
    "network": "network",
    # Water & Plumbing
    "water": "plumbing",
    "tap": "plumbing",
    "pipe": "plumbing",
    "leak": "plumbing",
    "leakage": "plumbing",
    "flush": "plumbing",
    "drain": "plumbing",
    "toilet": "plumbing",
    "washroom": "plumbing",
    "restroom": "plumbing",
    # Classroom Furniture
    "bench": "furniture",
    "benches": "furniture",
    "desk": "furniture",
    "desks": "furniture",
    "chair": "furniture",
    "chairs": "furniture",
    "table": "furniture",
    "tables": "furniture",
    "blackboard": "furniture",
    "board": "furniture",
}


# Common campus grievance synonym groups
SYNONYM_MAP = {
    "wifi": "internet", "wi": "internet", "fi": "internet", "network": "internet", "lan": "internet",
    "fan": "ventilation", "cooler": "cooling", "ac": "cooling",
    "pipe": "plumbing", "leak": "leakage", "water": "plumbing", "tap": "plumbing",
    "projector": "display", "screen": "display", "monitor": "display",
    "projecter": "display", "scrren": "display", "scren": "display", "projecktor": "display",
    "blinking": "flickering", "audio": "av", "speaker": "av", "mic": "av",
}


def _clean_tokens(text: str) -> Set[str]:
    """Extract lowercase alphanumeric tokens, replacing domain synonyms and skipping stopwords."""
    words = re.findall(r"[a-z0-9]+", text.lower())
    tokens = set()
    for w in words:
        if len(w) > 1 and w not in STOPWORDS:
            tokens.add(SYNONYM_MAP.get(w, w))
    return tokens


def _extract_domains(text: str) -> Set[str]:
    """Extract recognized equipment or infrastructure categories from complaint text."""
    words = re.findall(r"[a-z0-9]+", text.lower())
    domains = set()
    for w in words:
        if w in EQUIPMENT_DOMAINS:
            domains.add(EQUIPMENT_DOMAINS[w])
    return domains


def _trigrams(text: str) -> Set[str]:
    """Generate 3-character n-grams for typo-tolerant character-level matching."""
    cleaned = re.sub(r"\s+", " ", text.lower().strip())
    if len(cleaned) < 3:
        return {cleaned}
    return {cleaned[i : i + 3] for i in range(len(cleaned) - 2)}


def _jaccard(set_a: Set[str], set_b: Set[str]) -> float:
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union > 0 else 0.0


def extract_block_name(location: Optional[str]) -> str:
    """Normalize campus block or building identifiers (e.g., 'C Block', 'Science Block')."""
    if not location:
        return ""
    loc_lower = location.lower()
    # Match patterns like 'c block', 'block c', 'science block', 'library', 'a-105', 'hostel'
    match = re.search(r"\b([a-z0-9]+[\s\-]+block|block[\s\-]+[a-z0-9]+|science\s+block|library|hostel|cafeteria|[a-z]\-[0-9]{3}|cs[0-9]{3})\b", loc_lower)
    if match:
        return match.group(1).replace("-", " ").strip()
    return location.strip()


def extract_building_prefix(location: Optional[str]) -> str:
    """Extract common campus building/block or department prefix from room codes (e.g. 'cs205' -> 'cs', 'C-204' -> 'c')."""
    if not location:
        return ""
    loc_lower = location.lower().strip()
    m = re.search(r"\b([a-z]+)[\s\-_]*[0-9]{2,4}\b", loc_lower)
    if m:
        return m.group(1).lower()
    m2 = re.search(r"\b([a-z0-9]+)[\s\-]+block\b", loc_lower)
    if m2:
        return m2.group(1).lower()
    m3 = re.search(r"\bblock[\s\-]+([a-z0-9]+)\b", loc_lower)
    if m3:
        return m3.group(1).lower()
    return ""


def calculate_similarity(
    title1: str,
    desc1: str,
    loc1: Optional[str],
    cat1: Optional[str],
    title2: str,
    desc2: str,
    loc2: Optional[str],
    cat2: Optional[str],
) -> float:
    """Compute multi-factor similarity score between 0.0 and 1.0.

    Weights token overlap, n-gram character structure, block/location match,
    and category alignment. Explicitly rejects grievances with incompatible equipment domains.
    """
    # 0. Domain Conflict Check:
    # If both complaints specify recognized equipment/facility domains and have no overlap
    # (e.g., Projector/AV vs Fan/Cooling, or Fan vs Benches), they are distinct grievances.
    domains1 = _extract_domains(f"{title1} {desc1}")
    domains2 = _extract_domains(f"{title2} {desc2}")
    if domains1 and domains2 and domains1.isdisjoint(domains2):
        return 0.0

    # 1. Title similarity (Word Jaccard + Trigram Jaccard)
    title_word_sim = _jaccard(_clean_tokens(title1), _clean_tokens(title2))
    title_tri_sim = _jaccard(_trigrams(title1), _trigrams(title2))
    title_sim = (0.7 * title_word_sim) + (0.3 * title_tri_sim)

    # 2. Description similarity with cross-title fallback
    desc_clean1 = _clean_tokens(desc1)
    desc_clean2 = _clean_tokens(desc2)
    desc_word_sim = max(
        _jaccard(desc_clean1, desc_clean2),
        0.5 * _jaccard(_clean_tokens(title1), desc_clean2),
        0.5 * _jaccard(_clean_tokens(title2), desc_clean1),
    )
    desc_tri_sim = _jaccard(_trigrams(desc1), _trigrams(desc2))
    desc_sim = (0.7 * desc_word_sim) + (0.3 * desc_tri_sim)

    # 3. Location / Campus Block match
    loc_sim = 0.0
    if loc1 and loc2:
        block1 = extract_block_name(loc1)
        block2 = extract_block_name(loc2)
        prefix1 = extract_building_prefix(loc1)
        prefix2 = extract_building_prefix(loc2)

        if block1 and block2 and (block1 == block2 or (len(block1) > 2 and len(block2) > 2 and (block1 in block2 or block2 in block1))):
            loc_sim = 1.0
        elif prefix1 and prefix2 and prefix1 == prefix2:
            loc_sim = 0.85
        else:
            loc_tokens1 = _clean_tokens(loc1)
            loc_tokens2 = _clean_tokens(loc2)
            loc_sim = _jaccard(loc_tokens1, loc_tokens2)

    # 4. Category match & penalty for incompatible categories
    cat_sim = 0.0
    if cat1 and cat2:
        if cat1.strip().lower() == cat2.strip().lower():
            cat_sim = 1.0
        else:
            cat_sim = -0.25

    # Composite weighted score (35% title, 25% description, 25% location, 15% category)
    score = (0.35 * title_sim) + (0.25 * desc_sim) + (0.25 * loc_sim) + (0.15 * cat_sim)
    return round(min(max(score, 0.0), 1.0), 2)


async def find_duplicate_candidates(
    db: AsyncSession,
    title: str,
    description: str,
    category: Optional[str] = None,
    location: Optional[str] = None,
    exclude_ticket_id: Optional[UUID] = None,
    threshold: float = 0.40,
) -> List[DuplicateCandidateResult]:
    """Retrieve existing complaints that match the incoming grievance."""
    query = select(Ticket).options(selectinload(Ticket.creator)).where(
        Ticket.status.notin_([TicketStatusEnum.CLOSED.value])
    )
    if exclude_ticket_id:
        query = query.where(Ticket.id != exclude_ticket_id)

    rows = await db.scalars(query)
    candidates: List[DuplicateCandidateResult] = []

    for existing in rows.all():
        score = calculate_similarity(
            title, description, location, category,
            existing.title, existing.description, existing.location, existing.category,
        )
        if score >= threshold:
            candidates.append(
                DuplicateCandidateResult(
                    ticket_id=existing.id,
                    ticket_number=existing.ticket_number,
                    title=existing.title,
                    category=existing.category,
                    location=existing.location,
                    status=existing.status,
                    similarity_score=score,
                    reported_by_name=existing.creator.full_name,
                    created_at=existing.created_at,
                )
            )

    candidates.sort(key=lambda c: c.similarity_score, reverse=True)
    return candidates[:10]


async def auto_link_duplicates_on_create(db: AsyncSession, new_ticket: Ticket) -> List[TicketDuplicate]:
    """Detect and record potential duplicate relationships immediately when a ticket is created."""
    candidates = await find_duplicate_candidates(
        db,
        title=new_ticket.title,
        description=new_ticket.description,
        category=new_ticket.category,
        location=new_ticket.location,
        exclude_ticket_id=new_ticket.id,
        threshold=0.40,
    )
    links: List[TicketDuplicate] = []
    for candidate in candidates[:3]:
        # Check if already linked in either direction
        existing_link = await db.scalar(
            select(TicketDuplicate).where(
                or_(
                    (TicketDuplicate.primary_ticket_id == candidate.ticket_id) & (TicketDuplicate.duplicate_ticket_id == new_ticket.id),
                    (TicketDuplicate.primary_ticket_id == new_ticket.id) & (TicketDuplicate.duplicate_ticket_id == candidate.ticket_id),
                )
            )
        )
        if not existing_link:
            dup_record = TicketDuplicate(
                primary_ticket_id=candidate.ticket_id,
                duplicate_ticket_id=new_ticket.id,
                similarity_score=candidate.similarity_score,
                detected_by="AI_AUTO",
                is_verified=False,
            )
            db.add(dup_record)
            links.append(dup_record)
    if links:
        await db.flush()
    return links


async def ensure_active_duplicates_linked(db: AsyncSession, threshold: float = 0.40) -> int:
    """Scan all active non-closed grievances across students and link any matching candidates."""
    open_tickets = (
        await db.scalars(
            select(Ticket)
            .options(selectinload(Ticket.creator))
            .where(Ticket.status.notin_([TicketStatusEnum.CLOSED.value]))
            .order_by(Ticket.created_at.asc())
        )
    ).all()

    new_links_count = 0
    for i, primary in enumerate(open_tickets):
        for secondary in open_tickets[i + 1 :]:
            if primary.id == secondary.id:
                continue

            existing = await db.scalar(
                select(TicketDuplicate).where(
                    or_(
                        (TicketDuplicate.primary_ticket_id == primary.id) & (TicketDuplicate.duplicate_ticket_id == secondary.id),
                        (TicketDuplicate.primary_ticket_id == secondary.id) & (TicketDuplicate.duplicate_ticket_id == primary.id),
                    )
                )
            )
            if existing:
                continue

            score = calculate_similarity(
                primary.title, primary.description, primary.location, primary.category,
                secondary.title, secondary.description, secondary.location, secondary.category,
            )
            if score >= threshold:
                dup_record = TicketDuplicate(
                    primary_ticket_id=primary.id,
                    duplicate_ticket_id=secondary.id,
                    similarity_score=score,
                    detected_by="AI_AUTO",
                    is_verified=False,
                )
                db.add(dup_record)
                new_links_count += 1

    if new_links_count > 0:
        await db.commit()
    return new_links_count


async def merge_tickets(
    db: AsyncSession,
    admin_user: User,
    primary_ref: str,
    duplicate_refs: List[str],
    notes: Optional[str] = None,
) -> TicketDetailRead:
    """Merge duplicate student tickets into a primary ticket.

    1. Links records in ``ticket_duplicates`` with is_verified=True.
    2. Closes duplicate tickets with status remarks referencing the primary ticket.
    3. Adds audit records and system comments linking both tickets.
    """
    from app.services import ticket_service

    if not policy.can_triage(admin_user):
        raise ForbiddenException("Only administrators and coordinators can merge tickets.")

    primary_ticket = await ticket_service.get_ticket_for_user(db, admin_user, primary_ref, for_update=True)

    for dup_ref in duplicate_refs:
        if dup_ref == primary_ref or dup_ref == primary_ticket.ticket_number or str(primary_ticket.id) == dup_ref:
            continue
        duplicate_ticket = await ticket_service.get_ticket_for_user(db, admin_user, dup_ref, for_update=True)
        if duplicate_ticket.id == primary_ticket.id:
            continue

        # Compute similarity score
        score = calculate_similarity(
            primary_ticket.title, primary_ticket.description, primary_ticket.location, primary_ticket.category,
            duplicate_ticket.title, duplicate_ticket.description, duplicate_ticket.location, duplicate_ticket.category,
        )

        # Check existing duplicate record or create a new one
        existing_dup = await db.scalar(
            select(TicketDuplicate).where(
                TicketDuplicate.primary_ticket_id == primary_ticket.id,
                TicketDuplicate.duplicate_ticket_id == duplicate_ticket.id,
            )
        )
        if existing_dup:
            existing_dup.is_verified = True
            existing_dup.verified_by = admin_user.id
            existing_dup.similarity_score = max(existing_dup.similarity_score, score)
        else:
            db.add(
                TicketDuplicate(
                    primary_ticket_id=primary_ticket.id,
                    duplicate_ticket_id=duplicate_ticket.id,
                    similarity_score=score,
                    detected_by="ADMIN_MERGE",
                    verified_by=admin_user.id,
                    is_verified=True,
                )
            )

        # Transition duplicate ticket to CLOSED with clear remarks
        old_status = duplicate_ticket.status
        duplicate_ticket.status = TicketStatusEnum.CLOSED.value
        db.add(
            TicketStatusHistory(
                ticket_id=duplicate_ticket.id,
                changed_by=admin_user.id,
                from_status=old_status,
                to_status=TicketStatusEnum.CLOSED.value,
                remarks=f"Merged into primary ticket {primary_ticket.ticket_number} (Duplicate campus grievance).",
            )
        )

        # Add comment on primary ticket
        dup_creator_name = duplicate_ticket.creator.full_name if duplicate_ticket.creator else "Student"
        db.add(
            TicketComment(
                ticket_id=primary_ticket.id,
                user_id=admin_user.id,
                content=(
                    f"[Merged Duplicate] Linked ticket {duplicate_ticket.ticket_number} reported by "
                    f"{dup_creator_name} from {duplicate_ticket.location}. "
                    f"Original issue: '{duplicate_ticket.title}'."
                    + (f" Note: {notes}" if notes else "")
                ),
                is_internal=False,
            )
        )

        # Add comment on duplicate ticket
        db.add(
            TicketComment(
                ticket_id=duplicate_ticket.id,
                user_id=admin_user.id,
                content=(
                    f"[Consolidated Resolution] This complaint has been identified as a duplicate and merged into "
                    f"primary ticket {primary_ticket.ticket_number} ('{primary_ticket.title}'). "
                    f"All progress and resolution are managed on the primary ticket."
                ),
                is_internal=False,
            )
        )

        record_audit(
            db,
            user=admin_user,
            action=AuditActionEnum.UPDATE,
            entity_type="ticket_duplicate",
            entity_id=primary_ticket.id,
            new_values={
                "action": "MERGE_DUPLICATE",
                "primary": primary_ticket.ticket_number,
                "duplicate": duplicate_ticket.ticket_number,
            },
        )

    await db.commit()
    return await ticket_service._detail_after_commit(db, admin_user, primary_ticket.id)


async def unmerge_ticket(
    db: AsyncSession,
    admin_user: User,
    primary_ref: str,
    duplicate_ref: str,
) -> TicketDetailRead:
    """Detach a duplicate ticket from the primary ticket and reopen it."""
    from app.services import ticket_service

    if not policy.can_triage(admin_user):
        raise ForbiddenException("Only administrators and coordinators can unmerge tickets.")

    primary_ticket = await ticket_service.get_ticket_for_user(db, admin_user, primary_ref, for_update=True)
    duplicate_ticket = await ticket_service.get_ticket_for_user(db, admin_user, duplicate_ref, for_update=True)

    await db.execute(
        delete(TicketDuplicate).where(
            TicketDuplicate.primary_ticket_id == primary_ticket.id,
            TicketDuplicate.duplicate_ticket_id == duplicate_ticket.id,
        )
    )

    duplicate_ticket.status = TicketStatusEnum.UNDER_REVIEW.value
    db.add(
        TicketStatusHistory(
            ticket_id=duplicate_ticket.id,
            changed_by=admin_user.id,
            from_status=TicketStatusEnum.CLOSED.value,
            to_status=TicketStatusEnum.UNDER_REVIEW.value,
            remarks=f"Unmerged from primary ticket {primary_ticket.ticket_number}. Reopened for independent review.",
        )
    )

    record_audit(
        db,
        user=admin_user,
        action=AuditActionEnum.UPDATE,
        entity_type="ticket_duplicate",
        entity_id=primary_ticket.id,
        new_values={"action": "UNMERGE_DUPLICATE", "duplicate": duplicate_ticket.ticket_number},
    )

    await db.commit()
    return await ticket_service._detail_after_commit(db, admin_user, primary_ticket.id)


async def dismiss_duplicate_candidate(
    db: AsyncSession,
    user: User,
    primary_ref: str,
    duplicate_ref: str,
) -> TicketDetailRead:
    """Mark a suggested duplicate candidate pair as dismissed / not a duplicate."""
    from app.services import ticket_service

    if not policy.can_triage(user):
        raise ForbiddenException("Only administrators and coordinators can dismiss duplicate suggestions.")

    primary_ticket = await ticket_service.get_ticket_for_user(db, user, primary_ref, for_update=True)
    duplicate_ticket = await ticket_service.get_ticket_for_user(db, user, duplicate_ref, for_update=True)

    # Find the link in either direction
    dup_link = await db.scalar(
        select(TicketDuplicate).where(
            or_(
                (TicketDuplicate.primary_ticket_id == primary_ticket.id) & (TicketDuplicate.duplicate_ticket_id == duplicate_ticket.id),
                (TicketDuplicate.primary_ticket_id == duplicate_ticket.id) & (TicketDuplicate.duplicate_ticket_id == primary_ticket.id),
            )
        )
    )

    if dup_link:
        dup_link.detected_by = "DISMISSED"
        dup_link.is_verified = False
        dup_link.verified_by = user.id
    else:
        dup_link = TicketDuplicate(
            primary_ticket_id=primary_ticket.id,
            duplicate_ticket_id=duplicate_ticket.id,
            similarity_score=0.0,
            detected_by="DISMISSED",
            is_verified=False,
            verified_by=user.id,
        )
        db.add(dup_link)

    record_audit(
        db,
        user=user,
        action=AuditActionEnum.UPDATE,
        entity_type="ticket_duplicate",
        entity_id=primary_ticket.id,
        new_values={
            "action": "DISMISS_DUPLICATE_CANDIDATE",
            "primary": primary_ticket.ticket_number,
            "candidate": duplicate_ticket.ticket_number,
        },
    )

    await db.commit()
    return await ticket_service._detail_after_commit(db, user, primary_ticket.id)


async def get_duplicate_clusters(db: AsyncSession) -> List[DuplicateClusterItem]:
    """Retrieve consolidated issue clusters where multiple students raised reports across blocks."""
    # Ensure active duplicate pairs across students are detected and tracked
    await ensure_active_duplicates_linked(db, threshold=0.45)

    # Query all TicketDuplicate records
    q = select(TicketDuplicate).options(
        selectinload(TicketDuplicate.primary_ticket).selectinload(Ticket.creator),
        selectinload(TicketDuplicate.duplicate_ticket).selectinload(Ticket.creator),
    )
    duplicates = (await db.scalars(q)).all()

    # Group by primary ticket
    cluster_map: dict[UUID, dict] = {}

    for dup in duplicates:
        # Ignore explicitly dismissed pairs
        if dup.detected_by == "DISMISSED":
            continue

        primary = dup.primary_ticket
        duplicate = dup.duplicate_ticket
        if not primary or not duplicate:
            continue

        # If this is an unverified candidate, verify it still qualifies with domain conflict checks
        if not dup.is_verified:
            live_sim = calculate_similarity(
                primary.title, primary.description, primary.location, primary.category,
                duplicate.title, duplicate.description, duplicate.location, duplicate.category,
            )
            if live_sim <= 0.0 or live_sim < 0.40:
                # Obsolete/false candidate (e.g., fan vs projector) - auto-dismiss
                dup.detected_by = "DISMISSED"
                continue

        pid = primary.id
        if pid not in cluster_map:
            creator_name = primary.creator.full_name if primary.creator else "Student"
            cluster_map[pid] = {
                "primary": primary,
                "students": {creator_name},
                "locations": {primary.location},
                "merged": [],
                "pending": [],
            }

        dup_student_name = duplicate.creator.full_name if duplicate.creator else "Student"
        dup_student_email = duplicate.creator.email if duplicate.creator else ""
        cluster_map[pid]["students"].add(dup_student_name)
        if duplicate.location:
            cluster_map[pid]["locations"].add(duplicate.location)

        report = MergedDuplicateReport(
            ticket_id=duplicate.id,
            ticket_number=duplicate.ticket_number,
            student_id=duplicate.created_by,
            student_name=dup_student_name,
            student_email=dup_student_email,
            location=duplicate.location,
            title=duplicate.title,
            description=duplicate.description,
            similarity_score=dup.similarity_score,
            is_verified=dup.is_verified,
            created_at=duplicate.created_at,
        )

        if dup.is_verified:
            cluster_map[pid]["merged"].append(report)
        else:
            cluster_map[pid]["pending"].append(report)

    result: List[DuplicateClusterItem] = []
    for pid, data in cluster_map.items():
        primary = data["primary"]
        # Only return clusters that have either merged duplicates or pending duplicate candidates
        if not data["merged"] and not data["pending"]:
            continue
        result.append(
            DuplicateClusterItem(
                primary_ticket_id=primary.id,
                primary_ticket_number=primary.ticket_number,
                title=primary.title,
                description=primary.description,
                category=primary.category,
                priority=primary.priority,
                status=primary.status,
                location=primary.location,
                student_count=len(data["students"]),
                students=sorted(list(data["students"])),
                locations=sorted(list(data["locations"])),
                created_at=primary.created_at,
                merged_tickets=data["merged"],
                pending_candidates=data["pending"],
            )
        )

    # Commit any auto-dismissed obsolete candidates
    await db.commit()

    # Sort so issues with the most students affected appear first
    result.sort(key=lambda item: (item.student_count, len(item.merged_tickets) + len(item.pending_candidates)), reverse=True)
    return result
