"""Tests for the event bus and audit logger."""

from jarvis.audit.logger import AuditLogger
from jarvis.events import Event, EventBus, EventType


class TestEventBus:
    def test_subscribe_and_publish(self) -> None:
        bus = EventBus()
        received: list[Event] = []
        bus.subscribe(EventType.TASK_CREATED, received.append)
        event = Event(type=EventType.TASK_CREATED, task_id="t1")
        bus.publish(event)
        assert len(received) == 1
        assert received[0].task_id == "t1"

    def test_unsubscribed_events_ignored(self) -> None:
        bus = EventBus()
        received: list[Event] = []
        bus.subscribe(EventType.TASK_CREATED, received.append)
        bus.publish(Event(type=EventType.TASK_COMPLETED, task_id="t1"))
        assert len(received) == 0

    def test_handler_error_does_not_propagate(self) -> None:
        bus = EventBus()

        def bad_handler(event: Event) -> None:
            raise RuntimeError("boom")

        bus.subscribe(EventType.TASK_CREATED, bad_handler)
        # Should not raise
        bus.publish(Event(type=EventType.TASK_CREATED, task_id="t1"))

    def test_clear(self) -> None:
        bus = EventBus()
        received: list[Event] = []
        bus.subscribe(EventType.TASK_CREATED, received.append)
        bus.clear()
        bus.publish(Event(type=EventType.TASK_CREATED, task_id="t1"))
        assert len(received) == 0


class TestAuditLogger:
    def test_records_task_created(self) -> None:
        bus = EventBus()
        audit = AuditLogger(bus)
        bus.publish(Event(type=EventType.TASK_CREATED, task_id="t1"))
        entries = audit.get_entries()
        assert len(entries) == 1
        assert entries[0].action == "task_created"
        assert entries[0].task_id == "t1"
        assert entries[0].success is True

    def test_records_task_failed(self) -> None:
        bus = EventBus()
        audit = AuditLogger(bus)
        bus.publish(Event(type=EventType.TASK_FAILED, task_id="t2"))
        entries = audit.get_entries()
        assert entries[0].success is False

    def test_filter_by_task_id(self) -> None:
        bus = EventBus()
        audit = AuditLogger(bus)
        bus.publish(Event(type=EventType.TASK_CREATED, task_id="t1"))
        bus.publish(Event(type=EventType.TASK_CREATED, task_id="t2"))
        assert len(audit.get_entries(task_id="t1")) == 1
        assert len(audit.get_entries(task_id="t2")) == 1

    def test_clear(self) -> None:
        bus = EventBus()
        audit = AuditLogger(bus)
        bus.publish(Event(type=EventType.TASK_CREATED, task_id="t1"))
        audit.clear()
        assert len(audit.get_entries()) == 0
