"""Notification service — dispatches notifications to registered providers."""

import logging
from typing import Any

from jarvis.events import Event, EventBus, EventType
from jarvis.notifications.base import NotificationProvider

logger = logging.getLogger(__name__)


class NotificationService:
    """Fan-out notifications to all registered providers."""

    def __init__(
        self,
        event_bus: EventBus,
        providers: list[NotificationProvider] | None = None,
    ) -> None:
        self._event_bus = event_bus
        self._providers: list[NotificationProvider] = list(providers) if providers else []

    def add_provider(self, provider: NotificationProvider) -> None:
        self._providers.append(provider)

    async def notify(
        self,
        title: str,
        body: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        for provider in self._providers:
            try:
                await provider.send(title, body, metadata)
                self._event_bus.publish(
                    Event(
                        type=EventType.NOTIFICATION_SENT,
                        task_id="",
                        data={"provider": provider.name, "title": title},
                    )
                )
            except Exception:
                logger.exception("Notification provider %s failed", provider.name)
                self._event_bus.publish(
                    Event(
                        type=EventType.NOTIFICATION_FAILED,
                        task_id="",
                        data={"provider": provider.name, "title": title},
                    )
                )
