"""Add email verification fields to users.

Revision ID: 005_email_verification
Revises: 004_google_oauth
Create Date: 2026-07-24
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "005_email_verification"
down_revision: str | None = "004_google_oauth"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column("users", sa.Column("email_verify_token_hash", sa.String(length=255), nullable=True))
    op.add_column("users", sa.Column("email_verify_code_hash", sa.String(length=255), nullable=True))
    op.add_column(
        "users",
        sa.Column("email_verify_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    # Drop server default so new rows must set email_verified explicitly in app code.
    op.alter_column("users", "email_verified", server_default=None)


def downgrade() -> None:
    op.drop_column("users", "email_verify_expires_at")
    op.drop_column("users", "email_verify_code_hash")
    op.drop_column("users", "email_verify_token_hash")
    op.drop_column("users", "email_verified")
