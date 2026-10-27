"""Planner abstraction and basic deterministic implementation.

The planner converts a user request into a structured execution plan.
Designed so a real LLM-powered planner can be swapped in later.
"""

import abc
import re
from dataclasses import dataclass

MAX_TITLE_WORDS = 8
MAX_TITLE_CHARS = 60

# Conversational lead-ins that add nothing to a task title.
_LEAD_IN = re.compile(
    r"^(?:(?:hey|hi|ok(?:ay)?|so|jarvis)[,!.\s]+)*"
    r"(?:(?:can|could|would|will)\s+you\s+(?:please\s+)?|please(?:\s+|$)|i\s+(?:want|need)\s+(?:you\s+)?to\s+"
    r"|i'?d\s+like\s+(?:you\s+)?to\s+|let'?s\s+)?",
    re.IGNORECASE,
)


def short_title(request: str) -> str:
    """Turn a raw request into a short task title (max 8 words, 60 chars).

    Takes the first line/sentence, drops polite lead-ins ("can you please"),
    and capitalises the first letter. Long text is cut on a word boundary.
    """
    text = request.strip().splitlines()[0] if request.strip() else ""
    text = re.split(r"(?<=[.!?])\s", text, maxsplit=1)[0]
    text = _LEAD_IN.sub("", text).strip().rstrip(".!?,;:")
    if not text:
        return "Untitled task"
    words = text.split()
    cut = len(words) > MAX_TITLE_WORDS
    text = " ".join(words[:MAX_TITLE_WORDS])
    if len(text) > MAX_TITLE_CHARS:
        text = text[: MAX_TITLE_CHARS - 1].rsplit(" ", 1)[0] or text[: MAX_TITLE_CHARS - 1]
        cut = True
    text = text[0].upper() + text[1:]
    return text + "…" if cut else text


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
        title = short_title(request)

        steps = [
            "Understand and analyze the request",
            "Identify the relevant project and context",
            "Inspect the relevant code or resources",
            "Implement the required changes",
            "Run tests and verify the result",
            "Report the outcome",
        ]

        return Plan(title=title, steps=steps)
