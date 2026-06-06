"""
Memory service — business logic for memory tree operations.

Provides ls, cat, and grep functionality over the S3-backed memory tree,
with frontmatter parsing for metadata extraction.
"""

import logging
from typing import Optional

import frontmatter

from src.models.schemas import (
    GrepFileResult,
    GrepMatch,
    MemoryFileMetadata,
    MemoryFileResponse,
    MemoryNode,
)
from src.services.storage_service import StorageService

logger = logging.getLogger(__name__)


class MemoryService:
    """High-level operations on the memory file tree."""

    def __init__(self):
        self.storage = StorageService()

    def list_directory(
        self, path: str = "/", depth: Optional[int] = None
    ) -> list[MemoryNode]:
        """
        List contents of a memory directory (ls equivalent).

        Args:
            path: Directory path to list.
            depth: 0 for immediate children, None for recursive (immediate dirs).
        """
        entries = self.storage.list_directory(
            path=path, depth=0 if depth == 0 else None
        )

        nodes = []
        for entry in entries:
            node = MemoryNode(
                name=entry["name"],
                type=entry["type"],
                path=entry["path"],
                size=entry.get("size"),
                last_modified=entry.get("last_modified"),
            )
            nodes.append(node)

        return nodes

    def read_file(self, path: str) -> Optional[MemoryFileResponse]:
        """
        Read a memory file with parsed frontmatter (cat equivalent).

        Returns both the content and extracted metadata from YAML frontmatter.
        """
        raw_content = self.storage.read_file(path)
        if raw_content is None:
            return None

        # Parse YAML frontmatter
        metadata = None
        content = raw_content

        try:
            post = frontmatter.loads(raw_content)
            if post.metadata:
                metadata = MemoryFileMetadata(
                    type=post.metadata.get("type"),
                    entity=post.metadata.get("entity"),
                    display_name=post.metadata.get("display_name"),
                    tags=post.metadata.get("tags"),
                    version=post.metadata.get("version"),
                    source_transcripts=post.metadata.get("source_transcripts"),
                    created_at=str(post.metadata.get("created_at", "")),
                    updated_at=str(post.metadata.get("updated_at", "")),
                )
            content = post.content
        except Exception as e:
            logger.warning("Failed to parse frontmatter for %s: %s", path, e)
            # Fall back to raw content without metadata

        return MemoryFileResponse(
            path=path,
            type="file",
            metadata=metadata,
            content=content,
        )

    def search(
        self,
        query: str,
        path: str = "/",
        case_insensitive: bool = True,
    ) -> list[GrepFileResult]:
        """
        Search for text pattern across memory files (grep equivalent).

        Returns structured results with line numbers and matching content.
        """
        raw_results = self.storage.search_files(
            query=query,
            path=path,
            case_insensitive=case_insensitive,
        )

        results = []
        for raw in raw_results:
            matches = [
                GrepMatch(line=m["line"], content=m["content"]) for m in raw["matches"]
            ]
            results.append(
                GrepFileResult(
                    path=raw["path"],
                    matches=matches,
                )
            )

        # Sort by number of matches (most relevant first)
        results.sort(key=lambda r: len(r.matches), reverse=True)

        return results
