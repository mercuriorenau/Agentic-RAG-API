"""Add chats and scope documents per chat.

Revision ID: 002_chats
Revises: 001_initial
Create Date: 2026-07-16
"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "002_chats"
down_revision: str | None = "001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "chats",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_chats_user_id"), "chats", ["user_id"], unique=False)

    op.create_table(
        "messages",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("chat_id", sa.UUID(), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["chat_id"], ["chats.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_messages_chat_id"), "messages", ["chat_id"], unique=False)

    op.add_column("documents", sa.Column("chat_id", sa.UUID(), nullable=True))

    conn = op.get_bind()
    users = conn.execute(sa.text("SELECT id FROM users")).fetchall()
    for (user_id,) in users:
        chat_id = uuid.uuid4()
        conn.execute(
            sa.text(
                "INSERT INTO chats (id, user_id, title) VALUES (:chat_id, :user_id, 'Default chat')"
            ),
            {"chat_id": chat_id, "user_id": user_id},
        )
        conn.execute(
            sa.text("UPDATE documents SET chat_id = :chat_id WHERE user_id = :user_id"),
            {"chat_id": chat_id, "user_id": user_id},
        )

    op.alter_column("documents", "chat_id", nullable=False)
    op.create_index(op.f("ix_documents_chat_id"), "documents", ["chat_id"], unique=False)
    op.create_foreign_key(
        "fk_documents_chat_id_chats",
        "documents",
        "chats",
        ["chat_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint("fk_documents_chat_id_chats", "documents", type_="foreignkey")
    op.drop_index(op.f("ix_documents_chat_id"), table_name="documents")
    op.drop_column("documents", "chat_id")
    op.drop_index(op.f("ix_messages_chat_id"), table_name="messages")
    op.drop_table("messages")
    op.drop_index(op.f("ix_chats_user_id"), table_name="chats")
    op.drop_table("chats")
