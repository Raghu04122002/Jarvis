"""Tests for the SSE streaming endpoint."""

import asyncio
import json

import pytest

from jarvis.api.routes.events import _event_to_sse
from jarvis.events import Event, EventType


def test_event_to_sse_format() -> None:
    """SSE formatter produces correct event stream lines."""
    event = Event(
        type=EventType.TASK_CREATED,
        task_id="t1",
        data={"title": "hello"},
    )
    result = _event_to_sse(event)
    assert result.startswith("event: task_created\n")
    assert "data: " in result
    assert result.endswith("\n\n")

    data_line = result.split("\n")[1]
    payload = json.loads(data_line.removeprefix("data: "))
    assert payload["type"] == "task_created"
    assert payload["task_id"] == "t1"
    assert payload["data"]["title"] == "hello"
    assert "timestamp" in payload


@pytest.mark.asyncio
async def test_sse_generator_yields_events() -> None:
    """The SSE generator yields events from the EventBus queue."""
    from jarvis.api.routes.events import _event_generator
    from jarvis.db.engine import Database

    db = Database.__new__(Database)
    db._engine = None  # type: ignore[assignment]
    from jarvis.api.dependencies import reset_dependencies

    reset_dependencies()

    # Re-init with a minimal setup
    import jarvis.api.dependencies as deps
    from jarvis.events import EventBus

    deps._event_bus = EventBus()
    event_bus = deps._event_bus

    async def publish_soon() -> None:
        await asyncio.sleep(0.05)
        event_bus.publish(
            Event(type=EventType.TASK_CREATED, task_id="t1", data={"key": "val"})
        )

    task = asyncio.create_task(publish_soon())

    collected: list[str] = []
    async with asyncio.timeout(2):
        async for chunk in _event_generator():
            collected.append(chunk)
            if "task_created" in chunk:
                break

    task.cancel()
    assert len(collected) >= 1
    assert "event: task_created" in collected[0]
    assert '"task_id": "t1"' in collected[0]

    # Cleanup
    deps._event_bus = None


@pytest.mark.asyncio
async def test_sse_generator_filters_by_task_id() -> None:
    """The SSE generator filters by task_id."""
    import jarvis.api.dependencies as deps
    from jarvis.api.routes.events import _event_generator
    from jarvis.events import EventBus

    deps._event_bus = EventBus()
    event_bus = deps._event_bus

    async def publish_events() -> None:
        await asyncio.sleep(0.05)
        event_bus.publish(
            Event(type=EventType.TASK_CREATED, task_id="other", data={})
        )
        await asyncio.sleep(0.02)
        event_bus.publish(
            Event(type=EventType.TASK_COMPLETED, task_id="target", data={})
        )

    task = asyncio.create_task(publish_events())

    collected: list[str] = []
    async with asyncio.timeout(2):
        async for chunk in _event_generator(task_id="target"):
            collected.append(chunk)
            if "task_completed" in chunk:
                break

    task.cancel()
    combined = "".join(collected)
    assert "task_completed" in combined
    assert "task_created" not in combined

    deps._event_bus = None


def test_sse_endpoint_is_registered() -> None:
    """The SSE endpoint is registered on the app."""
    from jarvis.api.routes.events import router

    paths = [r.path for r in router.routes]  # type: ignore[union-attr]
    assert "/events/stream" in paths


@pytest.mark.asyncio
async def test_event_bus_unsubscribe() -> None:
    """EventBus.unsubscribe removes a specific handler."""
    from jarvis.events import EventBus

    bus = EventBus()
    calls: list[str] = []

    def handler1(e: Event) -> None:
        calls.append("h1")

    def handler2(e: Event) -> None:
        calls.append("h2")

    bus.subscribe(EventType.TASK_CREATED, handler1)
    bus.subscribe(EventType.TASK_CREATED, handler2)

    bus.publish(Event(type=EventType.TASK_CREATED, task_id="t1"))
    assert calls == ["h1", "h2"]

    calls.clear()
    bus.unsubscribe(EventType.TASK_CREATED, handler1)
    bus.publish(Event(type=EventType.TASK_CREATED, task_id="t1"))
    assert calls == ["h2"]


@pytest.mark.asyncio
async def test_event_bus_unsubscribe_missing_handler() -> None:
    """Unsubscribing a non-existent handler doesn't raise."""
    from jarvis.events import EventBus

    bus = EventBus()

    def handler(e: Event) -> None:
        pass

    # Should not raise
    bus.unsubscribe(EventType.TASK_CREATED, handler)
