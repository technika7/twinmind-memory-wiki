"""
Integration tests for memory API endpoints (ls, cat, grep).

Tests use a mocked StorageService to verify the API layer handles
file tree operations correctly.
"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

from fastapi.testclient import TestClient


@pytest.fixture
def memory_test_client():
    """Create a test client with mocked storage service."""
    from src.main import app
    from src.db.session import get_db

    async def override_get_db():
        yield MagicMock()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


class TestMemoryTree:
    """Test GET /api/v1/memories/tree (ls equivalent)."""

    def test_list_root_directory(self, memory_test_client):
        """Should return top-level directories."""
        mock_entries = [
            {"name": "people", "type": "directory", "path": "/people"},
            {"name": "topics", "type": "directory", "path": "/topics"},
            {"name": "events", "type": "directory", "path": "/events"},
        ]

        with patch("src.services.memory_service.StorageService") as MockStorage:
            instance = MockStorage.return_value
            instance.list_directory.return_value = mock_entries

            response = memory_test_client.get("/api/v1/memories/tree?path=/")

        assert response.status_code == 200
        data = response.json()
        assert data["path"] == "/"
        assert data["type"] == "directory"
        assert len(data["children"]) == 3

    def test_list_subdirectory(self, memory_test_client):
        """Should list files in a subdirectory."""
        mock_entries = [
            {
                "name": "profile.md",
                "type": "file",
                "path": "/people/john_doe/profile.md",
                "size": 512,
                "last_modified": "2026-06-05T10:00:00+00:00",
            },
        ]

        with patch("src.services.memory_service.StorageService") as MockStorage:
            instance = MockStorage.return_value
            instance.list_directory.return_value = mock_entries

            response = memory_test_client.get(
                "/api/v1/memories/tree?path=/people/john_doe&depth=0"
            )

        assert response.status_code == 200
        data = response.json()
        assert len(data["children"]) == 1
        assert data["children"][0]["name"] == "profile.md"
        assert data["children"][0]["type"] == "file"

    def test_list_empty_directory(self, memory_test_client):
        """Empty directory should return empty children list."""
        with patch("src.services.memory_service.StorageService") as MockStorage:
            instance = MockStorage.return_value
            instance.list_directory.return_value = []

            response = memory_test_client.get("/api/v1/memories/tree?path=/empty")

        assert response.status_code == 200
        data = response.json()
        assert data["children"] == []


class TestMemoryFile:
    """Test GET /api/v1/memories/file (cat equivalent)."""

    def test_read_file_with_frontmatter(self, memory_test_client):
        """Should return file content with parsed frontmatter metadata."""
        mock_content = """---
type: person_profile
entity: john_doe
display_name: "John Doe"
tags: ["engineering", "role"]
version: 2
source_transcripts: ["tr_123", "tr_456"]
created_at: "2026-06-05T10:00:00Z"
updated_at: "2026-06-05T14:00:00Z"
---

# John Doe

## Role & Context
Senior Engineer at Acme Corp.
"""

        with patch("src.services.memory_service.StorageService") as MockStorage:
            instance = MockStorage.return_value
            instance.read_file.return_value = mock_content

            response = memory_test_client.get(
                "/api/v1/memories/file?path=/people/john_doe/profile.md"
            )

        assert response.status_code == 200
        data = response.json()
        assert data["path"] == "/people/john_doe/profile.md"
        assert data["type"] == "file"
        assert data["metadata"]["entity"] == "john_doe"
        assert data["metadata"]["display_name"] == "John Doe"
        assert data["metadata"]["version"] == 2
        assert "# John Doe" in data["content"]

    def test_read_nonexistent_file_returns_404(self, memory_test_client):
        """Should return 404 for missing files."""
        with patch("src.services.memory_service.StorageService") as MockStorage:
            instance = MockStorage.return_value
            instance.read_file.return_value = None

            response = memory_test_client.get(
                "/api/v1/memories/file?path=/nonexistent.md"
            )

        assert response.status_code == 404

    def test_read_file_without_frontmatter(self, memory_test_client):
        """Plain markdown without frontmatter should still work."""
        with patch("src.services.memory_service.StorageService") as MockStorage:
            instance = MockStorage.return_value
            instance.read_file.return_value = "# Simple File\n\nJust some content."

            response = memory_test_client.get(
                "/api/v1/memories/file?path=/simple.md"
            )

        assert response.status_code == 200
        data = response.json()
        assert "Simple File" in data["content"]


class TestMemorySearch:
    """Test GET /api/v1/memories/search (grep equivalent)."""

    def test_search_returns_matches(self, memory_test_client):
        """Should return line-level matches across files."""
        mock_results = [
            {
                "path": "/topics/project_atlas/overview.md",
                "matches": [
                    {"line": 3, "content": "Project Atlas is a migration initiative"},
                    {"line": 12, "content": "Atlas milestone 2 completed"},
                ],
            },
            {
                "path": "/people/john_doe/profile.md",
                "matches": [
                    {"line": 8, "content": "Leads the Atlas project"},
                ],
            },
        ]

        with patch("src.services.memory_service.StorageService") as MockStorage:
            instance = MockStorage.return_value
            instance.search_files.return_value = mock_results

            response = memory_test_client.get(
                "/api/v1/memories/search?q=atlas&path=/"
            )

        assert response.status_code == 200
        data = response.json()
        assert data["query"] == "atlas"
        assert data["scope"] == "/"
        assert data["total_matches"] == 3
        assert len(data["results"]) == 2

    def test_search_no_results(self, memory_test_client):
        """Should return empty results for no matches."""
        with patch("src.services.memory_service.StorageService") as MockStorage:
            instance = MockStorage.return_value
            instance.search_files.return_value = []

            response = memory_test_client.get(
                "/api/v1/memories/search?q=nonexistent&path=/"
            )

        assert response.status_code == 200
        data = response.json()
        assert data["total_matches"] == 0
        assert data["results"] == []

    def test_search_requires_query(self, memory_test_client):
        """Should return 422 if query is missing."""
        response = memory_test_client.get("/api/v1/memories/search")
        assert response.status_code == 422

    def test_search_scoped_to_directory(self, memory_test_client):
        """Should pass the path scope to the storage service."""
        with patch("src.services.memory_service.StorageService") as MockStorage:
            instance = MockStorage.return_value
            instance.search_files.return_value = []

            memory_test_client.get(
                "/api/v1/memories/search?q=test&path=/topics"
            )

            instance.search_files.assert_called_once()
            call_args = instance.search_files.call_args
            assert call_args[1]["path"] == "/topics" or call_args[0][1] == "/topics"
