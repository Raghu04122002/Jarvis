"""Jarvis FastAPI application."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from jarvis import __version__
from jarvis.api.dependencies import get_database, init_dependencies, reset_dependencies
from jarvis.api.routes.approvals import router as approvals_router
from jarvis.api.routes.health import router as health_router
from jarvis.api.routes.memory import router as memory_router
from jarvis.api.routes.projects import router as projects_router
from jarvis.api.routes.tasks import router as tasks_router
from jarvis.config import JarvisConfig, load_config
from jarvis.logging import setup_logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info("Jarvis %s starting up", __version__)
    config: JarvisConfig = app.state.config
    init_dependencies(config)
    db = get_database()
    await db.connect()
    yield
    await db.disconnect()
    reset_dependencies()
    logger.info("Jarvis shutting down")


def create_app(config: JarvisConfig | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    if config is None:
        config = load_config()

    setup_logging(config.logging)

    app = FastAPI(
        title="Jarvis",
        version=__version__,
        description="Local-first personal AI orchestration system",
        lifespan=lifespan,
    )

    # Store config on app state for access in routes
    app.state.config = config

    # Register routes
    app.include_router(health_router)
    app.include_router(tasks_router)
    app.include_router(projects_router)
    app.include_router(memory_router)
    app.include_router(approvals_router)

    # Global exception handler
    @app.exception_handler(Exception)
    async def unhandled_exception(request: Request, exc: Exception) -> JSONResponse:
        logger.error("Unhandled error on %s %s: %s", request.method, request.url.path, exc)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )

    return app
