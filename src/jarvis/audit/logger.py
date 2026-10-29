"""Audit logger — records task lifecycle events.

Listens to the event bus and creates audit entries.
Never logs secrets or sensitive data.
"""

import logging
import uuid

from jarvis.events import Event, EventBus, EventType
from jarvis.models.audit import AuditEntry

logger = logging.getLogger(__name__)

_APPROVAL_EVENT_TYPES = frozenset(
    {
        EventType.APPROVAL_REQUESTED,
        EventType.APPROVAL_APPROVED,
        EventType.APPROVAL_DENIED,
        EventType.APPROVAL_EXPIRED,
    }
)


class AuditLogger:
    """Records audit entries for task lifecycle events."""

    def __init__(self, event_bus: EventBus) -> None:
        self._entries: list[AuditEntry] = []
        self._event_bus = event_bus
        self._subscribe()

    def _subscribe(self) -> None:
        for event_type in EventType:
            self._event_bus.subscribe(event_type, self._handle_event)

    def _handle_event(self, event: Event) -> None:
        approval_state: str | None = None
        if event.type in _APPROVAL_EVENT_TYPES:
            approval_state = event.type.value

        entry = AuditEntry(
            id=str(uuid.uuid4()),
            task_id=event.task_id,
            timestamp=event.timestamp,
            action=event.type.value,
            args_metadata={k: str(v) for k, v in event.data.items() if k != "task"},
            success=event.type not in (EventType.TASK_FAILED, EventType.TASK_CANCELLED),
            approval_state=approval_state,
        )
        self._entries.append(entry)
        logger.info(
            "AUDIT: %s task_id=%s",
            event.type.value,
            event.task_id,
        )

    def get_entries(self, task_id: str | None = None) -> list[AuditEntry]:
        if task_id is None:
            return list(self._entries)
        return [e for e in self._entries if e.task_id == task_id]

    def clear(self) -> None:
        self._entries.clear()
