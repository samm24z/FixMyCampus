"""Knowledge Document and Chunk models: the college website text the assistant answers from."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import Boolean, Computed, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin, UUIDMixin
from app.models.types import VectorType

if TYPE_CHECKING:
    from app.models.user import User


class KnowledgeDocument(Base, UUIDMixin, TimestampMixin):
    """One page or PDF of the college website. ``category`` holds its section."""

    __tablename__ = "knowledge_documents"

    title: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    category: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    file_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    file_checksum: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    url: Mapped[Optional[str]] = mapped_column(String(1000), unique=True, nullable=True)
    kind: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)  # "html" or "pdf"
    source_sha256: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    fetched_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    uploaded_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    uploader: Mapped[Optional["User"]] = relationship("User")
    chunks: Mapped[List["KnowledgeChunk"]] = relationship(
        "KnowledgeChunk", back_populates="document", cascade="all, delete-orphan"
    )


class KnowledgeChunk(Base, UUIDMixin, TimestampMixin):
    """A passage of a page, embedded for vector search and indexed for full-text search."""

    __tablename__ = "knowledge_chunks"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_documents.id", ondelete="CASCADE"), index=True, nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    
    # 384-dimensional vector embedding for pgvector cosine distance retrieval
    embedding: Mapped[Optional[List[float]]] = mapped_column(VectorType(384), nullable=True)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    search_vector: Mapped[Optional[str]] = mapped_column(
        TSVECTOR, Computed("to_tsvector('english', chunk_text)", persisted=True), nullable=True
    )

    # Relationships
    document: Mapped["KnowledgeDocument"] = relationship("KnowledgeDocument", back_populates="chunks")
