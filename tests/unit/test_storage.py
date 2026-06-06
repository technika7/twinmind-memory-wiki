"""
Unit tests for storage service path normalization and logic.
"""

from src.services.storage_service import StorageService


class TestPathNormalization:
    """Test the path normalization logic independent of S3."""

    def test_strips_leading_slash(self):
        assert StorageService._normalize_path("/people/john") == "people/john"

    def test_strips_multiple_leading_slashes(self):
        assert StorageService._normalize_path("///people/john") == "people/john"

    def test_collapses_double_slashes(self):
        assert (
            StorageService._normalize_path("people//john//profile.md")
            == "people/john/profile.md"
        )

    def test_resolves_parent_references(self):
        assert (
            StorageService._normalize_path("/people/../topics/atlas") == "topics/atlas"
        )

    def test_resolves_current_dir_references(self):
        assert StorageService._normalize_path("/people/./john") == "people/john"

    def test_empty_path(self):
        assert StorageService._normalize_path("") == ""

    def test_root_path(self):
        assert StorageService._normalize_path("/") == ""

    def test_complex_path(self):
        assert (
            StorageService._normalize_path("//people/../people/john_doe/./profile.md")
            == "people/john_doe/profile.md"
        )

    def test_parent_beyond_root(self):
        """Parent references shouldn't go above root."""
        assert StorageService._normalize_path("/../../people") == "people"
