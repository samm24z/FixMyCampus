"""College website knowledge base: page details, full-text search, vector index.

Revision ID: 20261019_0007
Revises: 20261019_0006
Create Date: 2026-10-19
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20261019_0007"
down_revision: Union[str, None] = "20261019_0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("knowledge_documents", sa.Column("url", sa.String(1000), nullable=True))
    op.add_column("knowledge_documents", sa.Column("kind", sa.String(10), nullable=True))
    op.add_column("knowledge_documents", sa.Column("source_sha256", sa.String(64), nullable=True))
    op.add_column("knowledge_documents", sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True))
    op.create_unique_constraint("uq_knowledge_documents_url", "knowledge_documents", ["url"])
    op.execute(
        "ALTER TABLE knowledge_chunks ADD COLUMN search_vector tsvector "
        "GENERATED ALWAYS AS (to_tsvector('english', chunk_text)) STORED"
    )
    op.execute("CREATE INDEX ix_knowledge_chunks_search_vector ON knowledge_chunks USING gin (search_vector)")
    op.execute("CREATE INDEX ix_knowledge_chunks_embedding_hnsw ON knowledge_chunks USING hnsw (embedding vector_cosine_ops)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_knowledge_chunks_embedding_hnsw")
    op.execute("DROP INDEX IF EXISTS ix_knowledge_chunks_search_vector")
    op.drop_column("knowledge_chunks", "search_vector")
    op.drop_constraint("uq_knowledge_documents_url", "knowledge_documents", type_="unique")
    for column in ("fetched_at", "source_sha256", "kind", "url"):
        op.drop_column("knowledge_documents", column)
