"""Tool base class and shared types."""

import abc
from dataclasses import dataclass

from jarvis.models.approval import RiskLevel


class ToolError(Exception):
    """Base exception for tool errors."""


class InvalidOperationError(ToolError):
    """Raised when an unknown operation is requested."""

    def __init__(self, tool_name: str, operation: str) -> None:
        self.tool_name = tool_name
        self.operation = operation
        super().__init__(
            f"Invalid operation '{operation}' for tool '{tool_name}'"
        )


@dataclass(frozen=True)
class ToolResult:
    """Result of a tool execution."""

    success: bool
    output: str
    error: str | None = None
    exit_code: int = 0


class BaseTool(abc.ABC):
    """Abstract base class for all tools."""

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Unique tool name."""

    @abc.abstractmethod
    def operations(self) -> dict[str, RiskLevel]:
        """Map operation names to their risk levels."""

    @abc.abstractmethod
    async def execute(
        self, operation: str, working_dir: str, **kwargs: str | int | list[str]
    ) -> ToolResult:
        """Execute a tool operation.

        Subclasses should validate the operation and dispatch to the
        appropriate method.
        """

    def risk_level_for(self, operation: str) -> RiskLevel:
        """Return the risk level for a given operation."""
        ops = self.operations()
        if operation not in ops:
            raise InvalidOperationError(self.name, operation)
        return ops[operation]
