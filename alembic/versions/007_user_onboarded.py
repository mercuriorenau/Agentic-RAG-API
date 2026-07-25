"""Track whether a user has seen the first-visit walkthrough.

Revision ID: 007_user_onboarded
Revises: 006_pending_reset
Create Date: 2026-07-25
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "007_user_onboarded"
down_revision: str | None = "006_pending_reset"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "onboarded",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    # New column only; existing accounts default to not onboarded (tour shows once).
    op.alter_column("users", "onboarded", server_default=None)


def downgrade() -> None:
    op.drop_column("users", "onboarded")
