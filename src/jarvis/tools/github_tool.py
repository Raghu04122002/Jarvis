"""GitHub CLI operations tool — interacts with GitHub via the gh CLI."""

import asyncio
import logging
import re

from jarvis.models.approval import RiskLevel
from jarvis.tools.base import BaseTool, InvalidOperationError, ToolError, ToolResult

logger = logging.getLogger(__name__)

_REPO_PATTERN = re.compile(r"^[a-zA-Z0-9._-]+/[a-zA-Z0-9._-]+$")


class InvalidRepoFormatError(ToolError):
    """Raised when the repo string doesn't match owner/repo format."""

    def __init__(self, repo: str) -> None:
        self.repo = repo
        super().__init__(f"Invalid repo format: {repo!r}. Expected 'owner/repo'.")


class GitHubTool(BaseTool):
    """GitHub operations via the gh CLI."""

    @property
    def name(self) -> str:
        return "github"

    def operations(self) -> dict[str, RiskLevel]:
        return {
            "issue_list": RiskLevel.SAFE,
            "issue_view": RiskLevel.SAFE,
            "pr_list": RiskLevel.SAFE,
            "pr_view": RiskLevel.SAFE,
            "ci_status": RiskLevel.SAFE,
            "pr_create": RiskLevel.REQUIRES_APPROVAL,
            "pr_merge": RiskLevel.BLOCKED,
        }

    async def execute(
        self, operation: str, working_dir: str, **kwargs: str | int | list[str]
    ) -> ToolResult:
        if operation not in self.operations():
            raise InvalidOperationError(self.name, operation)

        dispatch = {
            "issue_list": self._issue_list,
            "issue_view": self._issue_view,
            "pr_list": self._pr_list,
            "pr_view": self._pr_view,
            "ci_status": self._ci_status,
            "pr_create": self._pr_create,
            "pr_merge": self._pr_merge,
        }
        return await dispatch[operation](working_dir, **kwargs)

    @staticmethod
    def _validate_repo_format(repo: str) -> None:
        if not _REPO_PATTERN.match(repo):
            raise InvalidRepoFormatError(repo)

    @staticmethod
    async def _run_gh(working_dir: str, *args: str) -> ToolResult:
        proc = await asyncio.create_subprocess_exec(
            "gh",
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

    def _get_repo(self, kwargs: dict[str, str | int | list[str]]) -> str:
        repo = kwargs.get("repo")
        if not isinstance(repo, str) or not repo:
            raise InvalidRepoFormatError("")
        self._validate_repo_format(repo)
        return repo

    async def _issue_list(self, working_dir: str, **kwargs: str | int | list[str]) -> ToolResult:
        repo = self._get_repo(kwargs)
        return await self._run_gh(
            working_dir,
            "issue",
            "list",
            "--repo",
            repo,
            "--json",
            "number,title,state",
        )

    async def _issue_view(self, working_dir: str, **kwargs: str | int | list[str]) -> ToolResult:
        repo = self._get_repo(kwargs)
        number = kwargs.get("number")
        if not isinstance(number, (str, int)) or not str(number):
            return ToolResult(success=False, output="", error="number is required", exit_code=1)
        return await self._run_gh(
            working_dir,
            "issue",
            "view",
            str(number),
            "--repo",
            repo,
            "--json",
            "number,title,body,state",
        )

    async def _pr_list(self, working_dir: str, **kwargs: str | int | list[str]) -> ToolResult:
        repo = self._get_repo(kwargs)
        return await self._run_gh(
            working_dir,
            "pr",
            "list",
            "--repo",
            repo,
            "--json",
            "number,title,state",
        )

    async def _pr_view(self, working_dir: str, **kwargs: str | int | list[str]) -> ToolResult:
        repo = self._get_repo(kwargs)
        number = kwargs.get("number")
        if not isinstance(number, (str, int)) or not str(number):
            return ToolResult(success=False, output="", error="number is required", exit_code=1)
        return await self._run_gh(
            working_dir,
            "pr",
            "view",
            str(number),
            "--repo",
            repo,
            "--json",
            "number,title,body,state",
        )

    async def _ci_status(self, working_dir: str, **kwargs: str | int | list[str]) -> ToolResult:
        repo = self._get_repo(kwargs)
        return await self._run_gh(
            working_dir,
            "run",
            "list",
            "--repo",
            repo,
            "--limit",
            "5",
            "--json",
            "status,conclusion,name",
        )

    async def _pr_create(self, working_dir: str, **kwargs: str | int | list[str]) -> ToolResult:
        repo = self._get_repo(kwargs)
        title = kwargs.get("title")
        if not isinstance(title, str) or not title:
            return ToolResult(success=False, output="", error="title is required", exit_code=1)
        body = kwargs.get("body", "")
        if not isinstance(body, str):
            body = ""
        return await self._run_gh(
            working_dir,
            "pr",
            "create",
            "--repo",
            repo,
            "--title",
            title,
            "--body",
            body,
        )

    async def _pr_merge(self, working_dir: str, **kwargs: str | int | list[str]) -> ToolResult:
        return ToolResult(
            success=False,
            output="",
            error="pr_merge is permanently blocked for safety",
            exit_code=1,
        )
