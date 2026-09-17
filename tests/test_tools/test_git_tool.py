"""Tests for GitTool — uses real temporary git repos."""

import subprocess
from pathlib import Path

import pytest

from jarvis.models.approval import RiskLevel
from jarvis.tools.base import InvalidOperationError
from jarvis.tools.git_tool import GitTool, NotAGitRepoError


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """Create a real git repo with one commit."""
    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=str(tmp_path),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=str(tmp_path),
        check=True,
        capture_output=True,
    )
    (tmp_path / "README.md").write_text("# Test\n")
    subprocess.run(
        ["git", "add", "README.md"],
        cwd=str(tmp_path),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=str(tmp_path),
        check=True,
        capture_output=True,
    )
    return tmp_path


@pytest.fixture
def tool() -> GitTool:
    return GitTool()


class TestGitToolMeta:
    def test_name(self, tool: GitTool) -> None:
        assert tool.name == "git"

    def test_operations_keys(self, tool: GitTool) -> None:
        ops = tool.operations()
        assert "status" in ops
        assert "diff" in ops
        assert "log" in ops
        assert "branch_list" in ops
        assert "current_branch" in ops
        assert "checkout" in ops
        assert "create_branch" in ops
        assert "commit" in ops
        assert "push" in ops

    def test_safe_operations(self, tool: GitTool) -> None:
        ops = tool.operations()
        for op in ("status", "diff", "log", "branch_list", "current_branch"):
            assert ops[op] == RiskLevel.SAFE

    def test_approval_operations(self, tool: GitTool) -> None:
        ops = tool.operations()
        for op in ("checkout", "create_branch", "commit", "push"):
            assert ops[op] == RiskLevel.REQUIRES_APPROVAL


class TestGitToolValidation:
    @pytest.mark.asyncio
    async def test_nonexistent_path(self, tool: GitTool) -> None:
        with pytest.raises(NotAGitRepoError):
            await tool.execute("status", "/nonexistent/path/abc123")

    @pytest.mark.asyncio
    async def test_not_a_repo(self, tool: GitTool, tmp_path: Path) -> None:
        with pytest.raises(NotAGitRepoError):
            await tool.execute("status", str(tmp_path))

    @pytest.mark.asyncio
    async def test_invalid_operation(self, tool: GitTool, git_repo: Path) -> None:
        with pytest.raises(InvalidOperationError):
            await tool.execute("destroy_everything", str(git_repo))


class TestGitToolSafeOps:
    @pytest.mark.asyncio
    async def test_status_clean(self, tool: GitTool, git_repo: Path) -> None:
        result = await tool.execute("status", str(git_repo))
        assert result.success is True
        assert result.output == ""  # clean repo

    @pytest.mark.asyncio
    async def test_status_dirty(self, tool: GitTool, git_repo: Path) -> None:
        (git_repo / "new.txt").write_text("hello")
        result = await tool.execute("status", str(git_repo))
        assert result.success is True
        assert "new.txt" in result.output

    @pytest.mark.asyncio
    async def test_diff_clean(self, tool: GitTool, git_repo: Path) -> None:
        result = await tool.execute("diff", str(git_repo))
        assert result.success is True

    @pytest.mark.asyncio
    async def test_diff_with_changes(self, tool: GitTool, git_repo: Path) -> None:
        (git_repo / "README.md").write_text("# Changed\n")
        result = await tool.execute("diff", str(git_repo))
        assert result.success is True
        assert "Changed" in result.output

    @pytest.mark.asyncio
    async def test_log(self, tool: GitTool, git_repo: Path) -> None:
        result = await tool.execute("log", str(git_repo))
        assert result.success is True
        assert "Initial commit" in result.output

    @pytest.mark.asyncio
    async def test_log_with_limit(self, tool: GitTool, git_repo: Path) -> None:
        result = await tool.execute("log", str(git_repo), limit=1)
        assert result.success is True
        assert result.output.count("\n") == 0  # single line

    @pytest.mark.asyncio
    async def test_branch_list(self, tool: GitTool, git_repo: Path) -> None:
        result = await tool.execute("branch_list", str(git_repo))
        assert result.success is True
        # Should show the default branch
        assert result.output.strip() != ""

    @pytest.mark.asyncio
    async def test_current_branch(self, tool: GitTool, git_repo: Path) -> None:
        result = await tool.execute("current_branch", str(git_repo))
        assert result.success is True
        assert result.output.strip() != ""


class TestGitToolApprovalOps:
    @pytest.mark.asyncio
    async def test_create_branch(self, tool: GitTool, git_repo: Path) -> None:
        result = await tool.execute(
            "create_branch", str(git_repo), branch="feature/test"
        )
        assert result.success is True
        # Verify we're on the new branch
        br = await tool.execute("current_branch", str(git_repo))
        assert br.output == "feature/test"

    @pytest.mark.asyncio
    async def test_checkout(self, tool: GitTool, git_repo: Path) -> None:
        # Create a branch, switch back, then checkout
        await tool.execute("create_branch", str(git_repo), branch="other")
        subprocess.run(
            ["git", "checkout", "-"],
            cwd=str(git_repo),
            check=True,
            capture_output=True,
        )
        result = await tool.execute("checkout", str(git_repo), branch="other")
        assert result.success is True

    @pytest.mark.asyncio
    async def test_commit(self, tool: GitTool, git_repo: Path) -> None:
        (git_repo / "new.txt").write_text("content")
        result = await tool.execute(
            "commit",
            str(git_repo),
            files=["new.txt"],
            message="Add new file",
        )
        assert result.success is True

    @pytest.mark.asyncio
    async def test_commit_missing_message(self, tool: GitTool, git_repo: Path) -> None:
        result = await tool.execute("commit", str(git_repo), files=["x.txt"])
        assert result.success is False
        assert result.error == "message is required"

    @pytest.mark.asyncio
    async def test_commit_missing_files(self, tool: GitTool, git_repo: Path) -> None:
        result = await tool.execute(
            "commit", str(git_repo), message="msg"
        )
        assert result.success is False
        assert result.error == "files list is required"

    @pytest.mark.asyncio
    async def test_checkout_missing_branch(
        self, tool: GitTool, git_repo: Path
    ) -> None:
        result = await tool.execute("checkout", str(git_repo))
        assert result.success is False
        assert result.error == "branch is required"

    @pytest.mark.asyncio
    async def test_create_branch_missing_branch(
        self, tool: GitTool, git_repo: Path
    ) -> None:
        result = await tool.execute("create_branch", str(git_repo))
        assert result.success is False
        assert result.error == "branch is required"

    @pytest.mark.asyncio
    async def test_push_set_upstream_missing_branch(
        self, tool: GitTool, git_repo: Path
    ) -> None:
        result = await tool.execute(
            "push", str(git_repo), set_upstream="true"
        )
        assert result.success is False
        assert "branch is required" in (result.error or "")
