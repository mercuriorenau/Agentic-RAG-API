"""Pending signups + password-reset fields.

Revision ID: 006_pending_reset
Revises: 005_email_verification
Create Date: 2026-07-24
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "006_pending_reset"
down_revision: str | None = "005_email_verification"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "pending_signups",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("email_verify_token_hash", sa.String(length=255), nullable=False),
        sa.Column("email_verify_code_hash", sa.String(length=255), nullable=False),
        sa.Column("email_verify_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_pending_signups_email", "pending_signups", ["email"], unique=True)

    op.add_column("users", sa.Column("password_reset_code_hash", sa.String(length=255), nullable=True))
    op.add_column(
        "users",
        sa.Column("password_reset_expires_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "password_reset_expires_at")
    op.drop_column("users", "password_reset_code_hash")
    op.drop_index("ix_pending_signups_email", table_name="pending_signups")
    op.drop_table("pending_signups")
