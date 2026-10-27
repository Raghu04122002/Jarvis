"""Jarvis FastAPI application."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from jarvis import __version__
from jarvis.api.dependencies import (
    get_ai_service,
    get_database,
    get_pxpipe_service,
    get_scheduler_engine,
    init_dependencies,
    reset_dependencies,
)
from jarvis.api.routes.approvals import router as approvals_router
from jarvis.api.routes.events import router as events_router
from jarvis.api.routes.health import router as health_router
from jarvis.api.routes.memory import router as memory_router
from jarvis.api.routes.projects import router as projects_router
from jarvis.api.routes.schedules import router as schedules_router
from jarvis.api.routes.tasks import router as tasks_router
from jarvis.api.routes.voice import router as voice_router
from jarvis.api.routes.workflows import router as workflows_router
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

    # Start pxpipe proxy if enabled
    pxpipe = get_pxpipe_service()
    if pxpipe is not None:
        pxpipe_ok = await pxpipe.start()
        if not pxpipe_ok:
            logger.warning("pxpipe proxy unavailable — using direct Anthropic API")
            ai = get_ai_service()
            ai.set_pxpipe_base_url(None)

    if config.scheduler.enabled:
        get_scheduler_engine().start()
    yield
    if config.scheduler.enabled:
        await get_scheduler_engine().stop()
    if pxpipe is not None:
        await pxpipe.stop()
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

    # CORS middleware for desktop app
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:1420", "tauri://localhost"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routes
    app.include_router(health_router)
    app.include_router(tasks_router)
    app.include_router(projects_router)
    app.include_router(memory_router)
    app.include_router(approvals_router)
    app.include_router(schedules_router)
    app.include_router(events_router)
    app.include_router(voice_router)
    app.include_router(workflows_router)

    # Global exception handler
    @app.exception_handler(Exception)
    async def unhandled_exception(request: Request, exc: Exception) -> JSONResponse:
        logger.error("Unhandled error on %s %s: %s", request.method, request.url.path, exc)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )

    return app
