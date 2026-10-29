"""Git operations tool — local repository operations via subprocess."""

import asyncio
import logging
from pathlib import Path

from jarvis.models.approval import RiskLevel
from jarvis.security.validators import PathTraversalError, validate_working_dir
from jarvis.tools.base import BaseTool, InvalidOperationError, ToolError, ToolResult

logger = logging.getLogger(__name__)


class NotAGitRepoError(ToolError):
    """Raised when working_dir is not a git repository."""

    def __init__(self, path: str) -> None:
        self.path = path
        super().__init__(f"Not a git repository: {path!r}")


class GitTool(BaseTool):
    """Local git operations via subprocess."""

    @property
    def name(self) -> str:
        return "git"

    def operations(self) -> dict[str, RiskLevel]:
        return {
            "status": RiskLevel.SAFE,
            "diff": RiskLevel.SAFE,
            "log": RiskLevel.SAFE,
            "branch_list": RiskLevel.SAFE,
            "current_branch": RiskLevel.SAFE,
            "checkout": RiskLevel.REQUIRES_APPROVAL,
            "create_branch": RiskLevel.REQUIRES_APPROVAL,
            "commit": RiskLevel.REQUIRES_APPROVAL,
            "push": RiskLevel.REQUIRES_APPROVAL,
        }

    async def execute(
        self, operation: str, working_dir: str, **kwargs: str | int | list[str]
    ) -> ToolResult:
        if operation not in self.operations():
            raise InvalidOperationError(self.name, operation)

        try:
            working_dir = validate_working_dir(working_dir)
        except PathTraversalError as e:
            raise ToolError(str(e)) from e

        self._validate_repo(working_dir)

        dispatch = {
            "status": self._status,
            "diff": self._diff,
            "log": self._log,
            "branch_list": self._branch_list,
            "current_branch": self._current_branch,
            "checkout": self._checkout,
            "create_branch": self._create_branch,
            "commit": self._commit,
            "push": self._push,
        }
        return await dispatch[operation](working_dir, **kwargs)

    @staticmethod
    def _validate_repo(working_dir: str) -> None:
        path = Path(working_dir)
        if not path.is_dir():
            raise NotAGitRepoError(working_dir)
        if not (path / ".git").exists():
            raise NotAGitRepoError(working_dir)

    @staticmethod
    async def _run_git(working_dir: str, *args: str) -> ToolResult:
        proc = await asyncio.create_subprocess_exec(
            "git",
            *args,
            cwd=working_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_bytes, stderr_bytes = await proc.communicate()
        exit_code = proc.returncode or 0
        stdout = stdout_bytes.decode("utf-8", errors="replace").rstrip()
        stderr = stderr_bytes.decode("utf-8", errors="replace").rstrip()
        return ToolResult(
            success=exit_code == 0,
            output=stdout,
            error=stderr if stderr else None,
            exit_code=exit_code,
        )

    async def _status(self, working_dir: str, **kwargs: str | int | list[str]) -> ToolResult:
        return await self._run_git(working_dir, "status", "--porcelain")

    async def _diff(self, working_dir: str, **kwargs: str | int | list[str]) -> ToolResult:
        args = ["diff"]
        if kwargs.get("cached"):
            args.append("--cached")
        path = kwargs.get("path")
        if isinstance(path, str) and path:
            args.append("--")
            args.append(path)
        return await self._run_git(working_dir, *args)

    async def _log(self, working_dir: str, **kwargs: str | int | list[str]) -> ToolResult:
        raw_limit = kwargs.get("limit", 10)
        limit = raw_limit if isinstance(raw_limit, int) else int(str(raw_limit))
        return await self._run_git(working_dir, "log", "--oneline", f"-n{limit}")

    async def _branch_list(self, working_dir: str, **kwargs: str | int | list[str]) -> ToolResult:
        return await self._run_git(working_dir, "branch", "--list")

    async def _current_branch(
        self, working_dir: str, **kwargs: str | int | list[str]
    ) -> ToolResult:
        return await self._run_git(working_dir, "rev-parse", "--abbrev-ref", "HEAD")

    async def _checkout(self, working_dir: str, **kwargs: str | int | list[str]) -> ToolResult:
        branch = kwargs.get("branch")
        if not isinstance(branch, str) or not branch:
            return ToolResult(success=False, output="", error="branch is required", exit_code=1)
        return await self._run_git(working_dir, "checkout", branch)

    async def _create_branch(
        self, working_dir: str, **kwargs: str | int | list[str]
    ) -> ToolResult:
        branch = kwargs.get("branch")
        if not isinstance(branch, str) or not branch:
            return ToolResult(success=False, output="", error="branch is required", exit_code=1)
        return await self._run_git(working_dir, "checkout", "-b", branch)

    async def _commit(self, working_dir: str, **kwargs: str | int | list[str]) -> ToolResult:
        message = kwargs.get("message")
        if not isinstance(message, str) or not message:
            return ToolResult(
                success=False,
                output="",
                error="message is required",
                exit_code=1,
            )

        files = kwargs.get("files")
        if not isinstance(files, list) or not files:
            return ToolResult(
                success=False,
                output="",
                error="files list is required",
                exit_code=1,
            )

        # Stage files first
        add_result = await self._run_git(working_dir, "add", "--", *files)
        if not add_result.success:
            return add_result

        return await self._run_git(working_dir, "commit", "-m", message)

    async def _push(self, working_dir: str, **kwargs: str | int | list[str]) -> ToolResult:
        args = ["push"]
        if kwargs.get("set_upstream"):
            branch = kwargs.get("branch")
            if not isinstance(branch, str) or not branch:
                return ToolResult(
                    success=False,
                    output="",
                    error="branch is required with set_upstream",
                    exit_code=1,
                )
            args.extend(["--set-upstream", "origin", branch])
        return await self._run_git(working_dir, *args)
