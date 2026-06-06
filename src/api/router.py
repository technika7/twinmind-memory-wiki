"""
Top-level API router that aggregates all sub-routers.
"""

from fastapi import APIRouter

from src.api.health import router as health_router
from src.api.transcripts import router as transcripts_router
from src.api.memories import router as memories_router

api_router = APIRouter()

api_router.include_router(health_router, tags=["Health"])
api_router.include_router(transcripts_router, prefix="/transcripts", tags=["Transcripts"])
api_router.include_router(memories_router, prefix="/memories", tags=["Memories"])
