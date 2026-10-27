"""SSE streaming endpoint for real-time event delivery."""

import asyncio
import json
import logging
from collections.abc import AsyncIterator

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from jarvis.api.dependencies import get_event_bus
from jarvis.events import Event, EventType

router = APIRouter(prefix="/events", tags=["events"])
logger = logging.getLogger(__name__)

KEEPALIVE_INTERVAL = 30  # seconds


def _event_to_sse(event: Event) -> str:
    """Format an Event as an SSE string."""
    data = {
        "type": event.type.value,
        "task_id": event.task_id,
        "timestamp": event.timestamp.isoformat(),
        "data": event.data,
    }
    return f"event: {event.type.value}\ndata: {json.dumps(data)}\n\n"


async def _event_generator(
    task_id: str | None = None,
) -> AsyncIterator[str]:
    """Yield SSE-formatted events from the EventBus."""
    event_bus = get_event_bus()
    queue: asyncio.Queue[Event] = asyncio.Queue()

    def handler(event: Event) -> None:
        queue.put_nowait(event)

    # Subscribe to all event types
    for event_type in EventType:
        event_bus.subscribe(event_type, handler)

    try:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=KEEPALIVE_INTERVAL)
                if task_id and event.task_id != task_id:
                    continue
                yield _event_to_sse(event)
            except TimeoutError:
                yield ": keepalive\n\n"
    except asyncio.CancelledError:
        pass
    finally:
        for event_type in EventType:
            event_bus.unsubscribe(event_type, handler)


@router.get("/stream")
async def stream_events(
    task_id: str | None = Query(None, description="Filter events by task ID"),
) -> StreamingResponse:
    """Stream real-time events via Server-Sent Events."""
    return StreamingResponse(
        _event_generator(task_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
