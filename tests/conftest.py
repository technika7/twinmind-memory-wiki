"""
Shared test fixtures and configuration.
"""

import pytest
import asyncio
from unittest.mock import MagicMock, patch

from httpx import AsyncClient, ASGITransport

# Use a test-specific event loop
@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_llm_client():
    """Mock LLM client that returns predefined responses."""
    client = MagicMock()
    client.generate.return_value = "mocked response"
    client.generate_json.return_value = {
        "people": [
            {
                "name": "John Doe",
                "slug": "john_doe",
                "facts": [
                    {"text": "Senior Engineer at Acme Corp", "confidence": "high", "category": "role"},
                    {"text": "Leads the Atlas project", "confidence": "high", "category": "role"},
                ],
                "mentioned_in_context": "Gave a project update during standup"
            }
        ],
        "topics": [
            {
                "name": "Project Atlas",
                "slug": "project_atlas",
                "category": "project",
                "facts": [
                    {"text": "Migration initiative targeting Q3 completion", "confidence": "high"},
                ],
                "decisions": [
                    {"text": "Use microservices architecture", "date": "2026-06-05", "participants": ["John Doe"]}
                ],
                "action_items": [
                    {"text": "Complete API spec", "assignee": "John Doe", "due_date": "2026-06-12", "status": "open"}
                ]
            }
        ],
        "event": {
            "title": "Weekly Standup",
            "date": "2026-06-05",
            "participants": ["John Doe", "Sarah Chen"],
            "summary": "Team discussed Atlas project progress and upcoming milestones.",
            "key_outcomes": ["Atlas is 80% complete", "API spec due next week"]
        },
        "relationships": [
            {"from_entity": "john_doe", "to_entity": "project_atlas", "relationship_type": "works_on"}
        ]
    }
    return client


@pytest.fixture
def sample_transcript_data():
    """Sample transcript for testing."""
    return {
        "title": "Weekly Standup - June 5",
        "content": (
            "John: Good morning everyone. Quick update on Atlas - we're about 80% done "
            "with the migration. The API layer is complete, and we're now working on the "
            "data pipeline.\n\n"
            "Sarah: That's great progress. What's the timeline for the remaining 20%?\n\n"
            "John: I think we can wrap it up by end of Q3. The main blocker is the "
            "legacy data transformation, which is more complex than we anticipated.\n\n"
            "Sarah: Got it. Let's make sure we document the API spec by next Friday. "
            "I'll need it for the client integration.\n\n"
            "John: Will do. I'll have the spec ready by June 12th.\n\n"
            "Sarah: Perfect. Also, we decided to go with the microservices architecture "
            "for the new module. John, can you lead that effort?"
        ),
        "participants": ["John Doe", "Sarah Chen"],
    }


@pytest.fixture
def sample_extraction_result():
    """Pre-built extraction result for testing merge and pipeline logic."""
    from src.llm.extraction import (
        ExtractionResult,
        PersonExtraction,
        TopicExtraction,
        EventExtraction,
        Relationship,
        Fact,
        Decision,
        ActionItem,
    )

    return ExtractionResult(
        people=[
            PersonExtraction(
                name="John Doe",
                slug="john_doe",
                facts=[
                    Fact(text="Senior Engineer at Acme Corp", confidence="high", category="role"),
                    Fact(text="Leads the Atlas project", confidence="high", category="role"),
                ],
                mentioned_in_context="Gave project update during standup",
            ),
            PersonExtraction(
                name="Sarah Chen",
                slug="sarah_chen",
                facts=[
                    Fact(text="Works on client integrations", confidence="medium", category="role"),
                ],
                mentioned_in_context="Asked questions about timeline and API spec",
            ),
        ],
        topics=[
            TopicExtraction(
                name="Project Atlas",
                slug="project_atlas",
                category="project",
                facts=[Fact(text="Migration initiative, 80% complete", confidence="high")],
                decisions=[
                    Decision(
                        text="Use microservices architecture",
                        date="2026-06-05",
                        participants=["John Doe"],
                    )
                ],
                action_items=[
                    ActionItem(
                        text="Complete API spec",
                        assignee="John Doe",
                        due_date="2026-06-12",
                        status="open",
                    )
                ],
            )
        ],
        event=EventExtraction(
            title="Weekly Standup",
            date="2026-06-05",
            participants=["John Doe", "Sarah Chen"],
            summary="Team discussed Atlas project progress.",
            key_outcomes=["Atlas 80% complete", "API spec due June 12"],
        ),
        relationships=[
            Relationship(from_entity="john_doe", to_entity="project_atlas", relationship_type="works_on"),
        ],
    )


@pytest.fixture
def sample_person_profile_md():
    """Sample person profile markdown for testing merge logic."""
    return """---
type: person_profile
entity: john_doe
display_name: "John Doe"
created_at: "2026-06-01T10:00:00Z"
updated_at: "2026-06-01T10:00:00Z"
source_transcripts: ["tr_old_123"]
tags: ["engineering", "role"]
version: 1
---

# John Doe

## Role & Context
Engineer at Acme Corp.

## Key Facts
- Works on backend systems
- Joined in 2024

## Relationship Notes
- Met during onboarding
"""
