"""Tests for ClaudeCodeAgent subprocess management."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from jarvis.agents.claude_code import (
    ClaudeCodeAgent,
    ClaudeNotFoundError,
    InvalidProjectPathError,
)


class TestInit:
    def test_raises_when_claude_not_found(self) -> None:
        with patch("shutil.which", return_value=None):
            with pytest.raises(ClaudeNotFoundError, match="not-a-real-binary"):
                ClaudeCodeAgent(claude_command="not-a-real-binary")

    def test_resolves_path_via_shutil_which(self) -> None:
        with patch("shutil.which", return_value="/usr/local/bin/claude"):
            agent = ClaudeCodeAgent(claude_command="claude")
            assert agent._claude_path == "/usr/local/bin/claude"

    def test_default_timeout(self) -> None:
        with patch("shutil.which", return_value="/usr/local/bin/claude"):
            agent = ClaudeCodeAgent()
            assert agent._timeout == 300

    def test_custom_timeout(self) -> None:
        with patch("shutil.which", return_value="/usr/local/bin/claude"):
            agent = ClaudeCodeAgent(timeout=60)
            assert agent._timeout == 60


class TestRun:
    @pytest.fixture
    def agent(self) -> ClaudeCodeAgent:
        with patch("shutil.which", return_value="/usr/local/bin/claude"):
            return ClaudeCodeAgent(timeout=10)

    @pytest.mark.asyncio
    async def test_success(
        self, agent: ClaudeCodeAgent, tmp_path: str,
    ) -> None:
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(
            return_value=(b"output", b""),
        )
        mock_process.returncode = 0

        with patch(
            "asyncio.create_subprocess_exec",
            return_value=mock_process,
        ):
            exit_code, stdout, stderr = await agent.run(
                "fix bug", str(tmp_path),
            )

        assert exit_code == 0
        assert stdout == "output"
        assert stderr == ""
        assert agent.status() == "completed"

    @pytest.mark.asyncio
    async def test_failure_nonzero_exit(
        self, agent: ClaudeCodeAgent, tmp_path: str,
    ) -> None:
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(
            return_value=(b"", b"error output"),
        )
        mock_process.returncode = 1

        with patch(
            "asyncio.create_subprocess_exec",
            return_value=mock_process,
        ):
            exit_code, stdout, stderr = await agent.run(
                "fix bug", str(tmp_path),
            )

        assert exit_code == 1
        assert stderr == "error output"
        assert agent.status() == "failed"

    @pytest.mark.asyncio
    async def test_timeout(
        self, agent: ClaudeCodeAgent, tmp_path: str,
    ) -> None:
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(
            side_effect=asyncio.TimeoutError,
        )
        mock_process.kill = MagicMock()
        mock_process.wait = AsyncMock()

        with patch(
            "asyncio.create_subprocess_exec",
            return_value=mock_process,
        ):
            with pytest.raises(asyncio.TimeoutError):
                await agent.run("fix bug", str(tmp_path))

        assert agent.status() == "failed"
        mock_process.kill.assert_called_once()

    @pytest.mark.asyncio
    async def test_cancellation(
        self, agent: ClaudeCodeAgent, tmp_path: str,
    ) -> None:
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(
            side_effect=asyncio.CancelledError,
        )
        mock_process.kill = MagicMock()
        mock_process.wait = AsyncMock()

        with patch(
            "asyncio.create_subprocess_exec",
            return_value=mock_process,
        ):
            with pytest.raises(asyncio.CancelledError):
                await agent.run("fix bug", str(tmp_path))

        assert agent.status() == "cancelled"

    @pytest.mark.asyncio
    async def test_invalid_path(
        self, agent: ClaudeCodeAgent,
    ) -> None:
        with pytest.raises(
            InvalidProjectPathError, match="does-not-exist",
        ):
            await agent.run("fix bug", "/does-not-exist")

    @pytest.mark.asyncio
    async def test_env_sanitization(
        self, agent: ClaudeCodeAgent, tmp_path: str,
    ) -> None:
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(
            return_value=(b"ok", b""),
        )
        mock_process.returncode = 0

        captured_env: dict[str, str] = {}

        async def capture_exec(
            *args, **kwargs,  # type: ignore[no-untyped-def]
        ):
            captured_env.update(kwargs.get("env", {}))
            return mock_process

        env = {
            "HOME": "/home/user",
            "SECRET_KEY": "bad",
            "PATH": "/usr/bin",
            "DB_PASSWORD": "bad",
        }
        with (
            patch(
                "asyncio.create_subprocess_exec",
                side_effect=capture_exec,
            ),
            patch.dict("os.environ", env, clear=True),
        ):
            await agent.run("fix bug", str(tmp_path))

        assert "HOME" in captured_env
        assert "PATH" in captured_env
        assert "SECRET_KEY" not in captured_env
        assert "DB_PASSWORD" not in captured_env

    @pytest.mark.asyncio
    async def test_no_shell_true(
        self, agent: ClaudeCodeAgent, tmp_path: str,
    ) -> None:
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(
            return_value=(b"ok", b""),
        )
        mock_process.returncode = 0

        captured_kwargs: dict = {}  # type: ignore[type-arg]

        async def capture_exec(
            *args, **kwargs,  # type: ignore[no-untyped-def]
        ):
            captured_kwargs.update(kwargs)
            return mock_process

        with patch(
            "asyncio.create_subprocess_exec",
            side_effect=capture_exec,
        ):
            await agent.run("fix bug", str(tmp_path))

        assert "shell" not in captured_kwargs

    @pytest.mark.asyncio
    async def test_prompt_passed_as_argument(
        self, agent: ClaudeCodeAgent, tmp_path: str,
    ) -> None:
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(
            return_value=(b"ok", b""),
        )
        mock_process.returncode = 0

        captured_args: tuple = ()  # type: ignore[type-arg]

        async def capture_exec(
            *args, **kwargs,  # type: ignore[no-untyped-def]
        ):
            nonlocal captured_args
            captured_args = args
            return mock_process

        with patch(
            "asyncio.create_subprocess_exec",
            side_effect=capture_exec,
        ):
            await agent.run(
                "fix the $(whoami) bug", str(tmp_path),
            )

        # Prompt is a separate arg, not interpolated into shell
        assert "fix the $(whoami) bug" in captured_args


class TestStatus:
    def test_not_started(self) -> None:
        with patch("shutil.which", return_value="/usr/local/bin/claude"):
            agent = ClaudeCodeAgent()
        assert agent.status() == "not_started"

    @pytest.mark.asyncio
    async def test_running_then_completed(
        self, tmp_path: str,
    ) -> None:
        with patch("shutil.which", return_value="/usr/local/bin/claude"):
            agent = ClaudeCodeAgent()

        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(
            return_value=(b"ok", b""),
        )
        mock_process.returncode = 0

        with patch(
            "asyncio.create_subprocess_exec",
            return_value=mock_process,
        ):
            await agent.run("test", str(tmp_path))

        assert agent.status() == "completed"

    @pytest.mark.asyncio
    async def test_failed(self, tmp_path: str) -> None:
        with patch("shutil.which", return_value="/usr/local/bin/claude"):
            agent = ClaudeCodeAgent()

        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(
            return_value=(b"", b"err"),
        )
        mock_process.returncode = 1

        with patch(
            "asyncio.create_subprocess_exec",
            return_value=mock_process,
        ):
            await agent.run("test", str(tmp_path))

        assert agent.status() == "failed"


class TestElapsedSeconds:
    def test_none_before_start(self) -> None:
        with patch("shutil.which", return_value="/usr/local/bin/claude"):
            agent = ClaudeCodeAgent()
        assert agent.elapsed_seconds() is None

    @pytest.mark.asyncio
    async def test_returns_float_after_run(
        self, tmp_path: str,
    ) -> None:
        with patch("shutil.which", return_value="/usr/local/bin/claude"):
            agent = ClaudeCodeAgent()

        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(
            return_value=(b"ok", b""),
        )
        mock_process.returncode = 0

        with patch(
            "asyncio.create_subprocess_exec",
            return_value=mock_process,
        ):
            await agent.run("test", str(tmp_path))

        elapsed = agent.elapsed_seconds()
        assert elapsed is not None
        assert elapsed >= 0.0


class TestCancel:
    @pytest.mark.asyncio
    async def test_cancel_running_process(
        self, tmp_path: str,
    ) -> None:
        with patch("shutil.which", return_value="/usr/local/bin/claude"):
            agent = ClaudeCodeAgent()

        mock_process = AsyncMock()
        mock_process.returncode = None  # still running
        mock_process.kill = MagicMock()
        mock_process.wait = AsyncMock()
        agent._process = mock_process

        await agent.cancel()

        mock_process.kill.assert_called_once()
        assert agent.status() == "cancelled"

    @pytest.mark.asyncio
    async def test_cancel_no_process(self) -> None:
        with patch("shutil.which", return_value="/usr/local/bin/claude"):
            agent = ClaudeCodeAgent()

        # Should not raise
        await agent.cancel()
        assert agent.status() == "not_started"
