"""
Health check endpoint.
"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check():
    """Simple liveness probe."""
    return {
        "status": "healthy",
        "service": "memory-wiki",
        "version": "1.0.0",
    }
