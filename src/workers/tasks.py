"""
Celery task definitions.

Each task is designed for:
- Idempotency: safe to run multiple times with the same input
- Retries: automatic retry with exponential backoff for transient failures
- Observability: structured logging at every stage
"""

import logging

from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded

from src.workers.celery_app import celery_app
from src.workers.pipeline import MemoryPipeline

logger = logging.getLogger(__name__)


@celery_app.task(
    name="process_transcript",
    bind=True,
    max_retries=3,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=60,
    retry_jitter=True,
    # Don't retry on these — they indicate a permanent failure
    dont_autoretry_for=(
        ValueError,
        SoftTimeLimitExceeded,
    ),
)
def process_transcript(self, transcript_id: str) -> dict:
    """
    Process a transcript: extract memories and store them in the file tree.

    This is the main background task that orchestrates:
    1. Fetching the transcript from the database
    2. Extracting structured memories via LLM
    3. Creating or merging memory files in S3
    4. Updating the _meta index
    5. Marking the transcript as completed

    The task is idempotent — re-running it for the same transcript
    will skip already-processed entities.
    """
    logger.info(
        "Starting memory generation for transcript %s (attempt %d/%d)",
        transcript_id,
        self.request.retries + 1,
        self.max_retries + 1,
    )

    try:
        pipeline = MemoryPipeline()
        result = pipeline.process(transcript_id)
        logger.info(
            "Memory generation complete for transcript %s: %s",
            transcript_id,
            result,
        )
        return result

    except SoftTimeLimitExceeded:
        logger.error(
            "Transcript %s processing timed out (soft limit)",
            transcript_id,
        )
        pipeline = MemoryPipeline()
        pipeline.mark_failed(
            transcript_id,
            "Processing timed out — transcript may be too long"
        )
        raise

    except Exception as e:
        logger.exception(
            "Failed to process transcript %s: %s",
            transcript_id,
            str(e),
        )
        # On final retry, mark as permanently failed
        if self.request.retries >= self.max_retries:
            try:
                pipeline = MemoryPipeline()
                pipeline.mark_failed(transcript_id, str(e))
            except Exception:
                logger.exception("Failed to mark transcript as failed")
        raise
