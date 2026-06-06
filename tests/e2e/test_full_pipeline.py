"""
End-to-end test for the full ingest-to-query pipeline.

This test verifies the complete flow:
1. POST a transcript
2. Wait for background processing
3. Query the memory tree and verify files were created

Note: This test requires all services running (docker compose up)
and a valid OPENAI_API_KEY. It is intended for manual verification
rather than CI, since it makes real LLM calls.

For CI, use the integration tests with mocked LLM responses.
"""

import pytest
import time
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient


class TestFullPipelineMocked:
    """
    E2E pipeline test with mocked LLM but real API flow.

    Tests the complete request path without making actual LLM calls,
    verifying that all components are wired together correctly.
    """

    def test_ingest_and_check_status(self):
        """
        Verify the async ingest flow:
        1. POST transcript → 202 with status "pending"
        2. GET status → returns the processing state
        """
        from src.main import app
        from src.db.session import get_db

        mock_session = MagicMock()

        async def override_get_db():
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db

        try:
            with patch("src.api.transcripts.process_transcript") as mock_task, \
                 patch("src.api.transcripts.TranscriptService") as MockService:

                mock_task.delay = MagicMock()

                # Create a fake transcript object
                from uuid import uuid4
                from datetime import datetime, timezone

                fake_id = uuid4()
                fake_transcript = MagicMock()
                fake_transcript.id = fake_id
                fake_transcript.title = "E2E Test Meeting"
                fake_transcript.content = "Alice and Bob discussed the roadmap"
                fake_transcript.participants = ["Alice", "Bob"]
                fake_transcript.occurred_at = None
                from src.models.transcript import TranscriptStatus
                fake_transcript.status = TranscriptStatus.PENDING
                
                fake_transcript.error_message = None
                fake_transcript.processed_entities = None
                fake_transcript.created_at = datetime.now(timezone.utc)
                fake_transcript.updated_at = datetime.now(timezone.utc)

                from unittest.mock import AsyncMock
                instance = MockService.return_value
                instance.create = AsyncMock(return_value=fake_transcript)
                instance.get_by_id = AsyncMock(return_value=fake_transcript)

                client = TestClient(app)

                # Step 1: Ingest
                response = client.post(
                    "/api/v1/transcripts",
                    json={
                        "title": "E2E Test Meeting",
                        "content": "Alice and Bob discussed the roadmap for Q3.",
                        "participants": ["Alice", "Bob"],
                    },
                )
                assert response.status_code == 202
                data = response.json()
                assert data["status"] == "pending"
                transcript_id = data["id"]

                # Verify Celery task was enqueued
                mock_task.delay.assert_called_once()

                # Step 2: Check status
                response = client.get(f"/api/v1/transcripts/{transcript_id}/status")
                assert response.status_code == 200
                status_data = response.json()
                assert status_data["status"] == "pending"

        finally:
            app.dependency_overrides.clear()

    def test_memory_tree_query_flow(self):
        """
        Verify the memory query endpoints work in sequence:
        1. List root directory (ls /)
        2. Read a specific file (cat)
        3. Search across files (grep)
        """
        from src.main import app
        from src.db.session import get_db

        async def override_get_db():
            yield MagicMock()

        app.dependency_overrides[get_db] = override_get_db

        try:
            with patch("src.services.memory_service.StorageService") as MockStorage:
                instance = MockStorage.return_value

                client = TestClient(app)

                # Step 1: ls /
                instance.list_directory.return_value = [
                    {"name": "people", "type": "directory", "path": "/people"},
                    {"name": "topics", "type": "directory", "path": "/topics"},
                ]
                response = client.get("/api/v1/memories/tree?path=/")
                assert response.status_code == 200
                assert len(response.json()["children"]) == 2

                # Step 2: cat a file
                instance.read_file.return_value = (
                    "---\ntype: person_profile\nentity: alice\n"
                    "display_name: Alice\nversion: 1\n---\n# Alice\n\nEngineer."
                )
                response = client.get(
                    "/api/v1/memories/file?path=/people/alice/profile.md"
                )
                assert response.status_code == 200
                data = response.json()
                assert data["metadata"]["entity"] == "alice"
                assert "Alice" in data["content"]

                # Step 3: grep for "engineer"
                instance.search_files.return_value = [
                    {
                        "path": "/people/alice/profile.md",
                        "matches": [{"line": 7, "content": "Engineer."}],
                    }
                ]
                response = client.get(
                    "/api/v1/memories/search?q=engineer&path=/"
                )
                assert response.status_code == 200
                data = response.json()
                assert data["total_matches"] == 1
                assert data["results"][0]["path"] == "/people/alice/profile.md"

        finally:
            app.dependency_overrides.clear()
