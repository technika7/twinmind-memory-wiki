"""
Celery application configuration.

Production-grade settings for reliable background job processing.
"""

from celery import Celery
from src.config import get_settings

settings = get_settings()

celery_app = Celery(
    "memory_wiki",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    # ── Reliability ────────────────────────────────────────────
    # Acknowledge task only AFTER it completes (not when received).
    # If the worker crashes mid-task, the task returns to the queue.
    task_acks_late=True,

    # Reject tasks back to the queue if worker is killed
    task_reject_on_worker_lost=True,

    # Each worker prefetches only 1 task at a time for fairness
    worker_prefetch_multiplier=1,

    # ── Timeouts ───────────────────────────────────────────────
    # Soft limit: raises SoftTimeLimitExceeded (caught in task)
    task_soft_time_limit=120,

    # Hard limit: kills the task process
    task_time_limit=180,

    # ── Serialization ──────────────────────────────────────────
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],

    # ── Task discovery ─────────────────────────────────────────
    include=["src.workers.tasks"],

    # ── Timezone ───────────────────────────────────────────────
    timezone="UTC",
    enable_utc=True,
)
