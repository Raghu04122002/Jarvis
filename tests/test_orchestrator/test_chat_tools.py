"""Tests for tool-enabled chat: honesty prompt, routing, tool loop, streaming."""

import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

import jarvis.services.ai_service as ai_module
from jarvis.api.dependencies import init_dependencies_with_db, reset_dependencies
from jarvis.config import AIConfig
from jarvis.db.engine import Database
from jarvis.db.tables import Base
from jarvis.events import EventBus
from jarvis.main import create_app
from jarvis.models.task import ChatRequest, ChatTurn
from jarvis.orchestrator.chat_prompt import build_system_prompt
from jarvis.orchestrator.orchestrator import Orchestrator
from jarvis.orchestrator.planner import BasicPlanner
from jarvis.services.ai_service import AIService, AIServiceError
from jarvis.services.chat_tools import SearchResult, Tool, Toolbox, WebSearchBackend
from jarvis.services.project_service import ProjectService
from jarvis.services.task_service import TaskService


class FakeStreamAI:
    """Scripted stand-in for AIService.stream_chat.

    Each script item is a str (streamed as a token), a ("call", name, args)
    tuple (runs the tool through the real toolbox), or an Exception (raised).
    """

    def __init__(self, *script: Any, available: bool = True) -> None:
        self.script = script
        self.available = available
        self.systems: list[str] = []
        self.messages: list[list[dict[str, str]]] = []

    async def stream_chat(
        self, system: str, messages: list[dict[str, str]], toolbox: Toolbox | None = None
    ) -> AsyncIterator[dict[str, Any]]:
        self.systems.append(system)
        self.messages.append(messages)
        assert toolbox is not None
        for i, item in enumerate(self.script):
            if isinstance(item, Exception):
                raise item
            if isinstance(item, tuple):
                _, name, args = item
                yield {
                    "type": "tool_start",
                    "id": f"c{i}",
                    "name": name,
                    "label": name,
                    "args": args,
                }
                ok, out = await toolbox.run(name, args)
                yield {"type": "tool_end", "id": f"c{i}", "name": name, "ok": ok, "output": out}
            else:
                yield {"type": "token", "text": item}


class FakeSearch(WebSearchBackend):
    async def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        return [
            SearchResult(
                "Big story about the real headline",
                "https://example.com/2026/10/27/big-story-real-headline",
                "Big story about the real headline.",
                datetime.now(UTC).isoformat(),
            )
        ]


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    db = Database(url="sqlite+aiosqlite://")
    async with db.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with db.session() as s:
        yield s
    await db.disconnect()


def _orch(ai: Any, search: WebSearchBackend | None = None) -> tuple[Orchestrator, TaskService]:
    bus = EventBus()
    task_svc = TaskService(bus)
    orch = Orchestrator(
        task_svc,
        BasicPlanner(),
        ProjectService(bus),
        event_bus=bus,
        ai_service=ai,
        search_backend=search,
    )
    return orch, task_svc


# --- system prompt ---------------------------------------------------------


def test_prompt_without_search_says_not_connected() -> None:
    p = build_system_prompt(Toolbox(), datetime(2026, 10, 27))
    assert "Web search is NOT connected" in p
    assert "Never make up news" in p
    assert "2026" in p


def test_prompt_lists_exact_tools() -> None:
    async def h(args: dict[str, Any]) -> str:
        return ""

    box = Toolbox([Tool("web_search", "Search the live web.", {}, h)])
    p = build_system_prompt(box, datetime(2026, 10, 27))
    assert "- web_search: Search the live web." in p
    assert "NOT connected" not in p


# --- toolbox ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_toolbox_unknown_and_failing_tools() -> None:
    async def boom(args: dict[str, Any]) -> str:
        raise RuntimeError("nope")

    box = Toolbox([Tool("x", "d", {}, boom)])
    ok, out = await box.run("missing", {})
    assert not ok and "Unknown tool" in out
    ok, out = await box.run("x", {})
    assert not ok and "nope" in out


# --- routing ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_small_talk_creates_no_task(session: AsyncSession) -> None:
    ai = FakeStreamAI("Hello. ", "How can I help?")
    orch, task_svc = _orch(ai)
    resp = await orch.handle_chat(session, ChatRequest(message="hi"))
    assert resp.status == "answered"
    assert resp.task_id is None
    assert resp.answer == "Hello. How can I help?"
    assert await task_svc.list_tasks(session) == []


@pytest.mark.asyncio
async def test_model_creates_task_and_link_is_appended(session: AsyncSession) -> None:
    ai = FakeStreamAI(
        ("call", "create_task", {"title": "Add dark mode", "request": "Add a dark mode toggle"}),
        "Started that.",
    )
    orch, task_svc = _orch(ai)
    resp = await orch.handle_chat(
        session, ChatRequest(message="add a dark mode toggle", conversation_id="conv-1")
    )
    assert resp.task_id is not None
    assert resp.status == "planning"
    assert resp.answer is not None
    assert resp.answer.endswith(
        f"Created task: Add dark mode → [{resp.task_id}](/tasks/{resp.task_id})"
    )
    task = await task_svc.get_task(session, resp.task_id)
    assert task.request == "Add a dark mode toggle"
    assert task.metadata["conversation_id"] == "conv-1"
    assert [c["name"] for c in resp.tool_calls] == ["create_task"]


@pytest.mark.asyncio
async def test_create_task_only_once_per_message(session: AsyncSession) -> None:
    ai = FakeStreamAI(
        ("call", "create_task", {"title": "A", "request": "do a"}),
        ("call", "create_task", {"title": "B", "request": "do b"}),
        "ok",
    )
    orch, task_svc = _orch(ai)
    await orch.handle_chat(session, ChatRequest(message="do things"))
    assert len(await task_svc.list_tasks(session)) == 1


@pytest.mark.asyncio
async def test_ai_error_on_question_reports_error_without_task(session: AsyncSession) -> None:
    ai = FakeStreamAI(AIServiceError("Ollama Cloud usage limit reached for now."))
    orch, task_svc = _orch(ai)
    resp = await orch.handle_chat(session, ChatRequest(message="what is a monad"))
    assert resp.status == "error"
    assert "usage limit" in (resp.answer or "")
    assert await task_svc.list_tasks(session) == []


@pytest.mark.asyncio
async def test_ai_error_on_action_still_creates_task(session: AsyncSession) -> None:
    ai = FakeStreamAI(AIServiceError("down"))
    orch, _ = _orch(ai)
    resp = await orch.handle_chat(session, ChatRequest(message="fix the login bug"))
    assert resp.task_id is not None


@pytest.mark.asyncio
async def test_action_hint_and_history_passed(session: AsyncSession) -> None:
    ai = FakeStreamAI("ok")
    orch, _ = _orch(ai)
    await orch.handle_chat(
        session,
        ChatRequest(
            message="fix the login bug",
            history=[
                ChatTurn(role="user", content="earlier"),
                ChatTurn(role="assistant", content="reply"),
            ],
        ),
    )
    assert "Router hint" in ai.systems[0]
    assert [m["content"] for m in ai.messages[0]] == ["earlier", "reply", "fix the login bug"]


@pytest.mark.asyncio
async def test_web_search_tool_offered_when_backend_set(session: AsyncSession) -> None:
    ai = FakeStreamAI(
        ("call", "web_search", {"query": "news"}),
        "See [Real headline](https://example.com/2026/10/27/big-story-real-headline)",
    )
    orch, _ = _orch(ai, FakeSearch())
    resp = await orch.handle_chat(session, ChatRequest(message="today's top news"))
    assert "- web_search:" in ai.systems[0]
    call = resp.tool_calls[0]
    assert call["name"] == "web_search" and call["status"] == "done"
    assert "https://example.com/2026/10/27/big-story-real-headline" in call["output"]


@pytest.mark.asyncio
async def test_no_web_search_without_backend(session: AsyncSession) -> None:
    ai = FakeStreamAI(("call", "web_search", {"query": "news"}), "I can't fetch live news.")
    orch, _ = _orch(ai)
    resp = await orch.handle_chat(session, ChatRequest(message="today's top news"))
    assert "Web search is NOT connected" in ai.systems[0]
    assert resp.tool_calls[0]["status"] == "error"


# --- AIService Ollama tool loop ---------------------------------------------


def _ndjson(*chunks: dict[str, Any]) -> bytes:
    return b"".join(json.dumps(c).encode() + b"\n" for c in chunks)


@pytest.mark.asyncio
async def test_ollama_stream_runs_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    bodies: list[dict[str, Any]] = []
    replies = [
        _ndjson(
            {
                "message": {
                    "content": "",
                    "tool_calls": [{"function": {"name": "echo", "arguments": {"x": "hi"}}}],
                },
                "done": True,
            }
        ),
        _ndjson(
            {"message": {"content": "Echo "}}, {"message": {"content": "said hi"}, "done": True}
        ),
    ]

    def handler(req: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(req.content))
        return httpx.Response(200, content=replies[len(bodies) - 1])

    real = httpx.AsyncClient

    def factory(*a: Any, **kw: Any) -> httpx.AsyncClient:
        kw["transport"] = httpx.MockTransport(handler)
        return real(*a, **kw)

    monkeypatch.setattr(ai_module.httpx, "AsyncClient", factory)

    async def echo(args: dict[str, Any]) -> str:
        return f"echo:{args['x']}"

    svc = AIService(AIConfig(provider="ollama", ollama_api_key="k", pxpipe_enabled=False))
    events = [
        e
        async for e in svc.stream_chat(
            "sys", [{"role": "user", "content": "q"}], Toolbox([Tool("echo", "d", {}, echo)])
        )
    ]
    types = [e["type"] for e in events]
    assert types == ["tool_start", "tool_end", "token", "token"]
    assert events[1]["output"] == "echo:hi"
    assert bodies[0]["stream"] is True and bodies[0]["tools"][0]["function"]["name"] == "echo"
    assert bodies[1]["messages"][-1] == {"role": "tool", "tool_name": "echo", "content": "echo:hi"}


@pytest.mark.asyncio
async def test_ollama_stream_429(monkeypatch: pytest.MonkeyPatch) -> None:
    real = httpx.AsyncClient

    def factory(*a: Any, **kw: Any) -> httpx.AsyncClient:
        kw["transport"] = httpx.MockTransport(lambda r: httpx.Response(429, json={"error": "x"}))
        return real(*a, **kw)

    monkeypatch.setattr(ai_module.httpx, "AsyncClient", factory)
    svc = AIService(AIConfig(provider="ollama", ollama_api_key="k", pxpipe_enabled=False))
    with pytest.raises(AIServiceError, match="usage limit"):
        async for _ in svc.stream_chat("s", [{"role": "user", "content": "q"}]):
            pass


# --- SSE endpoint -----------------------------------------------------------


@pytest.mark.asyncio
async def test_chat_stream_endpoint() -> None:
    db = Database(url="sqlite+aiosqlite://")
    async with db.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    reset_dependencies()
    init_dependencies_with_db(db)
    app = create_app()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
            resp = await ac.post("/chat/stream", json={"message": "hello"})
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        events = [
            json.loads(line[6:]) for line in resp.text.splitlines() if line.startswith("data: ")
        ]
        assert events[-1]["type"] == "done"
        assert events[-1]["response"]["status"] == "answered"
        assert any(e["type"] == "token" for e in events)
    finally:
        reset_dependencies()
        await db.disconnect()


@pytest.mark.asyncio
async def test_invented_links_are_removed_after_search(session: AsyncSession) -> None:
    ai = FakeStreamAI(
        ("call", "web_search", {"query": "news"}),
        "- [Real](https://example.com/2026/10/27/big-story-real-headline)\n- [Fake](https://made.up/x)",
    )
    orch, _ = _orch(ai, FakeSearch())
    resp = await orch.handle_chat(session, ChatRequest(message="today's top news"))
    answer = resp.answer or ""
    assert answer.startswith(
        "- Real — [Example](https://example.com/2026/10/27/big-story-real-headline)"
    )
    assert "made.up" not in answer and "Fake" not in answer
    assert "1 line removed" in answer


@pytest.mark.asyncio
async def test_gpt_oss_citation_markers_become_links(session: AsyncSession) -> None:
    ai = FakeStreamAI(
        ("call", "web_search", {"query": "news"}),
        "1. Big story【0†AP】\n2. Other【7†Nowhere】",
    )
    orch, _ = _orch(ai, FakeSearch())
    resp = await orch.handle_chat(session, ChatRequest(message="today's top news"))
    answer = resp.answer or ""
    assert answer.startswith(
        "1. Big story — [Example](https://example.com/2026/10/27/big-story-real-headline)\n"
    )
    assert "Nowhere" not in answer  # marker for a result that doesn't exist is dropped
    assert "*Covers " in answer


# --- freshness ----------------------------------------------------------------


class DatedSearch(WebSearchBackend):
    def __init__(self, *items: tuple[str, str]) -> None:
        self.items = items

    async def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        # A realistic headline from the URL slug ("Parliament passes new budget bill").
        return [
            SearchResult(
                url.rstrip("/").rsplit("/", 1)[-1].replace("-", " ").capitalize(), url, "text", pub
            )
            for url, pub in self.items
        ]


@pytest.mark.asyncio
async def test_fresh_only_drops_old_but_keeps_undated_results() -> None:
    from datetime import date

    from jarvis.services.chat_tools import web_search_tool

    backend = DatedSearch(
        ("https://a.com/2026/10/27/parliament-passes-new-budget-bill", "2026-10-27T08:00:00Z"),
        ("https://b.com/world/storm-hits-the-northern-coast", "2026-10-26"),  # < 48h
        ("https://c.com/news/old-story-from-last-week", "2026-10-20"),  # a week old
        ("https://d.com/news/council-approves-city-transit-plan", ""),  # no date anywhere
        ("https://e.com/", "2026-10-27"),  # a homepage, not an article
    )
    tool = web_search_tool(backend, fresh_only=True, today=date(2026, 10, 27))
    data = json.loads(await tool.handler({"query": "news"}))
    urls = [r["url"] for r in data["results"]]
    assert "https://c.com/news/old-story-from-last-week" not in urls
    assert "https://e.com/" not in urls
    assert set(urls) == {
        "https://a.com/2026/10/27/parliament-passes-new-budget-bill",
        "https://b.com/world/storm-hits-the-northern-coast",
        "https://d.com/news/council-approves-city-transit-plan",
    }
    undated = [r for r in data["results"] if r["url"].startswith("https://d.com")]
    assert undated[0]["date"] is None
    # Fewer than 5 survived, so the note says how many and why.
    assert "Only 3" in data["note"] and "older than 48 hours" in data["note"]

    stale = web_search_tool(
        DatedSearch(("https://c.com/news/old-story-from-last-week", "2026-10-20")),
        fresh_only=True,
        today=date(2026, 10, 27),
    )
    out = await stale.handler({"query": "news"})
    assert "No recent article headlines" in out


@pytest.mark.asyncio
async def test_not_time_sensitive_keeps_undated_results() -> None:
    from datetime import date

    from jarvis.services.chat_tools import web_search_tool

    tool = web_search_tool(DatedSearch(("https://d.com/w", "")), today=date(2026, 10, 27))
    data = json.loads(await tool.handler({"query": "python 3.13 release notes"}))
    assert data["results"][0]["url"] == "https://d.com/w"
    assert data["results"][0]["date"] is None


def test_search_output_always_valid_json() -> None:
    from jarvis.services.chat_tools import _MAX_TOOL_OUTPUT, _results_json
    from jarvis.services.search_grounding import GroundedResult

    big = [
        GroundedResult(f"Title {i}", f"https://x.com/{i}", "word " * 400, "X", "2026-10-27")
        for i in range(10)
    ]
    out = _results_json(big)
    assert len(out) < _MAX_TOOL_OUTPUT
    data = json.loads(out)
    assert len(data["results"]) >= 5 and data["results"][0]["url"] == "https://x.com/0"


@pytest.mark.asyncio
async def test_half_bracket_links_are_grounded(session: AsyncSession) -> None:
    ai = FakeStreamAI(
        ("call", "web_search", {"query": "news"}),
        "- Big story about the real headline【Example](https://example.com/2026/10/27/big-story-real-headline)\n"
        "These are the most prominent stories across selected outlets.",
    )
    orch, _ = _orch(ai, FakeSearch())
    resp = await orch.handle_chat(session, ChatRequest(message="today's top news"))
    answer = resp.answer or ""
    assert answer.startswith(
        "- Big story about the real headline — [Example](https://example.com/2026/10/27/big-story-real-headline)"
    )
    assert "prominent" not in answer and "【" not in answer


@pytest.mark.asyncio
async def test_mostly_unsupported_news_falls_back_to_verbatim_headlines(
    session: AsyncSession,
) -> None:
    ai = FakeStreamAI(
        ("call", "web_search", {"query": "news"}),
        "- Aliens landed and markets crashed 【Example】\n- The war is over, experts say",
    )
    orch, _ = _orch(ai, FakeSearch())
    resp = await orch.handle_chat(session, ChatRequest(message="today's top news"))
    answer = resp.answer or ""
    assert answer.startswith("Jarvis's summary didn't match its sources")
    assert (
        "- Big story about the real headline — [Example](https://example.com/2026/10/27/big-story-real-headline)"
        in answer
    )
    assert "Aliens" not in answer and "war is over" not in answer
    assert "*Covers " in answer
