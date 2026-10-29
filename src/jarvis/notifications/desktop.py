"""Desktop notification provider using plyer (optional dependency)."""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class DesktopNotificationProvider:
    """Cross-platform desktop notifications via plyer.

    Gracefully degrades if plyer is not installed.
    """

    @property
    def name(self) -> str:
        return "desktop"

    async def send(self, title: str, body: str, metadata: dict[str, Any] | None = None) -> None:
        try:
            from plyer import notification

            notification.notify(
                title=title,
                message=body,
                app_name="Jarvis",
                timeout=10,
            )
        except ImportError:
            logger.debug("plyer not installed — skipping desktop notification")
        except Exception:
            logger.exception("Desktop notification failed")
            raise
