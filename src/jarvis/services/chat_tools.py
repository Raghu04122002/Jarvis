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
from typing import Any

import httpx

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


class WebSearchBackend:
    """Base class: ``search`` returns real results with real URLs."""

    name = "base"

    async def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        raise NotImplementedError


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
            SearchResult(r.get("title", ""), r.get("url", ""), (r.get("content") or "")[:600])
            for r in data.get("results", [])
            if r.get("url")
        ]


class TavilyWebSearch(WebSearchBackend):
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
            SearchResult(r.get("title", ""), r.get("url", ""), (r.get("content") or "")[:600])
            for r in data.get("results", [])
            if r.get("url")
        ]


class BraveWebSearch(WebSearchBackend):
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
            SearchResult(r.get("title", ""), r.get("url", ""), (r.get("description") or "")[:600])
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


def web_search_tool(backend: WebSearchBackend) -> Tool:
    async def handler(args: dict[str, Any]) -> str:
        query = str(args.get("query", "")).strip()
        if not query:
            return "No query given."
        n = int(args.get("max_results") or 5)
        results = await backend.search(query, max(1, min(n, 10)))
        if not results:
            return f"No results for {query!r}."
        return json.dumps(
            [{"title": r.title, "url": r.url, "snippet": r.snippet} for r in results],
            ensure_ascii=False,
        )

    return Tool(
        name="web_search",
        label="Searching web",
        description=(
            "Search the live web. Use for news, current events, prices, weather, "
            "recent releases, or any fact that may have changed. Returns titles, URLs "
            "and snippets; cite the URLs you use."
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
