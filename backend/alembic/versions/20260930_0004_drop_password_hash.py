"""Drop users.password_hash: credentials now live in Supabase Auth.

``users.id`` is the Supabase Auth user id; this table keeps only the application profile
(role, department, active flag).

Revision ID: 20260930_0004
Revises: 20260929_0003
Create Date: 2026-09-30
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260930_0004"
down_revision: Union[str, None] = "20260929_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("users", "password_hash")


def downgrade() -> None:
    # Hashes cannot be recovered; restore the column so the old schema is valid again.
    op.add_column("users", sa.Column("password_hash", sa.String(255), nullable=False, server_default=""))
    op.alter_column("users", "password_hash", server_default=None)
