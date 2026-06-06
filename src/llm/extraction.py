"""
Memory extraction — parses LLM structured output into domain objects.
"""

import logging
from dataclasses import dataclass, field

from src.llm.client import LLMClient
from src.llm.prompts import EXTRACTION_SYSTEM_PROMPT, build_extraction_user_prompt

logger = logging.getLogger(__name__)


@dataclass
class Fact:
    text: str
    confidence: str = "medium"
    category: str = "general"


@dataclass
class PersonExtraction:
    name: str
    slug: str
    facts: list[Fact] = field(default_factory=list)
    mentioned_in_context: str = ""


@dataclass
class Decision:
    text: str
    date: str | None = None
    participants: list[str] = field(default_factory=list)


@dataclass
class ActionItem:
    text: str
    assignee: str | None = None
    due_date: str | None = None
    status: str = "open"


@dataclass
class TopicExtraction:
    name: str
    slug: str
    category: str = "concept"
    facts: list[Fact] = field(default_factory=list)
    decisions: list[Decision] = field(default_factory=list)
    action_items: list[ActionItem] = field(default_factory=list)


@dataclass
class EventExtraction:
    title: str
    date: str | None = None
    participants: list[str] = field(default_factory=list)
    summary: str = ""
    key_outcomes: list[str] = field(default_factory=list)


@dataclass
class Relationship:
    from_entity: str
    to_entity: str
    relationship_type: str


@dataclass
class ExtractionResult:
    """Complete extraction result from a single transcript."""

    people: list[PersonExtraction] = field(default_factory=list)
    topics: list[TopicExtraction] = field(default_factory=list)
    event: EventExtraction | None = None
    relationships: list[Relationship] = field(default_factory=list)


class MemoryExtractor:
    """Extracts structured memories from transcript text using an LLM."""

    def __init__(self, llm_client: LLMClient | None = None):
        self.llm = llm_client or LLMClient()

    def extract(
        self,
        transcript_content: str,
        transcript_title: str = "",
        participants_hint: list[str] | None = None,
        occurred_at: str | None = None,
    ) -> ExtractionResult:
        """
        Extract memories from a transcript.

        Returns a structured ExtractionResult with people, topics,
        event, and relationships.
        """
        user_prompt = build_extraction_user_prompt(
            transcript_content=transcript_content,
            transcript_title=transcript_title,
            participants_hint=participants_hint,
            occurred_at=occurred_at,
        )

        raw = self.llm.generate_json(
            system_prompt=EXTRACTION_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            temperature=0.2,
        )

        return self._parse_extraction(raw)

    def _parse_extraction(self, raw: dict) -> ExtractionResult:
        """Parse raw LLM JSON output into typed dataclasses."""
        result = ExtractionResult()

        # Parse people
        for p in raw.get("people", []):
            facts = [
                Fact(
                    text=f.get("text", ""),
                    confidence=f.get("confidence", "medium"),
                    category=f.get("category", "general"),
                )
                for f in p.get("facts", [])
            ]
            result.people.append(
                PersonExtraction(
                    name=p.get("name", "Unknown"),
                    slug=self._ensure_slug(p.get("slug", p.get("name", "unknown"))),
                    facts=facts,
                    mentioned_in_context=p.get("mentioned_in_context", ""),
                )
            )

        # Parse topics
        for t in raw.get("topics", []):
            facts = [
                Fact(text=f.get("text", ""), confidence=f.get("confidence", "medium"))
                for f in t.get("facts", [])
            ]
            decisions = [
                Decision(
                    text=d.get("text", ""),
                    date=d.get("date"),
                    participants=d.get("participants", []),
                )
                for d in t.get("decisions", [])
            ]
            action_items = [
                ActionItem(
                    text=a.get("text", ""),
                    assignee=a.get("assignee"),
                    due_date=a.get("due_date"),
                    status=a.get("status", "open"),
                )
                for a in t.get("action_items", [])
            ]
            result.topics.append(
                TopicExtraction(
                    name=t.get("name", "Unknown"),
                    slug=self._ensure_slug(t.get("slug", t.get("name", "unknown"))),
                    category=t.get("category", "concept"),
                    facts=facts,
                    decisions=decisions,
                    action_items=action_items,
                )
            )

        # Parse event
        event_data = raw.get("event")
        if event_data:
            result.event = EventExtraction(
                title=event_data.get("title", "Untitled Event"),
                date=event_data.get("date"),
                participants=event_data.get("participants", []),
                summary=event_data.get("summary", ""),
                key_outcomes=event_data.get("key_outcomes", []),
            )

        # Parse relationships
        for r in raw.get("relationships", []):
            result.relationships.append(
                Relationship(
                    from_entity=r.get("from_entity", ""),
                    to_entity=r.get("to_entity", ""),
                    relationship_type=r.get("relationship_type", "related"),
                )
            )

        logger.info(
            "Extraction complete: %d people, %d topics, %d relationships",
            len(result.people),
            len(result.topics),
            len(result.relationships),
        )

        self._validate_extraction(result)
        return result

    def _validate_extraction(self, result: ExtractionResult) -> None:
        """
        Validate extraction output quality.

        Raises ValueError for extraction results that are clearly unusable,
        so the pipeline can mark the transcript as failed with a clear message.
        """
        total_entities = len(result.people) + len(result.topics) + (
            1 if result.event else 0
        )
        if total_entities == 0:
            raise ValueError(
                "LLM extraction produced no entities (no people, topics, or events). "
                "The transcript may be too short or not contain meaningful content."
            )

        # Validate entity names aren't empty
        for person in result.people:
            if not person.name or not person.name.strip():
                logger.warning("Skipping person with empty name")
                result.people.remove(person)
            elif len(person.slug) > 100:
                person.slug = person.slug[:100]

        for topic in result.topics:
            if not topic.name or not topic.name.strip():
                logger.warning("Skipping topic with empty name")
                result.topics.remove(topic)
            elif len(topic.slug) > 100:
                topic.slug = topic.slug[:100]

    @staticmethod
    def _ensure_slug(name: str) -> str:
        """Generate a URL-safe slug from a name."""
        import re

        slug = name.lower().strip()
        slug = re.sub(r"[^a-z0-9]+", "_", slug)
        slug = slug.strip("_")
        return slug or "unknown"
