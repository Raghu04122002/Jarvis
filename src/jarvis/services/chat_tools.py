"""Tools the chat model can call, plus the web-search backends behind them.

A :class:`Toolbox` is the exact set of tools offered to the model in one turn.
Its :meth:`Toolbox.describe` output is put into the system prompt so the model
knows precisely what it can and cannot do, and never pretends to have a tool.
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import httpx

from jarvis.services.news_search import Page, collect_news, fetch_html
from jarvis.services.search_grounding import (
    GroundedResult,
    extract_date,
    source_name,
)

logger = logging.getLogger(__name__)

ToolHandler = Callable[[dict[str, Any]], Awaitable[str]]

_MAX_TOOL_OUTPUT = 6000
_SEARCH_TIMEOUT = 20.0


@dataclass(frozen=True)
class Tool:
    """One callable tool: its JSON schema plus the coroutine that runs it."""

    name: str
    description: str
    parameters: dict[str, Any]
    handler: ToolHandler
    # Short human label shown in the UI while the tool runs ("Searching web").
    label: str = ""


@dataclass
class Toolbox:
    """The tools available for a single chat turn."""

    tools: list[Tool] = field(default_factory=list)

    def add(self, tool: Tool) -> None:
        self.tools.append(tool)

    def get(self, name: str) -> Tool | None:
        return next((t for t in self.tools if t.name == name), None)

    @property
    def names(self) -> list[str]:
        return [t.name for t in self.tools]

    def describe(self) -> str:
        """Bullet list of tools for the system prompt."""
        if not self.tools:
            return "- (none)"
        return "\n".join(f"- {t.name}: {t.description}" for t in self.tools)

    def ollama_schemas(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                },
            }
            for t in self.tools
        ]

    def anthropic_schemas(self) -> list[dict[str, Any]]:
        return [
            {"name": t.name, "description": t.description, "input_schema": t.parameters}
            for t in self.tools
        ]

    async def run(self, name: str, args: dict[str, Any]) -> tuple[bool, str]:
        """Run a tool. Returns (ok, output); never raises."""
        tool = self.get(name)
        if tool is None:
            return False, f"Unknown tool '{name}'. Available: {', '.join(self.names) or 'none'}."
        try:
            out = await tool.handler(args)
        except Exception as e:  # tool failures are reported to the model, not raised
            logger.warning("Tool %s failed: %s", name, e)
            return False, f"Tool '{name}' failed: {e}"
        if len(out) > _MAX_TOOL_OUTPUT:
            out = out[:_MAX_TOOL_OUTPUT] + "\n…[truncated]"
        return True, out


# ---------------------------------------------------------------------------
# Web search
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    snippet: str
    published: str = ""  # backend-supplied publication timestamp, if any
    content: str = ""  # full page text when the backend returns it (hub mining)


class WebSearchBackend:
    """Base class: ``search`` returns real results with real URLs."""

    name = "base"

    async def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        raise NotImplementedError

    async def fetch_page(self, url: str) -> Page | None:
        """Fetch one page for dating / headline checks. None if unavailable."""
        return None


class _DirectFetchMixin:
    async def fetch_page(self, url: str) -> Page | None:
        return await fetch_html(url)


class OllamaWebSearch(WebSearchBackend):
    """Ollama's hosted web search (uses the same key as Ollama Cloud)."""

    name = "ollama"

    def __init__(self, api_key: str, base_url: str = "https://ollama.com") -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")

    async def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        async with httpx.AsyncClient(timeout=_SEARCH_TIMEOUT) as client:
            resp = await client.post(
                f"{self._base_url}/api/web_search",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={"query": query, "max_results": max_results},
            )
            resp.raise_for_status()
            data = resp.json()
        return [
            SearchResult(
                r.get("title", ""),
                r.get("url", ""),
                (r.get("content") or "")[:600],
                content=(r.get("content") or "")[:30000],
            )
            for r in data.get("results", [])
            if r.get("url")
        ]

    async def fetch_page(self, url: str) -> Page | None:
        """Fetch directly; for sites that block that, use Ollama's hosted web_fetch."""
        page = await fetch_html(url)
        if page is not None:
            return page
        try:
            async with httpx.AsyncClient(timeout=_SEARCH_TIMEOUT) as client:
                resp = await client.post(
                    f"{self._base_url}/api/web_fetch",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json={"url": url},
                )
                resp.raise_for_status()
                data = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.debug("web_fetch %s failed: %s", url, exc)
            return None
        return Page(text=str(data.get("content") or ""), title=str(data.get("title") or ""))


class TavilyWebSearch(_DirectFetchMixin, WebSearchBackend):
    name = "tavily"

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        async with httpx.AsyncClient(timeout=_SEARCH_TIMEOUT) as client:
            resp = await client.post(
                "https://api.tavily.com/search",
                json={"api_key": self._api_key, "query": query, "max_results": max_results},
            )
            resp.raise_for_status()
            data = resp.json()
        return [
            SearchResult(
                r.get("title", ""),
                r.get("url", ""),
                (r.get("content") or "")[:600],
                r.get("published_date") or "",
            )
            for r in data.get("results", [])
            if r.get("url")
        ]


class BraveWebSearch(_DirectFetchMixin, WebSearchBackend):
    name = "brave"

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        async with httpx.AsyncClient(timeout=_SEARCH_TIMEOUT) as client:
            resp = await client.get(
                "https://api.search.brave.com/res/v1/web/search",
                headers={"X-Subscription-Token": self._api_key, "Accept": "application/json"},
                params={"q": query, "count": max_results},
            )
            resp.raise_for_status()
            data = resp.json()
        return [
            SearchResult(
                r.get("title", ""),
                r.get("url", ""),
                (r.get("description") or "")[:600],
                r.get("page_age") or "",
            )
            for r in data.get("web", {}).get("results", [])
            if r.get("url")
        ]


def make_search_backend(provider: str, ollama_api_key: str = "") -> WebSearchBackend | None:
    """Pick a search backend. ``auto`` uses whichever key is present."""
    provider = provider.lower()
    tavily = os.environ.get("TAVILY_API_KEY", "")
    brave = os.environ.get("BRAVE_API_KEY", "")
    if provider == "none":
        return None
    if provider in ("tavily", "auto") and tavily:
        return TavilyWebSearch(tavily)
    if provider in ("brave", "auto") and brave:
        return BraveWebSearch(brave)
    if provider in ("ollama", "auto") and ollama_api_key:
        return OllamaWebSearch(ollama_api_key)
    return None


def ground_results(results: list[SearchResult], today: date) -> list[GroundedResult]:
    """Attach a publisher name and an absolute date (or None) to each result."""
    out = []
    for r in results:
        d = extract_date(r.url, r.title, r.snippet, r.published, today=today)
        out.append(
            GroundedResult(
                title=r.title,
                url=r.url,
                snippet=r.snippet,
                source=source_name(r.url, r.title),
                date=d.isoformat() if d else None,
            )
        )
    return out


def parse_search_output(output: str) -> list[GroundedResult]:
    """Read back the JSON a ``web_search`` call returned (empty if it wasn't JSON)."""
    try:
        data = json.loads(output)
    except ValueError:
        return []
    if isinstance(data, dict):
        data = data.get("results")
    if not isinstance(data, list):
        return []
    return [
        GroundedResult(
            title=str(r.get("title", "")),
            url=str(r.get("url", "")),
            snippet=str(r.get("snippet", "")),
            source=str(r.get("source", "")) or source_name(str(r.get("url", ""))),
            date=r.get("date") or None,
            headline=bool(r.get("headline", False)),
        )
        for r in data
        if isinstance(r, dict) and r.get("url")
    ]


def parse_search_note(output: str) -> str:
    """The collector's note ("Only 3 recent headlines found...") if there is one."""
    try:
        data = json.loads(output)
    except ValueError:
        return ""
    return str(data.get("note") or "") if isinstance(data, dict) else ""


def _results_json(
    results: list[GroundedResult], note: str = "", limit: int = _MAX_TOOL_OUTPUT - 200
) -> str:
    """Serialise results as JSON that always fits in the tool-output limit.

    Toolbox truncates long outputs, and truncated JSON can't be parsed by the
    grounding step or the tool view, so shorten snippets (then drop the
    lowest-ranked results) until the whole object fits.
    """

    def dump(items: list[GroundedResult], snip: int) -> str:
        rows = [
            {
                "title": r.title,
                "url": r.url,
                "source": r.source,
                "date": r.date,
                "headline": r.headline,
                "snippet": r.snippet if len(r.snippet) <= snip else r.snippet[:snip] + "…",
            }
            for r in items
        ]
        return json.dumps({"results": rows, "note": note}, ensure_ascii=False)

    items = list(results)
    while items:
        for snip in (600, 400, 250, 150, 0):
            out = dump(items, snip)
            if len(out) <= limit:
                return out
        items.pop()
    return dump([], 0)


def web_search_tool(
    backend: WebSearchBackend,
    *,
    fresh_only: bool = False,
    today: date | None = None,
) -> Tool:
    """The ``web_search`` tool.

    With ``fresh_only`` (news / "today" questions) the search goes through the
    news collector: hub pages are expanded into their articles, each article is
    dated from its page, anything older than 48 hours is dropped (undated
    articles are kept and marked), and captions / page titles are filtered out.
    """

    async def handler(args: dict[str, Any]) -> str:
        query = str(args.get("query", "")).strip()
        if not query:
            return "No query given."
        n = int(args.get("max_results") or 5)
        day = today or date.today()
        if fresh_only:
            report = await collect_news(backend, query, day, limit=max(5, min(n, 10)))
            if not report.items:
                return (
                    f"No recent article headlines found for {query!r}. {report.note} "
                    "Tell the user you couldn't find current coverage; do not use older news."
                )
            return _results_json(report.items, report.note)
        results = ground_results(await backend.search(query, max(1, min(n, 10))), day)
        if not results:
            return f"No results for {query!r}."
        return _results_json(results)

    return Tool(
        name="web_search",
        label="Searching web",
        description=(
            "Search the live web. Use for news, current events, prices, weather, "
            "recent releases, or any fact that may have changed. Returns title, url, "
            "source, date and snippet per result. Only state what a snippet says, "
            "and end each line with the source name linked to its url."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "max_results": {"type": "integer", "description": "1-10, default 5"},
            },
            "required": ["query"],
        },
        handler=handler,
    )
