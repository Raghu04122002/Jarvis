"""Deterministic intent classifier for user messages.

Classifies messages into QUERY, WORKFLOW, or ACTION intents
using regex patterns and keyword matching — no LLM required.
"""

import enum
import re
from dataclasses import dataclass


class IntentType(enum.StrEnum):
    QUERY = "query"
    WORKFLOW = "workflow"
    ACTION = "action"


@dataclass(frozen=True)
class IntentResult:
    intent: IntentType
    project_hint: str | None = None
    issue_number: int | None = None
    confidence: str = "high"


# --- Extraction patterns ---

_ISSUE_PATTERN = re.compile(r"(?:issue|bug|ticket|pr)?\s*#(\d+)|issue\s+(\d+)", re.IGNORECASE)

_PROJECT_HINT_PATTERN = re.compile(
    r"(?:test|check|fix|run|build|deploy|inspect)\s+([A-Za-z]\w+)", re.IGNORECASE
)

# --- Query patterns ---

_QUERY_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\bmy projects?\b",
        r"\bwhat(?:'s| is) broken\b",
        r"\bstatus\b",
        r"\bopen issues?\b",
        r"\bci status\b",
        r"\blist (?:all )?(?:tasks?|projects?)\b",
        r"\bshow (?:me )?(?:tasks?|projects?)\b",
        r"\bhow many\b",
        r"\bwhat(?:'s| is) (?:the )?(?:status|progress)\b",
        r"\bwhat can you do\b",
        r"\bwhat do you do\b",
        r"\bwho are you\b",
        r"\bhelp\b",
    ]
]

# Short conversational messages that should not create tasks
_GREETING_PATTERN = re.compile(
    r"^(?:hi|hello|hey|yo|sup|howdy|greetings|thanks|thank you|ok|okay|bye|goodbye|good\s+(?:morning|afternoon|evening|night))[\s!?.]*$",
    re.IGNORECASE,
)

# --- Workflow keywords ---

# --- Action keywords — message must contain one to be classified as ACTION ---

_ACTION_KEYWORDS: frozenset[str] = frozenset(
    {
        "add",
        "create",
        "build",
        "deploy",
        "run",
        "test",
        "update",
        "delete",
        "remove",
        "refactor",
        "rename",
        "move",
        "migrate",
        "install",
        "setup",
        "set up",
        "configure",
        "enable",
        "disable",
        "write",
        "generate",
        "change",
        "modify",
        "push",
        "merge",
        "revert",
        "upgrade",
        "downgrade",
        "scaffold",
        "init",
        "initialize",
        "publish",
        "release",
        "ship",
        "debug",
        "profile",
        "optimize",
        "lint",
        "format",
        # Also includes workflow verbs (they are actions when no issue number)
        "fix",
        "resolve",
        "handle",
        "implement",
        "close",
        "address",
    }
)

_ACTION_PATTERN = re.compile(
    r"^(?:please\s+|can you\s+|could you\s+)?("
    + "|".join(re.escape(kw) for kw in sorted(_ACTION_KEYWORDS, key=len, reverse=True))
    + r")\b",
    re.IGNORECASE,
)

# --- Workflow keywords ---

_WORKFLOW_KEYWORDS: frozenset[str] = frozenset(
    {
        "fix",
        "resolve",
        "handle",
        "take care of",
        "work on",
        "implement",
        "close",
        "address",
    }
)


def _extract_issue_number(message: str) -> int | None:
    """Extract an issue number from the message."""
    match = _ISSUE_PATTERN.search(message)
    if match:
        return int(match.group(1) or match.group(2))
    return None


def _extract_project_hint(message: str) -> str | None:
    """Extract a project name hint from the message."""
    match = _PROJECT_HINT_PATTERN.search(message)
    if match:
        return match.group(1)
    return None


def _is_query(message: str) -> bool:
    """Check if the message matches any query pattern."""
    return any(p.search(message) for p in _QUERY_PATTERNS)


def _has_workflow_keyword(message: str) -> bool:
    """Check if the message contains a workflow keyword before an issue reference."""
    lower = message.lower()
    return any(kw in lower for kw in _WORKFLOW_KEYWORDS)


def _has_action_keyword(message: str) -> bool:
    """Check if the message contains an action keyword indicating a task should be created."""
    lower = message.lower()
    # Check for action keywords anywhere in the message
    return any(re.search(r"\b" + re.escape(kw) + r"\b", lower) for kw in _ACTION_KEYWORDS)


def classify(message: str) -> IntentResult:
    """Classify a user message into an intent.

    Classification order:
    1. QUERY — greetings, known query patterns, or no action keywords
    2. WORKFLOW — contains issue number + workflow keyword
    3. ACTION — contains action keywords (create task + dispatch agent)
    4. Fallback: QUERY — conversational messages answered directly
    """
    message = message.strip()
    if not message:
        return IntentResult(intent=IntentType.QUERY, confidence="low")

    issue_number = _extract_issue_number(message)
    project_hint = _extract_project_hint(message)

    # 0. Greetings / short conversational messages
    if _GREETING_PATTERN.match(message):
        return IntentResult(intent=IntentType.QUERY, confidence="high")

    # 1. Query detection
    if _is_query(message):
        return IntentResult(
            intent=IntentType.QUERY,
            project_hint=project_hint,
            issue_number=issue_number,
        )

    # 2. Workflow detection: issue number + workflow keyword
    if issue_number is not None and _has_workflow_keyword(message):
        return IntentResult(
            intent=IntentType.WORKFLOW,
            project_hint=project_hint,
            issue_number=issue_number,
        )

    # 3. ACTION — only if message contains action keywords
    if _has_action_keyword(message):
        return IntentResult(
            intent=IntentType.ACTION,
            project_hint=project_hint,
            issue_number=issue_number,
        )

    # 4. Fallback: QUERY — conversational/general messages answered directly
    return IntentResult(
        intent=IntentType.QUERY,
        project_hint=project_hint,
        issue_number=issue_number,
        confidence="medium",
    )
