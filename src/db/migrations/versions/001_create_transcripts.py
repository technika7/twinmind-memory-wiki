"""create transcripts table

Revision ID: 001
Revises:
Create Date: 2026-06-06
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create the transcript_status enum type
    transcript_status = sa.Enum(
        "pending", "processing", "completed", "failed",
        name="transcript_status",
    )
    transcript_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "transcripts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("participants", JSONB(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status",
            sa.Enum("pending", "processing", "completed", "failed", name="transcript_status", create_type=False),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("processed_entities", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # Create indexes
    op.create_index("ix_transcripts_status", "transcripts", ["status"])
    op.create_index("ix_transcripts_created_at", "transcripts", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_transcripts_created_at")
    op.drop_index("ix_transcripts_status")
    op.drop_table("transcripts")

    # Drop the enum type
    sa.Enum(name="transcript_status").drop(op.get_bind(), checkfirst=True)
