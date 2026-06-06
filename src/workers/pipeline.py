"""
Memory processing pipeline.

Orchestrates the full flow:
  Transcript → LLM Extraction → File Creation/Merge → Index Update

Designed for idempotency: tracks which entities have been processed
per transcript, so partial failures can resume safely.
"""

import logging
import re
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from src.db.session import sync_engine
from src.llm.client import LLMClient
from src.llm.extraction import ExtractionResult, MemoryExtractor
from src.llm.merger import MemoryMerger
from src.models.transcript import Transcript, TranscriptStatus
from src.services.storage_service import StorageService

logger = logging.getLogger(__name__)


class MemoryPipeline:
    """
    Orchestrates transcript processing into memory files.

    Uses sync database operations since this runs in Celery workers.
    """

    def __init__(self):
        self.storage = StorageService()
        self.llm = LLMClient()
        self.extractor = MemoryExtractor(self.llm)
        self.merger = MemoryMerger(self.llm)

    def process(self, transcript_id: str) -> dict:
        """
        Process a transcript end-to-end.

        Returns a summary dict of what was created/updated.
        """
        # Step 1: Fetch transcript and mark as processing
        transcript = self._fetch_and_lock(transcript_id)
        if transcript is None:
            raise ValueError(f"Transcript {transcript_id} not found")

        if transcript.status == TranscriptStatus.COMPLETED:
            logger.info("Transcript %s already completed, skipping", transcript_id)
            return {"status": "already_completed"}

        # Step 2: Extract memories via LLM
        logger.info("Extracting memories from transcript %s", transcript_id)
        extraction = self.extractor.extract(
            transcript_content=transcript.content,
            transcript_title=transcript.title,
            participants_hint=transcript.participants,
            occurred_at=str(transcript.occurred_at) if transcript.occurred_at else None,
        )

        # Step 3: Process each entity (with idempotency)
        already_processed = set(transcript.processed_entities or [])
        results = {
            "created": [],
            "updated": [],
            "skipped": [],
        }

        # Process people
        for person in extraction.people:
            entity_key = f"people/{person.slug}"
            if entity_key in already_processed:
                results["skipped"].append(entity_key)
                continue

            action = self._process_person(person, transcript_id)
            results[action].append(entity_key)
            self._mark_entity_processed(transcript_id, entity_key)

        # Process topics
        for topic in extraction.topics:
            entity_key = f"topics/{topic.slug}"
            if entity_key in already_processed:
                results["skipped"].append(entity_key)
                continue

            action = self._process_topic(topic, transcript_id)
            results[action].append(entity_key)
            self._mark_entity_processed(transcript_id, entity_key)

        # Process event
        if extraction.event:
            event_slug = self._make_event_slug(extraction.event)
            entity_key = f"events/{event_slug}"
            if entity_key not in already_processed:
                self._process_event(extraction.event, transcript_id)
                results["created"].append(entity_key)
                self._mark_entity_processed(transcript_id, entity_key)

        # Step 4: Update meta index
        self._update_meta_index(extraction, transcript_id)

        # Step 5: Mark transcript as completed
        self._mark_completed(transcript_id)

        logger.info(
            "Pipeline complete for %s: created=%d, updated=%d, skipped=%d",
            transcript_id,
            len(results["created"]),
            len(results["updated"]),
            len(results["skipped"]),
        )
        return results

    # ── Entity Processing ──────────────────────────────────────

    def _process_person(self, person, transcript_id: str) -> str:
        """Create or merge a person's memory files. Returns 'created' or 'updated'."""
        profile_path = f"people/{person.slug}/profile.md"
        existing = self.storage.read_file(profile_path)

        if existing is None:
            # Create new profile
            content = self.merger.create_person_profile(person, transcript_id)
            self.storage.write_file(profile_path, content)
            logger.info("Created person profile: %s", profile_path)
            return "created"
        else:
            # Merge with existing
            new_facts = {
                "name": person.name,
                "facts": [
                    {"text": f.text, "confidence": f.confidence, "category": f.category}
                    for f in person.facts
                ],
                "context": person.mentioned_in_context,
            }
            updated = self.merger.merge_with_existing(
                existing, new_facts, transcript_id
            )
            self.storage.write_file(profile_path, updated)
            logger.info("Updated person profile: %s", profile_path)
            return "updated"

    def _process_topic(self, topic, transcript_id: str) -> str:
        """Create or merge a topic's memory files. Returns 'created' or 'updated'."""
        overview_path = f"topics/{topic.slug}/overview.md"
        existing = self.storage.read_file(overview_path)

        if existing is None:
            content = self.merger.create_topic_overview(topic, transcript_id)
            self.storage.write_file(overview_path, content)
            logger.info("Created topic overview: %s", overview_path)
            return "created"
        else:
            new_facts = {
                "name": topic.name,
                "category": topic.category,
                "facts": [
                    {"text": f.text, "confidence": f.confidence} for f in topic.facts
                ],
                "decisions": [
                    {"text": d.text, "date": d.date, "participants": d.participants}
                    for d in topic.decisions
                ],
                "action_items": [
                    {
                        "text": a.text,
                        "assignee": a.assignee,
                        "due_date": a.due_date,
                        "status": a.status,
                    }
                    for a in topic.action_items
                ],
            }
            updated = self.merger.merge_with_existing(
                existing, new_facts, transcript_id
            )
            self.storage.write_file(overview_path, updated)
            logger.info("Updated topic overview: %s", overview_path)
            return "updated"

    def _process_event(self, event, transcript_id: str) -> None:
        """Create an event summary file."""
        event_slug = self._make_event_slug(event)
        event_path = f"events/{event_slug}.md"

        content = self.merger.create_event_summary(event, transcript_id)
        self.storage.write_file(event_path, content)
        logger.info("Created event: %s", event_path)

    # ── Meta Index ─────────────────────────────────────────────

    def _update_meta_index(
        self, extraction: ExtractionResult, transcript_id: str
    ) -> None:
        """Update the _meta/index.json with current state of all memory files."""
        index_path = "_meta/index.json"
        existing_index = self.storage.read_json(index_path) or {
            "version": 0,
            "last_updated": None,
            "entities": {},
            "transcripts_processed": [],
        }

        # Update entity registry
        for person in extraction.people:
            key = f"people/{person.slug}"
            existing_index["entities"][key] = {
                "type": "person",
                "name": person.name,
                "slug": person.slug,
                "path": f"/people/{person.slug}/profile.md",
                "last_transcript": transcript_id,
            }

        for topic in extraction.topics:
            key = f"topics/{topic.slug}"
            existing_index["entities"][key] = {
                "type": "topic",
                "name": topic.name,
                "slug": topic.slug,
                "category": topic.category,
                "path": f"/topics/{topic.slug}/overview.md",
                "last_transcript": transcript_id,
            }

        if extraction.event:
            event_slug = self._make_event_slug(extraction.event)
            key = f"events/{event_slug}"
            existing_index["entities"][key] = {
                "type": "event",
                "title": extraction.event.title,
                "date": extraction.event.date,
                "path": f"/events/{event_slug}.md",
                "last_transcript": transcript_id,
            }

        # Update relationship graph
        if extraction.relationships:
            graph_path = "_meta/graph.json"
            existing_graph = self.storage.read_json(graph_path) or {"edges": []}
            for rel in extraction.relationships:
                edge = {
                    "from": rel.from_entity,
                    "to": rel.to_entity,
                    "type": rel.relationship_type,
                    "source_transcript": transcript_id,
                }
                # Avoid duplicate edges
                if edge not in existing_graph["edges"]:
                    existing_graph["edges"].append(edge)
            self.storage.write_json(graph_path, existing_graph)

        # Update index metadata
        if transcript_id not in existing_index["transcripts_processed"]:
            existing_index["transcripts_processed"].append(transcript_id)
        existing_index["version"] += 1
        existing_index["last_updated"] = datetime.now(timezone.utc).isoformat()

        self.storage.write_json(index_path, existing_index)
        logger.info("Updated _meta/index.json (version %d)", existing_index["version"])

    # ── Database Operations (sync for Celery) ──────────────────

    def _fetch_and_lock(self, transcript_id: str) -> Transcript | None:
        """Fetch transcript and set status to PROCESSING."""
        with Session(sync_engine) as session:
            transcript = session.execute(
                select(Transcript).where(Transcript.id == transcript_id)
            ).scalar_one_or_none()

            if transcript is None:
                return None

            if transcript.status == TranscriptStatus.COMPLETED:
                return transcript

            # Mark as processing
            transcript.status = TranscriptStatus.PROCESSING
            session.commit()
            session.refresh(transcript)
            return transcript

    def _mark_entity_processed(self, transcript_id: str, entity_key: str) -> None:
        """Track that an entity has been processed for a transcript (idempotency)."""
        with Session(sync_engine) as session:
            transcript = session.execute(
                select(Transcript).where(Transcript.id == transcript_id)
            ).scalar_one_or_none()

            if transcript:
                entities = list(transcript.processed_entities or [])
                if entity_key not in entities:
                    entities.append(entity_key)
                    transcript.processed_entities = entities
                    session.commit()

    def _mark_completed(self, transcript_id: str) -> None:
        """Mark a transcript as successfully processed."""
        with Session(sync_engine) as session:
            session.execute(
                update(Transcript)
                .where(Transcript.id == transcript_id)
                .values(
                    status=TranscriptStatus.COMPLETED,
                    updated_at=datetime.now(timezone.utc),
                )
            )
            session.commit()

    def mark_failed(self, transcript_id: str, error_message: str) -> None:
        """Mark a transcript as failed with error details."""
        with Session(sync_engine) as session:
            session.execute(
                update(Transcript)
                .where(Transcript.id == transcript_id)
                .values(
                    status=TranscriptStatus.FAILED,
                    error_message=error_message,
                    updated_at=datetime.now(timezone.utc),
                )
            )
            session.commit()
        logger.error("Marked transcript %s as failed: %s", transcript_id, error_message)

    # ── Helpers ─────────────────────────────────────────────────

    @staticmethod
    def _make_event_slug(event) -> str:
        """Generate a slug for an event file based on date and title."""
        date = event.date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        title_slug = re.sub(r"[^a-z0-9]+", "_", event.title.lower()).strip("_")
        # Truncate long titles
        if len(title_slug) > 50:
            title_slug = title_slug[:50].rstrip("_")
        return f"{date}_{title_slug}"
