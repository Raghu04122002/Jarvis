"""Tests for BrowserTool — uses a local FastAPI test server and real Playwright."""

import asyncio
import json
import socket
from pathlib import Path

import pytest
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse

from jarvis.config import BrowserConfig
from jarvis.models.approval import RiskLevel
from jarvis.tools.base import InvalidOperationError
from jarvis.tools.browser_tool import BrowserNotStartedError, BrowserTool

# ---------------------------------------------------------------------------
# Local test web app
# ---------------------------------------------------------------------------

_test_app = FastAPI()


@_test_app.get("/", response_class=HTMLResponse)
async def home() -> str:
    return """
    <html><head><title>Test Home</title></head><body>
        <h1>Welcome</h1>
        <a href="/page2" id="link-page2">Go to page 2</a>
        <form action="/submit" method="get">
            <input name="username" id="username" type="text" />
            <button type="submit" id="submit-btn">Submit</button>
        </form>
    </body></html>
    """


@_test_app.get("/page2", response_class=HTMLResponse)
async def page2() -> str:
    return """
    <html><head><title>Page Two</title></head><body>
        <h1>Page 2</h1>
        <a href="/" id="link-home">Back home</a>
    </body></html>
    """


@_test_app.get("/slow", response_class=HTMLResponse)
async def slow() -> str:
    await asyncio.sleep(5)
    return "<html><head><title>Slow</title></head><body><p>Finally!</p></body></html>"


@_test_app.get("/submit", response_class=HTMLResponse)
async def submit(request: Request) -> str:
    username = request.query_params.get("username", "")
    return f"""
    <html><head><title>Submitted</title></head><body>
        <p id="result">Hello, {username}</p>
    </body></html>
    """


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def server_url() -> str:
    """Start a local test server on a random port for the module."""
    port = _free_port()
    config = uvicorn.Config(_test_app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)

    loop = asyncio.new_event_loop()
    thread_import = __import__("threading")
    thread = thread_import.Thread(target=loop.run_until_complete, args=(server.serve(),))
    thread.daemon = True
    thread.start()

    # Wait for the server to start
    import time

    for _ in range(50):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                break
        except OSError:
            time.sleep(0.1)

    yield f"http://127.0.0.1:{port}"

    server.should_exit = True
    thread.join(timeout=5)


@pytest.fixture
async def tool() -> BrowserTool:
    """Create a BrowserTool with default config (headless)."""
    t = BrowserTool(BrowserConfig(headless=True))
    yield t  # type: ignore[misc]
    # Ensure session is cleaned up
    await t._session.close()


# ---------------------------------------------------------------------------
# Meta tests
# ---------------------------------------------------------------------------


class TestBrowserToolMeta:
    def test_name(self) -> None:
        t = BrowserTool()
        assert t.name == "browser"

    def test_operations_keys(self) -> None:
        t = BrowserTool()
        ops = t.operations()
        expected = {
            "navigate", "click", "fill", "press",
            "screenshot", "get_page_info", "inspect", "wait", "close",
        }
        assert set(ops.keys()) == expected

    def test_safe_operations(self) -> None:
        t = BrowserTool()
        ops = t.operations()
        for op in ("screenshot", "get_page_info", "inspect", "wait", "close"):
            assert ops[op] == RiskLevel.SAFE

    def test_approval_operations(self) -> None:
        t = BrowserTool()
        ops = t.operations()
        for op in ("navigate", "click", "fill", "press"):
            assert ops[op] == RiskLevel.REQUIRES_APPROVAL

    @pytest.mark.asyncio
    async def test_invalid_operation(self, tool: BrowserTool) -> None:
        with pytest.raises(InvalidOperationError):
            await tool.execute("hack_the_planet", ".")


# ---------------------------------------------------------------------------
# URL Security tests
# ---------------------------------------------------------------------------


class TestBrowserToolURLSecurity:
    def test_blocked_domain_bank(self) -> None:
        t = BrowserTool()
        err = t._check_url_allowed("https://www.bank.com/login")
        assert err is not None
        assert "blocked" in err.lower()

    def test_blocked_domain_paypal(self) -> None:
        t = BrowserTool()
        err = t._check_url_allowed("https://www.paypal.com/checkout")
        assert err is not None

    def test_blocked_domain_venmo(self) -> None:
        t = BrowserTool()
        err = t._check_url_allowed("https://venmo.com/pay")
        assert err is not None

    def test_allowed_url_passes(self) -> None:
        t = BrowserTool()
        err = t._check_url_allowed("http://localhost:8000")
        assert err is None

    def test_allowed_domains_allowlist(self) -> None:
        config = BrowserConfig(allowed_domains=["localhost", "*.example.com"])
        t = BrowserTool(config)
        assert t._check_url_allowed("http://localhost:3000") is None
        assert t._check_url_allowed("http://app.example.com") is None

    def test_allowed_domains_rejects_unlisted(self) -> None:
        config = BrowserConfig(allowed_domains=["localhost"])
        t = BrowserTool(config)
        err = t._check_url_allowed("http://evil.com")
        assert err is not None
        assert "not in the allowed domains" in err

    def test_empty_allowlist_allows_all(self) -> None:
        config = BrowserConfig(allowed_domains=[], blocked_domains=[])
        t = BrowserTool(config)
        assert t._check_url_allowed("http://anything.com") is None

    def test_wildcard_blocked(self) -> None:
        config = BrowserConfig(blocked_domains=["*.bank.*"])
        t = BrowserTool(config)
        assert t._check_url_allowed("https://my.bank.co.uk") is not None
        assert t._check_url_allowed("https://mysite.com") is None

    @pytest.mark.asyncio
    async def test_navigate_blocked_url(self, tool: BrowserTool) -> None:
        result = await tool.execute("navigate", ".", url="https://www.paypal.com")
        assert result.success is False
        assert "blocked" in (result.error or "").lower()


# ---------------------------------------------------------------------------
# Navigation tests
# ---------------------------------------------------------------------------


class TestBrowserToolNavigation:
    @pytest.mark.asyncio
    async def test_navigate_success(
        self, tool: BrowserTool, server_url: str
    ) -> None:
        result = await tool.execute("navigate", ".", url=server_url)
        assert result.success is True
        assert "Test Home" in result.output

    @pytest.mark.asyncio
    async def test_navigate_lazy_starts_session(
        self, tool: BrowserTool, server_url: str
    ) -> None:
        assert not tool._session.is_running
        await tool.execute("navigate", ".", url=server_url)
        assert tool._session.is_running

    @pytest.mark.asyncio
    async def test_get_page_info(
        self, tool: BrowserTool, server_url: str
    ) -> None:
        await tool.execute("navigate", ".", url=server_url)
        result = await tool.execute("get_page_info", ".")
        assert result.success is True
        info = json.loads(result.output)
        assert info["title"] == "Test Home"
        assert server_url in info["url"]

    @pytest.mark.asyncio
    async def test_navigate_missing_url(self, tool: BrowserTool) -> None:
        result = await tool.execute("navigate", ".")
        assert result.success is False
        assert result.error == "url is required"

    @pytest.mark.asyncio
    async def test_get_page_info_without_session(self, tool: BrowserTool) -> None:
        result = await tool.execute("get_page_info", ".")
        assert result.success is False
        assert "not started" in (result.error or "").lower()


# ---------------------------------------------------------------------------
# Interaction tests
# ---------------------------------------------------------------------------


class TestBrowserToolInteraction:
    @pytest.mark.asyncio
    async def test_click_link(
        self, tool: BrowserTool, server_url: str
    ) -> None:
        await tool.execute("navigate", ".", url=server_url)
        result = await tool.execute("click", ".", selector="#link-page2")
        assert result.success is True
        assert "Page Two" in result.output

    @pytest.mark.asyncio
    async def test_fill_input(
        self, tool: BrowserTool, server_url: str
    ) -> None:
        await tool.execute("navigate", ".", url=server_url)
        result = await tool.execute(
            "fill", ".", selector="#username", value="testuser"
        )
        assert result.success is True
        assert "Filled" in result.output

    @pytest.mark.asyncio
    async def test_press_key(
        self, tool: BrowserTool, server_url: str
    ) -> None:
        await tool.execute("navigate", ".", url=server_url)
        result = await tool.execute("press", ".", key="Tab")
        assert result.success is True
        assert "Tab" in result.output

    @pytest.mark.asyncio
    async def test_click_nonexistent_selector(
        self, tool: BrowserTool, server_url: str
    ) -> None:
        await tool.execute("navigate", ".", url=server_url)
        result = await tool.execute("click", ".", selector="#does-not-exist")
        assert result.success is False
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_fill_missing_selector(self, tool: BrowserTool) -> None:
        result = await tool.execute("fill", ".", value="x")
        assert result.success is False
        assert result.error == "selector is required"

    @pytest.mark.asyncio
    async def test_press_missing_key(self, tool: BrowserTool) -> None:
        result = await tool.execute("press", ".")
        assert result.success is False
        assert result.error == "key is required"


# ---------------------------------------------------------------------------
# Screenshot tests
# ---------------------------------------------------------------------------


class TestBrowserToolScreenshot:
    @pytest.mark.asyncio
    async def test_screenshot_creates_file(
        self, tool: BrowserTool, server_url: str, tmp_path: Path
    ) -> None:
        await tool.execute("navigate", ".", url=server_url)
        path = str(tmp_path / "shot.png")
        result = await tool.execute("screenshot", ".", path=path)
        assert result.success is True
        assert Path(path).exists()
        assert Path(path).stat().st_size > 0

    @pytest.mark.asyncio
    async def test_screenshot_full_page(
        self, tool: BrowserTool, server_url: str, tmp_path: Path
    ) -> None:
        await tool.execute("navigate", ".", url=server_url)
        path = str(tmp_path / "full.png")
        result = await tool.execute(
            "screenshot", ".", path=path, full_page="true"
        )
        assert result.success is True
        assert Path(path).exists()

    @pytest.mark.asyncio
    async def test_screenshot_without_session(self, tool: BrowserTool) -> None:
        result = await tool.execute("screenshot", ".")
        assert result.success is False
        assert "not started" in (result.error or "").lower()


# ---------------------------------------------------------------------------
# Wait tests
# ---------------------------------------------------------------------------


class TestBrowserToolWait:
    @pytest.mark.asyncio
    async def test_wait_for_selector(
        self, tool: BrowserTool, server_url: str
    ) -> None:
        await tool.execute("navigate", ".", url=server_url)
        result = await tool.execute("wait", ".", selector="h1")
        assert result.success is True
        assert "visible" in result.output

    @pytest.mark.asyncio
    async def test_wait_timeout_on_missing(
        self, tool: BrowserTool, server_url: str
    ) -> None:
        await tool.execute("navigate", ".", url=server_url)
        result = await tool.execute(
            "wait", ".", selector="#nonexistent", timeout_ms=500
        )
        assert result.success is False
        assert "timeout" in (result.error or "").lower()

    @pytest.mark.asyncio
    async def test_wait_for_load_state(
        self, tool: BrowserTool, server_url: str
    ) -> None:
        await tool.execute("navigate", ".", url=server_url)
        result = await tool.execute("wait", ".", state="domcontentloaded")
        assert result.success is True


# ---------------------------------------------------------------------------
# Inspect tests
# ---------------------------------------------------------------------------


class TestBrowserToolInspect:
    @pytest.mark.asyncio
    async def test_inspect_finds_elements(
        self, tool: BrowserTool, server_url: str
    ) -> None:
        await tool.execute("navigate", ".", url=server_url)
        result = await tool.execute("inspect", ".", selector="a")
        assert result.success is True
        elements = json.loads(result.output)
        assert len(elements) >= 1
        assert elements[0]["tag"] == "a"

    @pytest.mark.asyncio
    async def test_inspect_returns_attributes(
        self, tool: BrowserTool, server_url: str
    ) -> None:
        await tool.execute("navigate", ".", url=server_url)
        result = await tool.execute("inspect", ".", selector="#link-page2")
        assert result.success is True
        elements = json.loads(result.output)
        assert len(elements) == 1
        assert "href" in elements[0]["attributes"]
        assert elements[0]["attributes"]["id"] == "link-page2"

    @pytest.mark.asyncio
    async def test_inspect_no_matches(
        self, tool: BrowserTool, server_url: str
    ) -> None:
        await tool.execute("navigate", ".", url=server_url)
        result = await tool.execute("inspect", ".", selector=".nonexistent-class")
        assert result.success is True
        elements = json.loads(result.output)
        assert elements == []

    @pytest.mark.asyncio
    async def test_inspect_missing_selector(self, tool: BrowserTool) -> None:
        result = await tool.execute("inspect", ".")
        assert result.success is False
        assert result.error == "selector is required"


# ---------------------------------------------------------------------------
# Session lifecycle tests
# ---------------------------------------------------------------------------


class TestBrowserToolSession:
    @pytest.mark.asyncio
    async def test_close_session(
        self, tool: BrowserTool, server_url: str
    ) -> None:
        await tool.execute("navigate", ".", url=server_url)
        assert tool._session.is_running
        result = await tool.execute("close", ".")
        assert result.success is True
        assert not tool._session.is_running

    @pytest.mark.asyncio
    async def test_operation_after_close(
        self, tool: BrowserTool, server_url: str
    ) -> None:
        await tool.execute("navigate", ".", url=server_url)
        await tool.execute("close", ".")
        result = await tool.execute("get_page_info", ".")
        assert result.success is False
        assert "not started" in (result.error or "").lower()

    @pytest.mark.asyncio
    async def test_double_close_safe(
        self, tool: BrowserTool, server_url: str
    ) -> None:
        await tool.execute("navigate", ".", url=server_url)
        await tool.execute("close", ".")
        result = await tool.execute("close", ".")
        assert result.success is True

    @pytest.mark.asyncio
    async def test_session_not_started_error(self) -> None:
        from jarvis.tools.browser_tool import BrowserSession

        session = BrowserSession(BrowserConfig())
        with pytest.raises(BrowserNotStartedError):
            _ = session.page
