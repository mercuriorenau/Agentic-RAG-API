"""Add page_number to chunks.

Revision ID: 003_chunk_page
Revises: 002_chats
Create Date: 2026-07-19
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "003_chunk_page"
down_revision: str | None = "002_chats"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("chunks", sa.Column("page_number", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("chunks", "page_number")
