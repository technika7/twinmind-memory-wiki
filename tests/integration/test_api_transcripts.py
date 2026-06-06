"""
Integration tests for transcript API endpoints.

These tests use FastAPI's TestClient with a real database session
(mocked for testing), verifying the full request/response cycle.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def mock_db_session():
    """Create a mock async database session."""
    session = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    return session


@pytest.fixture
def test_client(mock_db_session):
    """
    Create a test client with mocked dependencies.

    We mock the DB session and Celery task to test the API layer
    in isolation from infrastructure.
    """
    from src.db.session import get_db
    from src.main import app

    async def override_get_db():
        yield mock_db_session

    app.dependency_overrides[get_db] = override_get_db

    with patch("src.api.transcripts.process_transcript") as mock_task:
        mock_task.delay = MagicMock()
        client = TestClient(app)
        yield client, mock_db_session, mock_task

    app.dependency_overrides.clear()


class TestHealthEndpoint:
    """Test the health check endpoint."""

    def test_health_returns_200(self, test_client):
        client, _, _ = test_client
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "memory-wiki"


class TestCreateTranscript:
    """Test POST /api/v1/transcripts."""

    def test_create_returns_202(self, test_client, mock_db_session):
        """Valid transcript creation returns 202 Accepted."""
        client, db, mock_task = test_client

        # Mock the service to return a transcript-like object
        fake_id = uuid4()
        fake_transcript = MagicMock()
        fake_transcript.id = fake_id
        fake_transcript.status.value = "pending"
        fake_transcript.created_at = datetime.now(timezone.utc)

        # Patch the service
        with patch("src.api.transcripts.TranscriptService") as MockService:
            instance = MockService.return_value
            instance.create = AsyncMock(return_value=fake_transcript)

            response = client.post(
                "/api/v1/transcripts",
                json={
                    "title": "Test Standup",
                    "content": "John said hello to Sarah",
                    "participants": ["John", "Sarah"],
                },
            )

        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "pending"
        assert "links" in data
        assert "self" in data["links"]
        assert "status" in data["links"]

    def test_create_enqueues_celery_task(self, test_client):
        """Transcript creation should enqueue a background processing task."""
        client, db, mock_task = test_client

        fake_id = uuid4()
        fake_transcript = MagicMock()
        fake_transcript.id = fake_id
        fake_transcript.status.value = "pending"
        fake_transcript.created_at = datetime.now(timezone.utc)

        with patch("src.api.transcripts.TranscriptService") as MockService:
            instance = MockService.return_value
            instance.create = AsyncMock(return_value=fake_transcript)

            client.post(
                "/api/v1/transcripts",
                json={"title": "Test", "content": "Content"},
            )

        mock_task.delay.assert_called_once_with(str(fake_id))

    def test_create_validates_empty_title(self, test_client):
        """Empty title should return 422."""
        client, _, _ = test_client
        response = client.post(
            "/api/v1/transcripts",
            json={"title": "", "content": "Some content"},
        )
        assert response.status_code == 422

    def test_create_validates_missing_content(self, test_client):
        """Missing content should return 422."""
        client, _, _ = test_client
        response = client.post(
            "/api/v1/transcripts",
            json={"title": "Test"},
        )
        assert response.status_code == 422

    def test_create_validates_title_too_long(self, test_client):
        """Title exceeding 500 chars should return 422."""
        client, _, _ = test_client
        response = client.post(
            "/api/v1/transcripts",
            json={"title": "x" * 501, "content": "Some content"},
        )
        assert response.status_code == 422


class TestGetTranscript:
    """Test GET /api/v1/transcripts/:id."""

    def test_get_existing_transcript(self, test_client):
        """Should return the transcript with all fields."""
        client, db, _ = test_client

        fake_id = uuid4()
        fake_transcript = MagicMock()
        fake_transcript.id = fake_id
        fake_transcript.title = "Test Standup"
        fake_transcript.content = "John said hello"
        fake_transcript.participants = ["John"]
        fake_transcript.occurred_at = None
        fake_transcript.status = "pending"
        fake_transcript.error_message = None
        fake_transcript.created_at = datetime.now(timezone.utc)
        fake_transcript.updated_at = datetime.now(timezone.utc)

        with patch("src.api.transcripts.TranscriptService") as MockService:
            instance = MockService.return_value
            instance.get_by_id = AsyncMock(return_value=fake_transcript)

            response = client.get(f"/api/v1/transcripts/{fake_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Test Standup"

    def test_get_nonexistent_returns_404(self, test_client):
        """Should return RFC 7807 error for missing transcript."""
        client, db, _ = test_client
        fake_id = uuid4()

        with patch("src.api.transcripts.TranscriptService") as MockService:
            instance = MockService.return_value
            instance.get_by_id = AsyncMock(return_value=None)

            response = client.get(f"/api/v1/transcripts/{fake_id}")

        assert response.status_code == 404
        data = response.json()
        assert data["type"] == "https://memorywiki.dev/errors/not-found"
        assert "Transcript" in data["title"]
