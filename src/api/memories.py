"""
Memory API endpoints — unix-style file tree operations.

GET /memories/tree     — ls (list directory)
GET /memories/file     — cat (read file content)
GET /memories/search   — grep (search across files)
"""

import logging

from fastapi import APIRouter, Query

from src.api.errors import NotFoundError
from src.services.memory_service import MemoryService
from src.models.schemas import (
    MemoryTreeResponse,
    MemoryFileResponse,
    GrepResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/tree",
    response_model=MemoryTreeResponse,
    summary="List directory contents (ls)",
    description=(
        "Lists the contents of a directory in the memory file tree. "
        "Equivalent to `ls /path`. Use depth=0 for non-recursive listing."
    ),
)
async def list_tree(
    path: str = Query("/", description="Directory path to list"),
    depth: int | None = Query(None, ge=0, description="0 for immediate children only, None for recursive"),
):
    service = MemoryService()
    children = service.list_directory(path=path, depth=depth)

    return MemoryTreeResponse(
        path=path,
        type="directory",
        children=children,
    )


@router.get(
    "/file",
    response_model=MemoryFileResponse,
    summary="Read file content (cat)",
    description=(
        "Reads the content of a file in the memory tree, including parsed "
        "YAML frontmatter metadata. Equivalent to `cat /path/to/file.md`."
    ),
)
async def read_file(
    path: str = Query(..., description="Full path to the file"),
):
    service = MemoryService()
    result = service.read_file(path=path)

    if result is None:
        raise NotFoundError("Memory file", path)

    return result


@router.get(
    "/search",
    response_model=GrepResponse,
    summary="Search file contents (grep)",
    description=(
        "Searches for a text pattern across all files under a given path. "
        "Returns line numbers and matching content, similar to `grep -rn`."
    ),
)
async def search_files(
    q: str = Query(..., min_length=1, description="Search query (literal text match)"),
    path: str = Query("/", description="Directory scope for the search"),
    case_insensitive: bool = Query(True, description="Case-insensitive search"),
):
    service = MemoryService()
    results = service.search(query=q, path=path, case_insensitive=case_insensitive)

    total_matches = sum(len(r.matches) for r in results)

    return GrepResponse(
        query=q,
        scope=path,
        total_matches=total_matches,
        results=results,
    )
