"""
Memory merger — handles intelligent merging of new facts into existing memory files.

Supports three merge strategies:
- Create: Generate new memory files from scratch
- Merge: Intelligently update existing files with new information
- Append: Add new entries to chronological logs
"""

import logging
from datetime import datetime, timezone

from src.llm.client import LLMClient
from src.llm.extraction import EventExtraction, PersonExtraction, TopicExtraction
from src.llm.prompts import (
    GENERATE_EVENT_PROMPT,
    GENERATE_PERSON_PROFILE_PROMPT,
    GENERATE_TOPIC_OVERVIEW_PROMPT,
    MERGE_SYSTEM_PROMPT,
    build_merge_user_prompt,
)

logger = logging.getLogger(__name__)


class MemoryMerger:
    """
    Handles creation and merging of memory files.

    When a file doesn't exist, it generates one from scratch.
    When a file exists, it intelligently merges new facts using the LLM.
    """

    def __init__(self, llm_client: LLMClient | None = None):
        self.llm = llm_client or LLMClient()

    def create_person_profile(
        self,
        person: PersonExtraction,
        transcript_id: str,
    ) -> str:
        """Generate a new person profile memory file."""
        timestamp = datetime.now(timezone.utc).isoformat()
        tags = self._extract_tags_from_person(person)

        facts_text = "\n".join(
            f"- {f.text} (confidence: {f.confidence})" for f in person.facts
        )

        user_prompt = (
            f"Create a profile for: {person.name}\n"
            f"Slug: {person.slug}\n"
            f"Context: {person.mentioned_in_context}\n\n"
            f"Known Facts:\n{facts_text}\n\n"
            f"Transcript ID: {transcript_id}\n"
            f"Timestamp: {timestamp}\n"
            f"Tags: {', '.join(tags)}"
        )

        return self.llm.generate(
            system_prompt=GENERATE_PERSON_PROFILE_PROMPT.format(
                slug=person.slug,
                name=person.name,
                timestamp=timestamp,
                transcript_id=transcript_id,
                tags=", ".join(f'"{t}"' for t in tags),
            ),
            user_prompt=user_prompt,
            temperature=0.3,
        )

    def create_topic_overview(
        self,
        topic: TopicExtraction,
        transcript_id: str,
    ) -> str:
        """Generate a new topic overview memory file."""
        timestamp = datetime.now(timezone.utc).isoformat()
        tags = [topic.category, topic.slug]

        facts_text = "\n".join(f"- {f.text}" for f in topic.facts)
        decisions_text = (
            "\n".join(
                f"- {d.text} (date: {d.date or 'unknown'})" for d in topic.decisions
            )
            or "None"
        )
        actions_text = (
            "\n".join(
                f"- [{a.status}] {a.text} (assignee: {a.assignee or 'unassigned'})"
                for a in topic.action_items
            )
            or "None"
        )

        user_prompt = (
            f"Create an overview for topic: {topic.name}\n"
            f"Category: {topic.category}\n"
            f"Slug: {topic.slug}\n\n"
            f"Facts:\n{facts_text}\n\n"
            f"Decisions:\n{decisions_text}\n\n"
            f"Action Items:\n{actions_text}\n\n"
            f"Transcript ID: {transcript_id}\n"
            f"Timestamp: {timestamp}"
        )

        return self.llm.generate(
            system_prompt=GENERATE_TOPIC_OVERVIEW_PROMPT.format(
                slug=topic.slug,
                name=topic.name,
                category=topic.category,
                timestamp=timestamp,
                transcript_id=transcript_id,
                tags=", ".join(f'"{t}"' for t in tags),
            ),
            user_prompt=user_prompt,
            temperature=0.3,
        )

    def create_event_summary(
        self,
        event: EventExtraction,
        transcript_id: str,
    ) -> str:
        """Generate a new event summary memory file."""
        timestamp = datetime.now(timezone.utc).isoformat()
        date = event.date or datetime.now(timezone.utc).strftime("%Y-%m-%d")

        outcomes_text = (
            "\n".join(f"- {o}" for o in event.key_outcomes) or "None recorded"
        )

        user_prompt = (
            f"Create an event summary:\n"
            f"Title: {event.title}\n"
            f"Date: {date}\n"
            f"Participants: {', '.join(event.participants)}\n"
            f"Summary: {event.summary}\n\n"
            f"Key Outcomes:\n{outcomes_text}\n\n"
            f"Transcript ID: {transcript_id}\n"
            f"Timestamp: {timestamp}"
        )

        return self.llm.generate(
            system_prompt=GENERATE_EVENT_PROMPT.format(
                title=event.title,
                date=date,
                participants=", ".join(f'"{p}"' for p in event.participants),
                timestamp=timestamp,
                transcript_id=transcript_id,
            ),
            user_prompt=user_prompt,
            temperature=0.3,
        )

    def merge_with_existing(
        self,
        existing_content: str,
        new_facts: dict,
        transcript_id: str,
    ) -> str:
        """
        Merge new facts into an existing memory file.

        Uses the LLM to intelligently deduplicate, resolve conflicts,
        and update the file while preserving existing information.
        """
        timestamp = datetime.now(timezone.utc).isoformat()

        user_prompt = build_merge_user_prompt(
            existing_content=existing_content,
            new_facts=new_facts,
            transcript_id=transcript_id,
            current_timestamp=timestamp,
        )

        result = self.llm.generate(
            system_prompt=MERGE_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            temperature=0.2,
            max_tokens=4096,
        )

        # Strip any code fences the LLM might add
        result = result.strip()
        if result.startswith("```"):
            lines = result.split("\n")
            # Remove first and last lines (code fence markers)
            lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            result = "\n".join(lines)

        return result

    @staticmethod
    def _extract_tags_from_person(person: PersonExtraction) -> list[str]:
        """Extract relevant tags from a person's facts."""
        tags = []
        for fact in person.facts:
            if fact.category and fact.category != "general":
                tags.append(fact.category)
        # Deduplicate while preserving order
        seen = set()
        unique_tags = []
        for tag in tags:
            if tag not in seen:
                seen.add(tag)
                unique_tags.append(tag)
        return unique_tags or ["person"]
