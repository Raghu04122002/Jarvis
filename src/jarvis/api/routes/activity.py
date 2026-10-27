"""Activity feed endpoint — persisted events, newest first."""

from datetime import datetime

from fastapi import APIRouter, Query

from jarvis.api.dependencies import get_database
from jarvis.services.activity_service import ActivityEvent, list_activity

router = APIRouter(tags=["activity"])


@router.get("/activity")
async def get_activity(
    type: list[str] | None = Query(None, description="Event types to include"),  # noqa: A002
    task_id: str | None = None,
    before: datetime | None = Query(None, description="Only events older than this"),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[ActivityEvent]:
    """List persisted activity events."""
    return await list_activity(
        get_database(), types=type, task_id=task_id, before=before, limit=limit
    )
