"""
Unit tests for Pydantic schema validation.

Tests edge cases in request/response models.
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.models.schemas import (
    ErrorResponse,
    GrepMatch,
    MemoryNode,
    TranscriptCreate,
    TranscriptResponse,
)


class TestTranscriptCreate:
    """Test transcript creation schema validation."""

    def test_valid_minimal(self):
        """Minimal valid transcript."""
        data = TranscriptCreate(title="Test", content="Hello world")
        assert data.title == "Test"
        assert data.participants is None
        assert data.occurred_at is None

    def test_valid_full(self):
        """Full transcript with all fields."""
        data = TranscriptCreate(
            title="Weekly Standup",
            content="John said hello",
            participants=["John", "Sarah"],
            occurred_at=datetime(2026, 6, 5, tzinfo=timezone.utc),
        )
        assert len(data.participants) == 2

    def test_empty_title_fails(self):
        """Title must be non-empty."""
        with pytest.raises(ValidationError):
            TranscriptCreate(title="", content="some content")

    def test_empty_content_fails(self):
        """Content must be non-empty."""
        with pytest.raises(ValidationError):
            TranscriptCreate(title="Test", content="")

    def test_title_max_length(self):
        """Title must not exceed 500 characters."""
        with pytest.raises(ValidationError):
            TranscriptCreate(title="x" * 501, content="some content")

    def test_unicode_content(self):
        """Unicode content should be accepted."""
        data = TranscriptCreate(
            title="日本語テスト",
            content="会議のメモ: プロジェクトの進捗について議論しました。",
        )
        assert "日本語" in data.title


class TestTranscriptResponse:
    """Test transcript response schema."""

    def test_from_attributes(self):
        """Verify from_attributes mode works for ORM objects."""

        # Simulate ORM-like object
        class FakeORM:
            id = uuid4()
            title = "Test"
            content = "Hello"
            participants = ["John"]
            occurred_at = None
            status = "pending"
            error_message = None
            created_at = datetime.now(timezone.utc)
            updated_at = datetime.now(timezone.utc)

        response = TranscriptResponse.model_validate(FakeORM())
        assert response.title == "Test"
        assert response.status == "pending"


class TestMemoryNode:
    """Test memory node schema."""

    def test_file_node(self):
        node = MemoryNode(
            name="profile.md",
            type="file",
            path="/people/john_doe/profile.md",
            size=1024,
        )
        assert node.type == "file"
        assert node.size == 1024

    def test_directory_node(self):
        node = MemoryNode(
            name="john_doe",
            type="directory",
            path="/people/john_doe",
        )
        assert node.type == "directory"
        assert node.size is None


class TestGrepMatch:
    """Test grep match schema."""

    def test_basic_match(self):
        match = GrepMatch(line=42, content="Atlas project is 80% complete")
        assert match.line == 42


class TestErrorResponse:
    """Test RFC 7807 error response schema."""

    def test_error_format(self):
        error = ErrorResponse(
            type="https://memorywiki.dev/errors/not-found",
            title="Transcript Not Found",
            status=404,
            detail="No transcript with ID 'xyz' exists.",
            instance="/api/v1/transcripts/xyz",
        )
        assert error.status == 404
