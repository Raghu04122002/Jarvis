"""Tests for activity persistence (events survive a reload)."""

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient

from jarvis.api.dependencies import get_database, get_event_bus
from jarvis.db.engine import Database
from jarvis.events import Event, EventBus, EventType
from jarvis.services.activity_service import ActivityRecorder, list_activity


class _Obj:
    def __str__(self) -> str:
        return "obj"


@pytest.mark.asyncio
async def test_recorder_persists_events(db: Database) -> None:
    bus = EventBus()
    rec = ActivityRecorder(bus, db)
    rec.start()
    t0 = datetime.now(UTC)
    bus.publish(
        Event(type=EventType.TASK_CREATED, task_id="TASK-1", data={"title": "a"}, timestamp=t0)
    )
    bus.publish(
        Event(
            type=EventType.TASK_FAILED,
            task_id="TASK-1",
            data={"error": "boom", "odd": _Obj(), "when": t0},
            timestamp=t0 + timedelta(seconds=1),
        )
    )
    await rec.stop()  # flushes the queue

    events = await list_activity(db)
    assert [e.type for e in events] == ["task_failed", "task_created"]  # newest first
    assert events[0].data == {"error": "boom", "odd": "obj", "when": t0.isoformat()}

    only_failed = await list_activity(db, types=["task_failed"])
    assert [e.task_id for e in only_failed] == ["TASK-1"]
    older = await list_activity(db, before=t0 + timedelta(milliseconds=500))
    assert [e.type for e in older] == ["task_created"]


@pytest.mark.asyncio
async def test_stop_unsubscribes(db: Database) -> None:
    bus = EventBus()
    rec = ActivityRecorder(bus, db)
    rec.start()
    await rec.stop()
    bus.publish(Event(type=EventType.TASK_CREATED, task_id="TASK-2", data={}))
    await rec.flush()
    assert await list_activity(db) == []


@pytest.mark.asyncio
async def test_activity_endpoint(client: AsyncClient) -> None:
    rec = ActivityRecorder(get_event_bus(), get_database())
    rec.start()
    resp = await client.post("/chat", json={"message": "Fix the login issue"})
    assert resp.status_code == 200
    await rec.stop()

    resp = await client.get("/activity")
    assert resp.status_code == 200
    types = [e["type"] for e in resp.json()]
    assert "task_created" in types

    resp = await client.get("/activity", params={"type": "task_created"})
    assert {e["type"] for e in resp.json()} == {"task_created"}
