"""
Pydantic schemas for API request/response validation.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ── Transcript Schemas ─────────────────────────────────────────


class TranscriptCreate(BaseModel):
    """Request body for creating a new transcript."""
    title: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="A descriptive title for the conversation.",
        examples=["Weekly Standup - June 5"],
    )
    content: str = Field(
        ...,
        min_length=1,
        description="The full text of the conversation transcript.",
        examples=["John: The Atlas migration is 80% done..."],
    )
    participants: Optional[list[str]] = Field(
        default=None,
        description="Optional list of participant names as hints for the LLM.",
        examples=[["John Doe", "Sarah Chen"]],
    )
    occurred_at: Optional[datetime] = Field(
        default=None,
        description="When the conversation occurred. Defaults to ingestion time.",
    )


class TranscriptResponse(BaseModel):
    """Response body for a transcript."""
    id: UUID
    title: str
    content: str
    participants: Optional[list[str]] = None
    occurred_at: Optional[datetime] = None
    status: str
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TranscriptCreatedResponse(BaseModel):
    """Response body after creating a transcript (202 Accepted)."""
    id: UUID
    status: str
    created_at: datetime
    links: dict[str, str]


class TranscriptStatusResponse(BaseModel):
    """Response body for checking transcript processing status."""
    id: UUID
    status: str
    error_message: Optional[str] = None
    processed_entities: Optional[list] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TranscriptListResponse(BaseModel):
    """Paginated list of transcripts."""
    items: list[TranscriptResponse]
    total: int
    page: int
    page_size: int


# ── Memory Schemas ─────────────────────────────────────────────


class MemoryNode(BaseModel):
    """A node in the memory file tree (file or directory)."""
    name: str
    type: str = Field(description="Either 'file' or 'directory'")
    path: str
    size: Optional[int] = None
    last_modified: Optional[datetime] = None
    children_count: Optional[int] = None


class MemoryTreeResponse(BaseModel):
    """Response for ls (list directory) operations."""
    path: str
    type: str = "directory"
    children: list[MemoryNode]


class MemoryFileMetadata(BaseModel):
    """Parsed YAML frontmatter from a memory file."""
    type: Optional[str] = None
    entity: Optional[str] = None
    display_name: Optional[str] = None
    tags: Optional[list[str]] = None
    version: Optional[int] = None
    source_transcripts: Optional[list[str]] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class MemoryFileResponse(BaseModel):
    """Response for cat (read file) operations."""
    path: str
    type: str = "file"
    metadata: Optional[MemoryFileMetadata] = None
    content: str


class GrepMatch(BaseModel):
    """A single line match within a file."""
    line: int
    content: str


class GrepFileResult(BaseModel):
    """Grep matches within a single file."""
    path: str
    matches: list[GrepMatch]
    relevance_score: Optional[float] = None


class GrepResponse(BaseModel):
    """Response for grep (search) operations."""
    query: str
    scope: str
    total_matches: int
    results: list[GrepFileResult]


# ── Error Schemas ──────────────────────────────────────────────


class ErrorResponse(BaseModel):
    """RFC 7807 Problem Details error response."""
    type: str
    title: str
    status: int
    detail: str
    instance: Optional[str] = None
