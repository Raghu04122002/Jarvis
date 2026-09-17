"""Tests for the AgentRouter."""

import pytest

from jarvis.agents.base import BaseAgent
from jarvis.agents.registry import AgentRegistry
from jarvis.agents.router import _ANTIGRAVITY_KEYWORDS, AgentRouter
from jarvis.config import AgentsConfig
from jarvis.models.task import Task, TaskStatus


class _FakeAgent(BaseAgent):
    @property
    def agent_name(self) -> str:
        return "fake"

    async def run(self, prompt: str, working_dir: str) -> tuple[int, str, str]:
        return 0, "", ""

    async def cancel(self) -> None:
        pass

    def status(self) -> str:
        return "not_started"

    def elapsed_seconds(self) -> float | None:
        return None


def _make_registry() -> AgentRegistry:
    registry = AgentRegistry()
    registry.register("claude_code", lambda _cfg: _FakeAgent())
    registry.register("antigravity", lambda _cfg: _FakeAgent())
    return registry


def _make_task(request: str = "Fix a bug", metadata: dict[str, str] | None = None) -> Task:
    return Task(
        id="TASK-1",
        request=request,
        title="Test",
        status=TaskStatus.PLANNING,
        metadata=metadata or {},
    )


class TestAgentRouter:
    def test_default_selects_claude_code(self) -> None:
        router = AgentRouter(_make_registry(), AgentsConfig())
        task = _make_task("Fix a bug in the code")
        assert router.select(task) == "claude_code"

    def test_explicit_agent_name_in_metadata(self) -> None:
        router = AgentRouter(_make_registry(), AgentsConfig())
        task = _make_task(metadata={"agent_name": "antigravity"})
        assert router.select(task) == "antigravity"

    def test_explicit_agent_name_unknown_falls_through(self) -> None:
        router = AgentRouter(_make_registry(), AgentsConfig())
        task = _make_task("Fix a bug", metadata={"agent_name": "unknown_agent"})
        assert router.select(task) == "claude_code"

    def test_preferred_agent_config(self) -> None:
        config = AgentsConfig(preferred_agent="antigravity")
        router = AgentRouter(_make_registry(), config)
        task = _make_task("Fix a bug")
        assert router.select(task) == "antigravity"

    def test_preferred_agent_default_does_not_override_keywords(self) -> None:
        # preferred_agent=claude_code (default) should still allow keyword matching
        router = AgentRouter(_make_registry(), AgentsConfig())
        task = _make_task("Take a screenshot of the page")
        assert router.select(task) == "antigravity"

    @pytest.mark.parametrize("keyword", sorted(_ANTIGRAVITY_KEYWORDS))
    def test_keyword_matching(self, keyword: str) -> None:
        router = AgentRouter(_make_registry(), AgentsConfig())
        task = _make_task(f"Please do something with {keyword}")
        assert router.select(task) == "antigravity"

    def test_keyword_case_insensitive(self) -> None:
        router = AgentRouter(_make_registry(), AgentsConfig())
        task = _make_task("Take a SCREENSHOT")
        assert router.select(task) == "antigravity"

    def test_metadata_overrides_keywords(self) -> None:
        router = AgentRouter(_make_registry(), AgentsConfig())
        task = _make_task(
            "Take a screenshot",
            metadata={"agent_name": "claude_code"},
        )
        assert router.select(task) == "claude_code"

    def test_metadata_overrides_preferred(self) -> None:
        config = AgentsConfig(preferred_agent="antigravity")
        router = AgentRouter(_make_registry(), config)
        task = _make_task(metadata={"agent_name": "claude_code"})
        assert router.select(task) == "claude_code"


class TestAgentRouterFallback:
    def test_fallback_for_claude_code(self) -> None:
        router = AgentRouter(_make_registry(), AgentsConfig())
        assert router.fallback_for("claude_code") == "antigravity"

    def test_fallback_for_antigravity(self) -> None:
        router = AgentRouter(_make_registry(), AgentsConfig())
        assert router.fallback_for("antigravity") == "claude_code"

    def test_fallback_for_unknown(self) -> None:
        router = AgentRouter(_make_registry(), AgentsConfig())
        assert router.fallback_for("unknown") is None

    def test_fallback_none_when_not_registered(self) -> None:
        registry = AgentRegistry()
        registry.register("claude_code", lambda _cfg: _FakeAgent())
        router = AgentRouter(registry, AgentsConfig())
        # antigravity is the fallback for claude_code but not registered
        assert router.fallback_for("claude_code") is None
