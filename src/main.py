"""
FastAPI application factory.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import get_settings
from src.api.router import api_router
from src.api.errors import register_error_handlers
from src.db.session import engine
from src.services.storage_service import StorageService


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle."""
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)

    # Ensure S3 bucket exists on startup
    storage = StorageService()
    storage.ensure_bucket()
    logger.info("MinIO bucket '%s' ready", settings.s3_bucket_name)

    yield

    # Shutdown: dispose database engine
    await engine.dispose()
    logger.info("Application shutdown complete")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="Memory Wiki",
        description=(
            "A service that ingests conversation transcripts, generates memories "
            "using an LLM, stores them in a file-system-like structure, and "
            "exposes them via unix-style REST endpoints."
        ),
        version="1.0.0",
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routes
    app.include_router(api_router, prefix="/api/v1")

    # Register global error handlers
    register_error_handlers(app)

    return app


# Module-level app instance for uvicorn
app = create_app()
