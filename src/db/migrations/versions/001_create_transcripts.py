"""create transcripts table

Revision ID: 001
Revises:
Create Date: 2026-06-06
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB, ENUM

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Define the enum type once, using the PG-native variant
transcript_status_enum = ENUM(
    "pending", "processing", "completed", "failed",
    name="transcript_status",
    create_type=False,
)


def upgrade() -> None:
    # Create the enum type explicitly via raw SQL (idempotent)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE transcript_status AS ENUM ('pending', 'processing', 'completed', 'failed');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    op.create_table(
        "transcripts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("participants", JSONB(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status",
            transcript_status_enum,
            nullable=False,
            server_default="pending",
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("processed_entities", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_index("ix_transcripts_status", "transcripts", ["status"])
    op.create_index("ix_transcripts_created_at", "transcripts", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_transcripts_created_at")
    op.drop_index("ix_transcripts_status")
    op.drop_table("transcripts")
    op.execute("DROP TYPE IF EXISTS transcript_status")
