"""Tests for the AgentRegistry."""

import pytest

from jarvis.agents.base import BaseAgent
from jarvis.agents.registry import (
    AgentNotFoundError,
    AgentRegistry,
    create_default_registry,
)
from jarvis.config import AgentsConfig


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


class TestAgentRegistry:
    def test_register_and_create(self) -> None:
        registry = AgentRegistry()
        registry.register("fake", lambda _cfg: _FakeAgent())
        agent = registry.create("fake", AgentsConfig())
        assert agent.agent_name == "fake"

    def test_create_unknown_raises(self) -> None:
        registry = AgentRegistry()
        with pytest.raises(AgentNotFoundError) as exc_info:
            registry.create("unknown", AgentsConfig())
        assert exc_info.value.name == "unknown"

    def test_list_agents(self) -> None:
        registry = AgentRegistry()
        registry.register("b_agent", lambda _cfg: _FakeAgent())
        registry.register("a_agent", lambda _cfg: _FakeAgent())
        assert registry.list_agents() == ["a_agent", "b_agent"]

    def test_has(self) -> None:
        registry = AgentRegistry()
        assert not registry.has("fake")
        registry.register("fake", lambda _cfg: _FakeAgent())
        assert registry.has("fake")

    def test_list_agents_empty(self) -> None:
        registry = AgentRegistry()
        assert registry.list_agents() == []


class TestAgentNotFoundError:
    def test_is_exception(self) -> None:
        err = AgentNotFoundError("test")
        assert isinstance(err, Exception)
        assert err.name == "test"

    def test_message(self) -> None:
        err = AgentNotFoundError("missing")
        assert "missing" in str(err)


class TestCreateDefaultRegistry:
    def test_has_claude_code(self) -> None:
        registry = create_default_registry()
        assert registry.has("claude_code")

    def test_has_antigravity(self) -> None:
        registry = create_default_registry()
        assert registry.has("antigravity")

    def test_list_agents(self) -> None:
        registry = create_default_registry()
        agents = registry.list_agents()
        assert "claude_code" in agents
        assert "antigravity" in agents
