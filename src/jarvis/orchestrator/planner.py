"""Planner abstraction and basic deterministic implementation.

The planner converts a user request into a structured execution plan.
Designed so a real LLM-powered planner can be swapped in later.
"""

import abc
from dataclasses import dataclass


@dataclass(frozen=True)
class Plan:
    """A structured execution plan for a task."""

    title: str
    steps: list[str]


class BasePlanner(abc.ABC):
    """Abstract planner interface."""

    @abc.abstractmethod
    def create_plan(self, request: str, context: dict[str, str] | None = None) -> Plan:
        """Generate an execution plan from a user request.

        Args:
            request: The natural-language user request.
            context: Optional context (project info, etc.).

        Returns:
            A structured Plan with title and steps.
        """


class BasicPlanner(BasePlanner):
    """Deterministic planner that produces a generic plan structure.

    This is a placeholder until an LLM-powered planner is integrated.
    It generates sensible default steps for any request.
    """

    def create_plan(self, request: str, context: dict[str, str] | None = None) -> Plan:
        # Derive a concise title from the request
        title = request.strip()
        if len(title) > 100:
            title = title[:97] + "..."

        steps = [
            "Understand and analyze the request",
            "Identify the relevant project and context",
            "Inspect the relevant code or resources",
            "Implement the required changes",
            "Run tests and verify the result",
            "Report the outcome",
        ]

        return Plan(title=title, steps=steps)
