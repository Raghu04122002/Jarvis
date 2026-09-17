"""Tests for ToolRegistry."""

import pytest

from jarvis.models.approval import RiskLevel
from jarvis.tools.base import BaseTool, ToolResult
from jarvis.tools.registry import ToolNotFoundError, ToolRegistry


class FakeTool(BaseTool):
    def __init__(self, tool_name: str = "fake") -> None:
        self._name = tool_name

    @property
    def name(self) -> str:
        return self._name

    def operations(self) -> dict[str, RiskLevel]:
        return {"op": RiskLevel.SAFE}

    async def execute(
        self, operation: str, working_dir: str, **kwargs: str | int | list[str]
    ) -> ToolResult:
        return ToolResult(success=True, output="ok")


class TestToolRegistry:
    def test_register_and_get(self) -> None:
        reg = ToolRegistry()
        tool = FakeTool("mytool")
        reg.register(tool)
        assert reg.get("mytool") is tool

    def test_get_not_found(self) -> None:
        reg = ToolRegistry()
        with pytest.raises(ToolNotFoundError) as exc_info:
            reg.get("missing")
        assert exc_info.value.tool_name == "missing"

    def test_list_tools_empty(self) -> None:
        reg = ToolRegistry()
        assert reg.list_tools() == []

    def test_list_tools_sorted(self) -> None:
        reg = ToolRegistry()
        reg.register(FakeTool("zebra"))
        reg.register(FakeTool("alpha"))
        assert reg.list_tools() == ["alpha", "zebra"]

    def test_register_overwrites(self) -> None:
        reg = ToolRegistry()
        t1 = FakeTool("same")
        t2 = FakeTool("same")
        reg.register(t1)
        reg.register(t2)
        assert reg.get("same") is t2
        assert reg.list_tools() == ["same"]
