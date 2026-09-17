"""Tests for tool base classes."""

import pytest

from jarvis.models.approval import RiskLevel
from jarvis.tools.base import BaseTool, InvalidOperationError, ToolResult


class DummyTool(BaseTool):
    """Concrete tool for testing."""

    @property
    def name(self) -> str:
        return "dummy"

    def operations(self) -> dict[str, RiskLevel]:
        return {
            "safe_op": RiskLevel.SAFE,
            "risky_op": RiskLevel.REQUIRES_APPROVAL,
        }

    async def execute(
        self, operation: str, working_dir: str, **kwargs: str | int | list[str]
    ) -> ToolResult:
        if operation not in self.operations():
            raise InvalidOperationError(self.name, operation)
        return ToolResult(success=True, output=f"executed {operation}")


class TestToolResult:
    def test_defaults(self) -> None:
        r = ToolResult(success=True, output="ok")
        assert r.success is True
        assert r.output == "ok"
        assert r.error is None
        assert r.exit_code == 0

    def test_with_error(self) -> None:
        r = ToolResult(success=False, output="", error="bad", exit_code=1)
        assert r.success is False
        assert r.error == "bad"
        assert r.exit_code == 1

    def test_frozen(self) -> None:
        r = ToolResult(success=True, output="ok")
        with pytest.raises(AttributeError):
            r.success = False  # type: ignore[misc]


class TestBaseTool:
    def test_name(self) -> None:
        t = DummyTool()
        assert t.name == "dummy"

    def test_operations(self) -> None:
        t = DummyTool()
        ops = t.operations()
        assert "safe_op" in ops
        assert ops["safe_op"] == RiskLevel.SAFE
        assert ops["risky_op"] == RiskLevel.REQUIRES_APPROVAL

    def test_risk_level_for_valid(self) -> None:
        t = DummyTool()
        assert t.risk_level_for("safe_op") == RiskLevel.SAFE

    def test_risk_level_for_invalid(self) -> None:
        t = DummyTool()
        with pytest.raises(InvalidOperationError) as exc_info:
            t.risk_level_for("nope")
        assert exc_info.value.tool_name == "dummy"
        assert exc_info.value.operation == "nope"

    @pytest.mark.asyncio
    async def test_execute(self) -> None:
        t = DummyTool()
        result = await t.execute("safe_op", "/tmp")
        assert result.success is True
        assert "safe_op" in result.output

    @pytest.mark.asyncio
    async def test_execute_invalid_operation(self) -> None:
        t = DummyTool()
        with pytest.raises(InvalidOperationError):
            await t.execute("nope", "/tmp")
