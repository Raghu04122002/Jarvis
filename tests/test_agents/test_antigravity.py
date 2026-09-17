"""Tests for the AntigravityAgent."""

from unittest.mock import patch

import pytest

from jarvis.agents.antigravity import (
    _ALLOWED_ENV_KEYS,
    AntigravityAgent,
    AntigravityNotFoundError,
)
from jarvis.agents.base import AgentError


class TestAntigravityNotFoundError:
    def test_is_agent_error(self) -> None:
        assert issubclass(AntigravityNotFoundError, AgentError)

    def test_message(self) -> None:
        err = AntigravityNotFoundError("ag")
        assert "ag" in str(err)
        assert err.command == "ag"


class TestAntigravityAgent:
    def test_raises_when_binary_not_found(self) -> None:
        with patch("shutil.which", return_value=None):
            with pytest.raises(AntigravityNotFoundError):
                AntigravityAgent(antigravity_command="nonexistent")

    def test_agent_name(self) -> None:
        with patch("shutil.which", return_value="/usr/bin/antigravity"):
            agent = AntigravityAgent()
            assert agent.agent_name == "antigravity"

    def test_status_initial(self) -> None:
        with patch("shutil.which", return_value="/usr/bin/antigravity"):
            agent = AntigravityAgent()
            assert agent.status() == "not_started"

    def test_elapsed_seconds_not_started(self) -> None:
        with patch("shutil.which", return_value="/usr/bin/antigravity"):
            agent = AntigravityAgent()
            assert agent.elapsed_seconds() is None

    @pytest.mark.asyncio
    async def test_cancel_noop_when_not_started(self) -> None:
        with patch("shutil.which", return_value="/usr/bin/antigravity"):
            agent = AntigravityAgent()
            await agent.cancel()  # should not raise

    def test_allowed_env_keys_contains_antigravity_api_key(self) -> None:
        assert "ANTIGRAVITY_API_KEY" in _ALLOWED_ENV_KEYS

    def test_allowed_env_keys_contains_common_keys(self) -> None:
        assert "HOME" in _ALLOWED_ENV_KEYS
        assert "PATH" in _ALLOWED_ENV_KEYS

    def test_run_with_invalid_dir(self) -> None:
        with patch("shutil.which", return_value="/usr/bin/antigravity"):
            agent = AntigravityAgent()

            async def _run() -> None:
                from jarvis.agents.claude_code import InvalidProjectPathError

                with pytest.raises(InvalidProjectPathError):
                    await agent.run("test", "/nonexistent/path/that/does/not/exist")

            import asyncio

            asyncio.get_event_loop().run_until_complete(_run())
