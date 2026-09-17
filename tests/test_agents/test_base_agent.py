"""Tests for the BaseAgent ABC."""

import pytest

from jarvis.agents.base import AgentError, BaseAgent


class ConcreteAgent(BaseAgent):
    """Minimal concrete implementation for testing the ABC."""

    @property
    def agent_name(self) -> str:
        return "test_agent"

    async def run(self, prompt: str, working_dir: str) -> tuple[int, str, str]:
        return 0, "ok", ""

    async def cancel(self) -> None:
        pass

    def status(self) -> str:
        return "not_started"

    def elapsed_seconds(self) -> float | None:
        return None


class TestBaseAgent:
    def test_cannot_instantiate_abc(self) -> None:
        with pytest.raises(TypeError):
            BaseAgent()  # type: ignore[abstract]

    def test_concrete_agent_name(self) -> None:
        agent = ConcreteAgent()
        assert agent.agent_name == "test_agent"

    @pytest.mark.asyncio
    async def test_concrete_agent_run(self) -> None:
        agent = ConcreteAgent()
        exit_code, stdout, stderr = await agent.run("hello", "/tmp")
        assert exit_code == 0
        assert stdout == "ok"

    def test_concrete_agent_status(self) -> None:
        agent = ConcreteAgent()
        assert agent.status() == "not_started"

    def test_concrete_agent_elapsed(self) -> None:
        agent = ConcreteAgent()
        assert agent.elapsed_seconds() is None

    @pytest.mark.asyncio
    async def test_concrete_agent_cancel(self) -> None:
        agent = ConcreteAgent()
        await agent.cancel()  # should not raise

    def test_agent_error_is_exception(self) -> None:
        assert issubclass(AgentError, Exception)

    def test_agent_error_message(self) -> None:
        err = AgentError("something went wrong")
        assert str(err) == "something went wrong"
