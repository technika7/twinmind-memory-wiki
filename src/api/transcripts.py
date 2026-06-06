"""
Transcript API endpoints.

POST /transcripts       — Ingest a new transcript
GET  /transcripts       — List all transcripts (paginated)
GET  /transcripts/:id   — Retrieve a transcript by ID
GET  /transcripts/:id/status — Check memory generation status
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.errors import NotFoundError
from src.db.session import get_db
from src.models.schemas import (
    TranscriptCreate,
    TranscriptCreatedResponse,
    TranscriptListResponse,
    TranscriptResponse,
    TranscriptStatusResponse,
)
from src.services.transcript_service import TranscriptService
from src.workers.tasks import process_transcript

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "",
    response_model=TranscriptCreatedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ingest a conversation transcript",
    description=(
        "Persists the transcript in the database and enqueues an async job "
        "to extract memories via LLM. Returns 202 Accepted because memory "
        "generation happens asynchronously."
    ),
)
async def create_transcript(
    data: TranscriptCreate,
    db: AsyncSession = Depends(get_db),
):
    service = TranscriptService(db)
    transcript = await service.create(data)

    # Enqueue background memory generation
    process_transcript.delay(str(transcript.id))
    logger.info("Enqueued memory generation for transcript %s", transcript.id)

    return TranscriptCreatedResponse(
        id=transcript.id,
        status=transcript.status.value,
        created_at=transcript.created_at,
        links={
            "self": f"/api/v1/transcripts/{transcript.id}",
            "status": f"/api/v1/transcripts/{transcript.id}/status",
        },
    )


@router.get(
    "",
    response_model=TranscriptListResponse,
    summary="List all transcripts",
)
async def list_transcripts(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: AsyncSession = Depends(get_db),
):
    service = TranscriptService(db)
    items, total = await service.list_all(page=page, page_size=page_size)

    return TranscriptListResponse(
        items=[TranscriptResponse.model_validate(t) for t in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{transcript_id}",
    response_model=TranscriptResponse,
    summary="Retrieve a transcript by ID",
)
async def get_transcript(
    transcript_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    service = TranscriptService(db)
    transcript = await service.get_by_id(transcript_id)

    if transcript is None:
        raise NotFoundError("Transcript", str(transcript_id))

    return TranscriptResponse.model_validate(transcript)


@router.get(
    "/{transcript_id}/status",
    response_model=TranscriptStatusResponse,
    summary="Check transcript processing status",
    description=(
        "Returns the current processing status of a transcript's memory generation. "
        "Status lifecycle: pending → processing → completed / failed."
    ),
)
async def get_transcript_status(
    transcript_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    service = TranscriptService(db)
    transcript = await service.get_by_id(transcript_id)

    if transcript is None:
        raise NotFoundError("Transcript", str(transcript_id))

    return TranscriptStatusResponse.model_validate(transcript)


@router.post(
    "/{transcript_id}/retry",
    response_model=TranscriptStatusResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Retry a failed transcript",
    description="Resets a failed transcript back to pending and re-enqueues the memory generation job.",
)
async def retry_transcript(
    transcript_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    from src.models.transcript import TranscriptStatus

    service = TranscriptService(db)
    transcript = await service.get_by_id(transcript_id)

    if transcript is None:
        raise NotFoundError("Transcript", str(transcript_id))

    if transcript.status not in (TranscriptStatus.FAILED, TranscriptStatus.PENDING):
        from fastapi import HTTPException
        raise HTTPException(
            status_code=400,
            detail=f"Cannot retry transcript with status '{transcript.status.value}'"
        )

    # Reset status and re-enqueue
    transcript.status = TranscriptStatus.PENDING
    transcript.error_message = None
    transcript.processed_entities = []
    await db.flush()
    await db.refresh(transcript)

    process_transcript.delay(str(transcript.id))
    logger.info("Re-enqueued transcript %s for retry", transcript.id)

    return TranscriptStatusResponse.model_validate(transcript)
