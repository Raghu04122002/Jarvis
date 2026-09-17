"""Browser automation tool — Playwright-based web interaction."""

import json
import logging
from collections.abc import Callable, Coroutine
from fnmatch import fnmatch
from typing import Any
from urllib.parse import urlparse

from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    async_playwright,
)
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from jarvis.config import BrowserConfig
from jarvis.models.approval import RiskLevel
from jarvis.tools.base import BaseTool, InvalidOperationError, ToolError, ToolResult

logger = logging.getLogger(__name__)


class BrowserNotStartedError(ToolError):
    """Raised when an operation requires a running browser session."""

    def __init__(self) -> None:
        super().__init__("Browser session is not started. Navigate to a URL first.")


class BrowserSession:
    """Manages Playwright browser lifecycle (browser, context, page)."""

    def __init__(self, config: BrowserConfig) -> None:
        self._config = config
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    @property
    def is_running(self) -> bool:
        return self._browser is not None and self._browser.is_connected()

    @property
    def page(self) -> Page:
        if self._page is None:
            raise BrowserNotStartedError()
        return self._page

    async def start(self) -> None:
        if self.is_running:
            return
        pw = await async_playwright().start()
        self._playwright = pw
        self._browser = await pw.chromium.launch(headless=self._config.headless)
        self._context = await self._browser.new_context(
            viewport={
                "width": self._config.viewport_width,
                "height": self._config.viewport_height,
            },
        )
        self._context.set_default_timeout(self._config.default_timeout_ms)
        self._page = await self._context.new_page()

    async def close(self) -> None:
        if self._context is not None:
            await self._context.close()
            self._context = None
        if self._browser is not None:
            await self._browser.close()
            self._browser = None
        if self._playwright is not None:
            await self._playwright.stop()
            self._playwright = None
        self._page = None


class BrowserTool(BaseTool):
    """Browser automation tool using Playwright."""

    def __init__(self, config: BrowserConfig | None = None) -> None:
        self._config = config or BrowserConfig()
        self._session = BrowserSession(self._config)

    @property
    def name(self) -> str:
        return "browser"

    def operations(self) -> dict[str, RiskLevel]:
        return {
            "navigate": RiskLevel.REQUIRES_APPROVAL,
            "click": RiskLevel.REQUIRES_APPROVAL,
            "fill": RiskLevel.REQUIRES_APPROVAL,
            "press": RiskLevel.REQUIRES_APPROVAL,
            "screenshot": RiskLevel.SAFE,
            "get_page_info": RiskLevel.SAFE,
            "inspect": RiskLevel.SAFE,
            "wait": RiskLevel.SAFE,
            "close": RiskLevel.SAFE,
        }

    async def execute(
        self, operation: str, working_dir: str, **kwargs: str | int | list[str]
    ) -> ToolResult:
        if operation not in self.operations():
            raise InvalidOperationError(self.name, operation)

        _handler_type = Callable[..., Coroutine[Any, Any, ToolResult]]
        dispatch: dict[str, _handler_type] = {
            "navigate": self._navigate,
            "click": self._click,
            "fill": self._fill,
            "press": self._press,
            "screenshot": self._screenshot,
            "get_page_info": self._get_page_info,
            "inspect": self._inspect,
            "wait": self._wait,
            "close": self._close,
        }
        try:
            handler = dispatch[operation]
            return await handler(working_dir, **kwargs)
        except BrowserNotStartedError as exc:
            return ToolResult(success=False, output="", error=str(exc), exit_code=1)
        except PlaywrightTimeoutError as exc:
            return ToolResult(
                success=False, output="", error=f"Timeout: {exc}", exit_code=1
            )
        except PlaywrightError as exc:
            return ToolResult(
                success=False, output="", error=f"Browser error: {exc}", exit_code=1
            )

    def _check_url_allowed(self, url: str) -> str | None:
        """Return an error message if the URL is blocked, else None."""
        parsed = urlparse(url)
        domain = parsed.hostname or ""

        for pattern in self._config.blocked_domains:
            if fnmatch(domain, pattern):
                return f"URL blocked: domain '{domain}' matches blocked pattern '{pattern}'"

        if self._config.allowed_domains:
            for pattern in self._config.allowed_domains:
                if fnmatch(domain, pattern):
                    return None
            return (
                f"URL blocked: domain '{domain}' is not in the allowed domains list"
            )

        return None

    async def _navigate(
        self, working_dir: str, **kwargs: str | int | list[str]
    ) -> ToolResult:
        url = kwargs.get("url")
        if not isinstance(url, str) or not url:
            return ToolResult(
                success=False, output="", error="url is required", exit_code=1
            )

        error = self._check_url_allowed(url)
        if error:
            return ToolResult(success=False, output="", error=error, exit_code=1)

        if not self._session.is_running:
            await self._session.start()

        await self._session.page.goto(url)
        title = await self._session.page.title()
        return ToolResult(
            success=True,
            output=f"Navigated to {self._session.page.url} — title: {title}",
        )

    async def _click(
        self, working_dir: str, **kwargs: str | int | list[str]
    ) -> ToolResult:
        selector = kwargs.get("selector")
        if not isinstance(selector, str) or not selector:
            return ToolResult(
                success=False, output="", error="selector is required", exit_code=1
            )

        await self._session.page.click(selector)

        # Defense-in-depth: check URL after click (may have navigated)
        current_url = self._session.page.url
        error = self._check_url_allowed(current_url)
        if error:
            await self._session.page.go_back()
            return ToolResult(success=False, output="", error=error, exit_code=1)

        title = await self._session.page.title()
        return ToolResult(
            success=True,
            output=f"Clicked '{selector}' — now at {current_url} — title: {title}",
        )

    async def _fill(
        self, working_dir: str, **kwargs: str | int | list[str]
    ) -> ToolResult:
        selector = kwargs.get("selector")
        if not isinstance(selector, str) or not selector:
            return ToolResult(
                success=False, output="", error="selector is required", exit_code=1
            )
        value = kwargs.get("value")
        if not isinstance(value, str):
            return ToolResult(
                success=False, output="", error="value is required", exit_code=1
            )

        await self._session.page.fill(selector, value)
        return ToolResult(
            success=True, output=f"Filled '{selector}' with value"
        )

    async def _press(
        self, working_dir: str, **kwargs: str | int | list[str]
    ) -> ToolResult:
        key = kwargs.get("key")
        if not isinstance(key, str) or not key:
            return ToolResult(
                success=False, output="", error="key is required", exit_code=1
            )

        await self._session.page.keyboard.press(key)
        return ToolResult(success=True, output=f"Pressed key '{key}'")

    async def _screenshot(
        self, working_dir: str, **kwargs: str | int | list[str]
    ) -> ToolResult:
        path = kwargs.get("path")
        if not isinstance(path, str) or not path:
            path = "screenshot.png"

        full_page = kwargs.get("full_page")
        is_full_page = str(full_page).lower() in ("true", "1", "yes") if full_page else False

        await self._session.page.screenshot(path=path, full_page=is_full_page)
        return ToolResult(success=True, output=f"Screenshot saved to {path}")

    async def _get_page_info(
        self, working_dir: str, **kwargs: str | int | list[str]
    ) -> ToolResult:
        page = self._session.page
        title = await page.title()
        info = {"url": page.url, "title": title}
        return ToolResult(success=True, output=json.dumps(info))

    async def _inspect(
        self, working_dir: str, **kwargs: str | int | list[str]
    ) -> ToolResult:
        selector = kwargs.get("selector")
        if not isinstance(selector, str) or not selector:
            return ToolResult(
                success=False, output="", error="selector is required", exit_code=1
            )

        elements = await self._session.page.query_selector_all(selector)
        results: list[dict[str, object]] = []
        for el in elements[:20]:
            tag = await el.evaluate("e => e.tagName.toLowerCase()")
            text = (await el.inner_text()).strip()[:200]
            attrs: dict[str, str] = await el.evaluate(
                "e => Object.fromEntries([...e.attributes].map(a => [a.name, a.value]))"
            )
            results.append({"tag": tag, "text": text, "attributes": attrs})

        return ToolResult(
            success=True,
            output=json.dumps(results, indent=2),
        )

    async def _wait(
        self, working_dir: str, **kwargs: str | int | list[str]
    ) -> ToolResult:
        selector = kwargs.get("selector")
        timeout_ms = kwargs.get("timeout_ms")
        state = kwargs.get("state")

        timeout = int(str(timeout_ms)) if timeout_ms else self._config.default_timeout_ms

        if isinstance(selector, str) and selector:
            wait_state = str(state) if state else "visible"
            await self._session.page.wait_for_selector(
                selector, timeout=timeout, state=wait_state  # type: ignore[arg-type]
            )
            return ToolResult(
                success=True, output=f"Element '{selector}' is {wait_state}"
            )

        load_state = str(state) if state else "load"
        await self._session.page.wait_for_load_state(
            load_state, timeout=timeout  # type: ignore[arg-type]
        )
        return ToolResult(success=True, output=f"Page reached '{load_state}' state")

    async def _close(
        self, working_dir: str, **kwargs: str | int | list[str]
    ) -> ToolResult:
        await self._session.close()
        return ToolResult(success=True, output="Browser session closed")
