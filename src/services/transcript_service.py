"""
Transcript service — business logic for transcript CRUD operations.
"""

import logging
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.transcript import Transcript, TranscriptStatus
from src.models.schemas import TranscriptCreate

logger = logging.getLogger(__name__)


class TranscriptService:
    """Handles transcript persistence and retrieval."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, data: TranscriptCreate) -> Transcript:
        """
        Create a new transcript record with PENDING status.

        The actual memory generation is triggered asynchronously
        via a Celery task after this returns.
        """
        transcript = Transcript(
            title=data.title,
            content=data.content,
            participants=data.participants or [],
            occurred_at=data.occurred_at,
            status=TranscriptStatus.PENDING,
        )
        self.db.add(transcript)
        await self.db.flush()
        await self.db.refresh(transcript)
        logger.info("Created transcript %s: '%s'", transcript.id, transcript.title)
        return transcript

    async def get_by_id(self, transcript_id: UUID) -> Transcript | None:
        """Retrieve a transcript by its UUID."""
        result = await self.db.execute(
            select(Transcript).where(Transcript.id == transcript_id)
        )
        return result.scalar_one_or_none()

    async def list_all(self, page: int = 1, page_size: int = 20) -> tuple[list[Transcript], int]:
        """
        List transcripts with pagination.

        Returns (items, total_count) tuple.
        """
        # Count total
        count_result = await self.db.execute(select(func.count(Transcript.id)))
        total = count_result.scalar_one()

        # Fetch page
        offset = (page - 1) * page_size
        result = await self.db.execute(
            select(Transcript)
            .order_by(Transcript.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        items = list(result.scalars().all())

        return items, total
