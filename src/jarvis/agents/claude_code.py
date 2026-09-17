"""Claude Code subprocess agent — launches claude CLI as a managed process."""

import asyncio
import logging
import os
import shutil
import time
from pathlib import Path

from jarvis.agents.base import AgentError, BaseAgent

logger = logging.getLogger(__name__)

# Environment variables allowed to pass through to the subprocess.
_ALLOWED_ENV_KEYS: frozenset[str] = frozenset({
    "HOME",
    "PATH",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "TERM",
    "USER",
    "SHELL",
    "ANTHROPIC_API_KEY",
    "CLAUDE_API_KEY",
    "XDG_CONFIG_HOME",
    "XDG_DATA_HOME",
    "TMPDIR",
})


class ClaudeNotFoundError(AgentError):
    """Raised when the claude CLI binary cannot be found."""

    def __init__(self, command: str) -> None:
        self.command = command
        super().__init__(f"Claude CLI not found: {command!r}")


class InvalidProjectPathError(AgentError):
    """Raised when the project working directory does not exist."""

    def __init__(self, path: str) -> None:
        self.path = path
        super().__init__(f"Project path does not exist: {path!r}")


class ClaudeCodeAgent(BaseAgent):
    """Manages a single Claude Code CLI subprocess.

    Responsible only for OS process management — no database access.
    """

    @property
    def agent_name(self) -> str:
        return "claude_code"

    def __init__(self, claude_command: str = "claude", timeout: int = 300) -> None:
        resolved = shutil.which(claude_command)
        if resolved is None:
            raise ClaudeNotFoundError(claude_command)
        self._claude_path: str = resolved
        self._timeout = timeout
        self._process: asyncio.subprocess.Process | None = None
        self._start_time: float | None = None
        self._end_time: float | None = None
        self._status: str = "not_started"

    def _sanitized_env(self) -> dict[str, str]:
        """Build a sanitized environment with only allowed keys."""
        return {k: v for k, v in os.environ.items() if k in _ALLOWED_ENV_KEYS}

    async def run(self, prompt: str, working_dir: str) -> tuple[int, str, str]:
        """Launch claude --print -p "<prompt>" and capture output.

        Returns (exit_code, stdout, stderr).
        """
        path = Path(working_dir)
        if not path.is_dir():
            raise InvalidProjectPathError(working_dir)

        self._status = "running"
        self._start_time = time.monotonic()

        try:
            self._process = await asyncio.create_subprocess_exec(
                self._claude_path,
                "--print",
                "-p",
                prompt,
                cwd=working_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=self._sanitized_env(),
            )

            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                self._process.communicate(),
                timeout=self._timeout,
            )

            self._end_time = time.monotonic()
            exit_code = self._process.returncode or 0
            self._status = "completed" if exit_code == 0 else "failed"

            stdout = stdout_bytes.decode("utf-8", errors="replace")
            stderr = stderr_bytes.decode("utf-8", errors="replace")
            return exit_code, stdout, stderr

        except TimeoutError:
            self._end_time = time.monotonic()
            self._status = "failed"
            if self._process is not None:
                self._process.kill()
                await self._process.wait()
            raise

        except asyncio.CancelledError:
            self._end_time = time.monotonic()
            self._status = "cancelled"
            if self._process is not None:
                self._process.kill()
                await self._process.wait()
            raise

    def status(self) -> str:
        """Return the current status: not_started, running, completed, failed, cancelled."""
        return self._status

    async def cancel(self) -> None:
        """Kill the running process."""
        if self._process is not None and self._process.returncode is None:
            self._process.kill()
            await self._process.wait()
            self._status = "cancelled"
            self._end_time = time.monotonic()

    def elapsed_seconds(self) -> float | None:
        """Return elapsed time in seconds, or None if not started."""
        if self._start_time is None:
            return None
        end = self._end_time or time.monotonic()
        return end - self._start_time
