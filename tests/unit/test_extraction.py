"""
Unit tests for memory extraction logic.

Tests the parsing of LLM structured output into typed domain objects,
independent of the actual LLM calls.
"""

import pytest
from src.llm.extraction import MemoryExtractor, ExtractionResult


class TestMemoryExtractor:
    """Test extraction parsing logic with mocked LLM responses."""

    def test_extract_parses_people(self, mock_llm_client):
        """Verify people are correctly parsed from LLM output."""
        extractor = MemoryExtractor(llm_client=mock_llm_client)
        result = extractor.extract("Some transcript content")

        assert len(result.people) == 1
        person = result.people[0]
        assert person.name == "John Doe"
        assert person.slug == "john_doe"
        assert len(person.facts) == 2
        assert person.facts[0].confidence == "high"
        assert person.facts[0].category == "role"

    def test_extract_parses_topics(self, mock_llm_client):
        """Verify topics with decisions and action items are parsed."""
        extractor = MemoryExtractor(llm_client=mock_llm_client)
        result = extractor.extract("Some transcript content")

        assert len(result.topics) == 1
        topic = result.topics[0]
        assert topic.name == "Project Atlas"
        assert topic.slug == "project_atlas"
        assert topic.category == "project"
        assert len(topic.decisions) == 1
        assert len(topic.action_items) == 1
        assert topic.action_items[0].status == "open"

    def test_extract_parses_event(self, mock_llm_client):
        """Verify event metadata is correctly extracted."""
        extractor = MemoryExtractor(llm_client=mock_llm_client)
        result = extractor.extract("Some transcript content")

        assert result.event is not None
        assert result.event.title == "Weekly Standup"
        assert result.event.date == "2026-06-05"
        assert len(result.event.participants) == 2

    def test_extract_parses_relationships(self, mock_llm_client):
        """Verify entity relationships are parsed."""
        extractor = MemoryExtractor(llm_client=mock_llm_client)
        result = extractor.extract("Some transcript content")

        assert len(result.relationships) == 1
        rel = result.relationships[0]
        assert rel.from_entity == "john_doe"
        assert rel.to_entity == "project_atlas"
        assert rel.relationship_type == "works_on"

    def test_extract_handles_empty_response(self, mock_llm_client):
        """Verify graceful handling of empty extraction."""
        mock_llm_client.generate_json.return_value = {
            "people": [],
            "topics": [],
            "event": None,
            "relationships": [],
        }

        extractor = MemoryExtractor(llm_client=mock_llm_client)
        result = extractor.extract("Minimal transcript")

        assert len(result.people) == 0
        assert len(result.topics) == 0
        assert result.event is None

    def test_extract_handles_missing_fields(self, mock_llm_client):
        """Verify fallback defaults for missing fields in LLM output."""
        mock_llm_client.generate_json.return_value = {
            "people": [{"name": "Jane", "slug": "jane", "facts": []}],
            "topics": [],
        }

        extractor = MemoryExtractor(llm_client=mock_llm_client)
        result = extractor.extract("Some content")

        assert len(result.people) == 1
        assert result.people[0].name == "Jane"
        assert result.people[0].mentioned_in_context == ""

    def test_slug_generation(self):
        """Verify slug normalization handles edge cases."""
        assert MemoryExtractor._ensure_slug("John Doe") == "john_doe"
        assert MemoryExtractor._ensure_slug("Dr. Jane O'Brien") == "dr_jane_o_brien"
        assert MemoryExtractor._ensure_slug("  spaces  ") == "spaces"
        assert MemoryExtractor._ensure_slug("UPPER-case") == "upper_case"
        assert MemoryExtractor._ensure_slug("") == "unknown"
        assert MemoryExtractor._ensure_slug("!!!") == "unknown"


class TestExtractionResult:
    """Test the ExtractionResult dataclass."""

    def test_default_empty(self):
        """Verify default empty state."""
        result = ExtractionResult()
        assert result.people == []
        assert result.topics == []
        assert result.event is None
        assert result.relationships == []
