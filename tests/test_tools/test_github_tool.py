"""Tests for GitHubTool — mocked subprocess calls."""

from unittest.mock import AsyncMock, patch

import pytest

from jarvis.models.approval import RiskLevel
from jarvis.tools.base import InvalidOperationError
from jarvis.tools.github_tool import GitHubTool, InvalidRepoFormatError

_GH_SUBPROCESS = (
    "jarvis.tools.github_tool.asyncio.create_subprocess_exec"
)


@pytest.fixture
def tool() -> GitHubTool:
    return GitHubTool()


def _mock_process(stdout: str = "", stderr: str = "", returncode: int = 0) -> AsyncMock:
    proc = AsyncMock()
    proc.communicate.return_value = (
        stdout.encode(),
        stderr.encode(),
    )
    proc.returncode = returncode
    return proc


class TestGitHubToolMeta:
    def test_name(self, tool: GitHubTool) -> None:
        assert tool.name == "github"

    def test_operations(self, tool: GitHubTool) -> None:
        ops = tool.operations()
        assert ops["issue_list"] == RiskLevel.SAFE
        assert ops["issue_view"] == RiskLevel.SAFE
        assert ops["pr_list"] == RiskLevel.SAFE
        assert ops["pr_view"] == RiskLevel.SAFE
        assert ops["ci_status"] == RiskLevel.SAFE
        assert ops["pr_create"] == RiskLevel.REQUIRES_APPROVAL
        assert ops["pr_merge"] == RiskLevel.BLOCKED


class TestGitHubToolValidation:
    @pytest.mark.asyncio
    async def test_invalid_operation(self, tool: GitHubTool) -> None:
        with pytest.raises(InvalidOperationError):
            await tool.execute("destroy", "/tmp", repo="owner/repo")

    @pytest.mark.asyncio
    async def test_invalid_repo_format_no_slash(self, tool: GitHubTool) -> None:
        with pytest.raises(InvalidRepoFormatError):
            await tool.execute("issue_list", "/tmp", repo="noslash")

    @pytest.mark.asyncio
    async def test_invalid_repo_format_empty(self, tool: GitHubTool) -> None:
        with pytest.raises(InvalidRepoFormatError):
            await tool.execute("issue_list", "/tmp", repo="")

    @pytest.mark.asyncio
    async def test_invalid_repo_format_special_chars(self, tool: GitHubTool) -> None:
        with pytest.raises(InvalidRepoFormatError):
            await tool.execute("issue_list", "/tmp", repo="owner/repo with spaces")

    def test_validate_repo_format_valid(self, tool: GitHubTool) -> None:
        # Should not raise
        GitHubTool._validate_repo_format("owner/repo")
        GitHubTool._validate_repo_format("my-org/my.repo_123")


class TestGitHubToolIssues:
    @pytest.mark.asyncio
    async def test_issue_list(self, tool: GitHubTool) -> None:
        mock_proc = _mock_process('[{"number":1,"title":"Bug","state":"OPEN"}]')
        with patch(_GH_SUBPROCESS, return_value=mock_proc):
            result = await tool.execute("issue_list", "/tmp", repo="owner/repo")
        assert result.success is True
        assert "Bug" in result.output

    @pytest.mark.asyncio
    async def test_issue_view(self, tool: GitHubTool) -> None:
        mock_proc = _mock_process('{"number":1,"title":"Bug","body":"details","state":"OPEN"}')
        with patch(_GH_SUBPROCESS, return_value=mock_proc):
            result = await tool.execute(
                "issue_view", "/tmp", repo="owner/repo", number=1
            )
        assert result.success is True
        assert "Bug" in result.output


class TestGitHubToolPRs:
    @pytest.mark.asyncio
    async def test_pr_list(self, tool: GitHubTool) -> None:
        mock_proc = _mock_process('[{"number":10,"title":"Fix","state":"OPEN"}]')
        with patch(_GH_SUBPROCESS, return_value=mock_proc):
            result = await tool.execute("pr_list", "/tmp", repo="owner/repo")
        assert result.success is True
        assert "Fix" in result.output

    @pytest.mark.asyncio
    async def test_pr_view(self, tool: GitHubTool) -> None:
        mock_proc = _mock_process('{"number":10,"title":"Fix","body":"desc","state":"MERGED"}')
        with patch(_GH_SUBPROCESS, return_value=mock_proc):
            result = await tool.execute(
                "pr_view", "/tmp", repo="owner/repo", number=10
            )
        assert result.success is True
        assert "Fix" in result.output

    @pytest.mark.asyncio
    async def test_pr_create(self, tool: GitHubTool) -> None:
        mock_proc = _mock_process("https://github.com/owner/repo/pull/11")
        with patch(_GH_SUBPROCESS, return_value=mock_proc):
            result = await tool.execute(
                "pr_create",
                "/tmp",
                repo="owner/repo",
                title="New PR",
                body="Description",
            )
        assert result.success is True
        assert "pull/11" in result.output

    @pytest.mark.asyncio
    async def test_pr_create_missing_title(self, tool: GitHubTool) -> None:
        result = await tool.execute("pr_create", "/tmp", repo="owner/repo")
        assert result.success is False
        assert result.error == "title is required"

    @pytest.mark.asyncio
    async def test_pr_merge_blocked(self, tool: GitHubTool) -> None:
        result = await tool.execute("pr_merge", "/tmp", repo="owner/repo", number=1)
        assert result.success is False
        assert "blocked" in (result.error or "").lower()


class TestGitHubToolCI:
    @pytest.mark.asyncio
    async def test_ci_status(self, tool: GitHubTool) -> None:
        mock_proc = _mock_process('[{"status":"completed","conclusion":"success","name":"test"}]')
        with patch(_GH_SUBPROCESS, return_value=mock_proc):
            result = await tool.execute("ci_status", "/tmp", repo="owner/repo")
        assert result.success is True
        assert "success" in result.output


class TestGitHubToolErrors:
    @pytest.mark.asyncio
    async def test_gh_cli_failure(self, tool: GitHubTool) -> None:
        mock_proc = _mock_process("", "not authenticated", 1)
        with patch(_GH_SUBPROCESS, return_value=mock_proc):
            result = await tool.execute("issue_list", "/tmp", repo="owner/repo")
        assert result.success is False
        assert result.exit_code == 1
        assert result.error == "not authenticated"
