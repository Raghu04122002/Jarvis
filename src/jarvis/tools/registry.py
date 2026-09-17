"""Tool registry for looking up tools by name."""

from jarvis.tools.base import BaseTool, ToolError


class ToolNotFoundError(ToolError):
    """Raised when a tool is not found in the registry."""

    def __init__(self, name: str) -> None:
        self.tool_name = name
        super().__init__(f"Tool not found: '{name}'")


class ToolRegistry:
    """Registry of available tools, keyed by name."""

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """Register a tool by its name."""
        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool:
        """Look up a tool by name. Raises ToolNotFoundError if not found."""
        try:
            return self._tools[name]
        except KeyError:
            raise ToolNotFoundError(name)

    def list_tools(self) -> list[str]:
        """Return sorted list of registered tool names."""
        return sorted(self._tools.keys())
