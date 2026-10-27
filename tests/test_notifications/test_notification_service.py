"""Tests for the NotificationService."""

from typing import Any

import pytest

from jarvis.events import Event, EventBus, EventType
from jarvis.services.notification_service import NotificationService


class FakeNotificationProvider:
    """Test provider that records calls."""

    def __init__(self, *, fail: bool = False) -> None:
        self._fail = fail
        self.calls: list[tuple[str, str, dict[str, Any] | None]] = []

    @property
    def name(self) -> str:
        return "fake"

    async def send(
        self, title: str, body: str, metadata: dict[str, Any] | None = None
    ) -> None:
        self.calls.append((title, body, metadata))
        if self._fail:
            raise RuntimeError("Provider failed")


class FailingProvider:
    """Provider that always raises."""

    @property
    def name(self) -> str:
        return "failing"

    async def send(
        self, title: str, body: str, metadata: dict[str, Any] | None = None
    ) -> None:
        raise RuntimeError("Always fails")


@pytest.fixture
def event_bus() -> EventBus:
    return EventBus()


class TestNotificationService:
    @pytest.mark.asyncio
    async def test_send_to_single_provider(self, event_bus: EventBus) -> None:
        provider = FakeNotificationProvider()
        service = NotificationService(event_bus, [provider])
        await service.notify("Title", "Body", {"key": "value"})
        assert len(provider.calls) == 1
        assert provider.calls[0] == ("Title", "Body", {"key": "value"})

    @pytest.mark.asyncio
    async def test_send_to_multiple_providers(self, event_bus: EventBus) -> None:
        p1 = FakeNotificationProvider()
        p2 = FakeNotificationProvider()
        service = NotificationService(event_bus, [p1, p2])
        await service.notify("Test", "Message")
        assert len(p1.calls) == 1
        assert len(p2.calls) == 1

    @pytest.mark.asyncio
    async def test_add_provider(self, event_bus: EventBus) -> None:
        service = NotificationService(event_bus)
        provider = FakeNotificationProvider()
        service.add_provider(provider)
        await service.notify("Test", "Message")
        assert len(provider.calls) == 1

    @pytest.mark.asyncio
    async def test_provider_failure_doesnt_stop_others(
        self, event_bus: EventBus
    ) -> None:
        failing = FailingProvider()
        working = FakeNotificationProvider()
        service = NotificationService(event_bus, [failing, working])
        await service.notify("Test", "Message")
        # Working provider should still receive the notification
        assert len(working.calls) == 1

    @pytest.mark.asyncio
    async def test_notification_sent_event(self, event_bus: EventBus) -> None:
        events: list[Event] = []
        event_bus.subscribe(EventType.NOTIFICATION_SENT, events.append)
        provider = FakeNotificationProvider()
        service = NotificationService(event_bus, [provider])
        await service.notify("Test", "Body")
        assert len(events) == 1
        assert events[0].data["provider"] == "fake"

    @pytest.mark.asyncio
    async def test_notification_failed_event(self, event_bus: EventBus) -> None:
        events: list[Event] = []
        event_bus.subscribe(EventType.NOTIFICATION_FAILED, events.append)
        service = NotificationService(event_bus, [FailingProvider()])
        await service.notify("Test", "Body")
        assert len(events) == 1
        assert events[0].data["provider"] == "failing"

    @pytest.mark.asyncio
    async def test_no_providers_no_error(self, event_bus: EventBus) -> None:
        service = NotificationService(event_bus)
        await service.notify("Test", "Body")  # Should not raise
