"""Health check endpoint."""

from datetime import UTC, datetime

from fastapi import APIRouter

from jarvis import __version__

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str | bool]:
    return {
        "status": "ok",
        "service": "jarvis",
        "version": __version__,
        "timestamp": datetime.now(UTC).isoformat(),
    }
