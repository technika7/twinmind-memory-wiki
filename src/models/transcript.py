"""
SQLAlchemy models for the Memory Wiki application.
"""

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime
from sqlalchemy import Enum as SAEnum
from sqlalchemy import Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from src.db.session import Base


class TranscriptStatus(str, enum.Enum):
    """Processing status lifecycle for a transcript."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Transcript(Base):
    """
    Stores ingested conversation transcripts.

    Each transcript goes through a processing pipeline:
    pending → processing → completed/failed
    """

    __tablename__ = "transcripts"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    title = Column(String(500), nullable=False)
    content = Column(Text, nullable=False)
    participants = Column(JSONB, nullable=True, default=list)
    occurred_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Processing status
    status = Column(
        SAEnum(
            TranscriptStatus,
            name="transcript_status",
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
        default=TranscriptStatus.PENDING,
        index=True,
    )
    error_message = Column(Text, nullable=True)

    # Idempotency: track which memory files were written
    processed_entities = Column(JSONB, nullable=True, default=list)

    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Indexes for common queries
    __table_args__ = (Index("ix_transcripts_created_at", "created_at"),)

    def __repr__(self) -> str:
        return f"<Transcript(id={self.id}, title='{self.title}', status={self.status})>"
