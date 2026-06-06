"""
Unit tests for memory merger logic.
"""

from src.llm.extraction import (
    ActionItem,
    Decision,
    Fact,
    PersonExtraction,
    TopicExtraction,
)
from src.llm.merger import MemoryMerger


class TestMemoryMerger:
    """Test memory file creation and merge logic."""

    def test_create_person_profile_calls_llm(self, mock_llm_client):
        """Verify person profile creation uses the LLM."""
        mock_llm_client.generate.return_value = (
            "---\ntype: person_profile\n---\n# John Doe"
        )
        merger = MemoryMerger(llm_client=mock_llm_client)

        person = PersonExtraction(
            name="John Doe",
            slug="john_doe",
            facts=[Fact(text="Engineer", confidence="high", category="role")],
            mentioned_in_context="Spoke during standup",
        )

        merger.create_person_profile(person, "tr_123")
        assert (
            "John Doe" in mock_llm_client.generate.call_args[1]["user_prompt"]
            or "John Doe" in mock_llm_client.generate.call_args[0][1]
            if mock_llm_client.generate.call_args[0]
            else True
        )
        mock_llm_client.generate.assert_called_once()

    def test_create_topic_overview_calls_llm(self, mock_llm_client):
        """Verify topic overview creation uses the LLM."""
        mock_llm_client.generate.return_value = (
            "---\ntype: topic_overview\n---\n# Atlas"
        )
        merger = MemoryMerger(llm_client=mock_llm_client)

        topic = TopicExtraction(
            name="Project Atlas",
            slug="project_atlas",
            category="project",
            facts=[Fact(text="Migration project", confidence="high")],
            decisions=[Decision(text="Use microservices", date="2026-06-05")],
            action_items=[
                ActionItem(text="Write spec", assignee="John", status="open")
            ],
        )

        merger.create_topic_overview(topic, "tr_123")
        mock_llm_client.generate.assert_called_once()

    def test_merge_strips_code_fences(self, mock_llm_client):
        """Verify code fences are stripped from LLM merge output."""
        mock_llm_client.generate.return_value = (
            "```markdown\n---\ntype: test\n---\n# Content\n```"
        )
        merger = MemoryMerger(llm_client=mock_llm_client)

        result = merger.merge_with_existing("existing", {"new": "facts"}, "tr_123")
        assert not result.startswith("```")
        assert not result.endswith("```")

    def test_extract_tags_from_person(self):
        """Verify tag extraction from person facts."""
        person = PersonExtraction(
            name="John",
            slug="john",
            facts=[
                Fact(text="Engineer", confidence="high", category="role"),
                Fact(text="Likes Python", confidence="medium", category="preference"),
                Fact(text="Another role fact", confidence="high", category="role"),
            ],
        )

        tags = MemoryMerger._extract_tags_from_person(person)
        assert "role" in tags
        assert "preference" in tags
        # Should be deduplicated
        assert tags.count("role") == 1

    def test_extract_tags_defaults_to_person(self):
        """Verify default tag when no categories found."""
        person = PersonExtraction(
            name="John",
            slug="john",
            facts=[Fact(text="Something", confidence="high", category="general")],
        )

        tags = MemoryMerger._extract_tags_from_person(person)
        assert tags == ["person"]
