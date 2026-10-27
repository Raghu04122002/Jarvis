"""Notification provider protocol."""

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class NotificationProvider(Protocol):
    @property
    def name(self) -> str: ...

    async def send(
        self, title: str, body: str, metadata: dict[str, Any] | None = None
    ) -> None: ...
