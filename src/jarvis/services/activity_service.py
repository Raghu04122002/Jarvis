"""Activity feed — persists EventBus events so they survive a reload/restart.

The EventBus is synchronous, so the recorder just queues events from the
handler and a background task writes them to the database in batches.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel
from sqlalchemy import select

from jarvis.db.engine import Database
from jarvis.db.tables import ActivityEventRow
from jarvis.events import Event, EventBus, EventType

logger = logging.getLogger(__name__)

_BATCH = 100


class ActivityEvent(BaseModel):
    """One entry in the activity feed."""

    id: str
    type: str
    task_id: str | None = None
    data: dict[str, Any]
    timestamp: datetime


def _jsonable(value: Any) -> Any:
    """Coerce event payloads into something the JSON column can store."""
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, list | tuple | set):
        return [_jsonable(v) for v in value]
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


class ActivityRecorder:
    """Subscribes to every event type and writes events to the database."""

    def __init__(self, event_bus: EventBus, db: Database) -> None:
        self._bus = event_bus
        self._db = db
        self._queue: asyncio.Queue[Event] = asyncio.Queue()
        self._task: asyncio.Task[None] | None = None

    def _on_event(self, event: Event) -> None:
        self._queue.put_nowait(event)

    def start(self) -> None:
        if self._task is not None:
            return
        for event_type in EventType:
            self._bus.subscribe(event_type, self._on_event)
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        for event_type in EventType:
            self._bus.unsubscribe(event_type, self._on_event)
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        await self.flush()

    async def flush(self) -> None:
        """Write everything currently queued."""
        while not self._queue.empty():
            batch = [self._queue.get_nowait()]
            while len(batch) < _BATCH and not self._queue.empty():
                batch.append(self._queue.get_nowait())
            await self._write(batch)

    async def _run(self) -> None:
        while True:
            first = await self._queue.get()
            batch = [first]
            while len(batch) < _BATCH and not self._queue.empty():
                batch.append(self._queue.get_nowait())
            await self._write(batch)

    async def _write(self, batch: list[Event]) -> None:
        try:
            async with self._db.session() as session:
                for event in batch:
                    session.add(
                        ActivityEventRow(
                            id=uuid.uuid4().hex,
                            type=event.type.value,
                            task_id=event.task_id,
                            data=_jsonable(event.data),
                            created_at=event.timestamp,
                        )
                    )
                await session.commit()
        except Exception:
            logger.exception("Failed to persist %d activity event(s)", len(batch))


async def list_activity(
    db: Database,
    *,
    types: list[str] | None = None,
    task_id: str | None = None,
    before: datetime | None = None,
    limit: int = 100,
) -> list[ActivityEvent]:
    """Newest-first activity, optionally filtered by type, task, or time."""
    stmt = select(ActivityEventRow)
    if types:
        stmt = stmt.where(ActivityEventRow.type.in_(types))
    if task_id:
        stmt = stmt.where(ActivityEventRow.task_id == task_id)
    if before is not None:
        stmt = stmt.where(ActivityEventRow.created_at < before)
    stmt = stmt.order_by(ActivityEventRow.created_at.desc()).limit(limit)
    async with db.session() as session:
        rows = (await session.execute(stmt)).scalars().all()
    return [
        ActivityEvent(
            id=r.id, type=r.type, task_id=r.task_id, data=r.data or {}, timestamp=r.created_at
        )
        for r in rows
    ]
