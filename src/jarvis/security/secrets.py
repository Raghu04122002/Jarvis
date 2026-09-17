"""Secret filtering utilities to prevent leaking sensitive data."""

import re

# Compiled patterns for detecting sensitive data
SENSITIVE_PATTERNS: list[re.Pattern[str]] = [
    # Generic API keys (key=..., api_key=..., apikey=...)
    re.compile(r"(?i)(?:api[_-]?key|api[_-]?secret)\s*[=:]\s*\S+"),
    # Bearer tokens
    re.compile(r"(?i)bearer\s+[a-zA-Z0-9\-._~+/]+=*"),
    # AWS access keys (AKIA...)
    re.compile(r"AKIA[0-9A-Z]{16}"),
    # AWS secret keys (40 chars of base64-ish)
    re.compile(r"(?i)aws[_-]?secret[_-]?access[_-]?key\s*[=:]\s*\S+"),
    # GitHub tokens (ghp_, gho_, ghs_, ghr_, github_pat_)
    re.compile(r"(?:ghp|gho|ghs|ghr)_[A-Za-z0-9_]{36,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{22,}"),
    # Generic password patterns
    re.compile(r"(?i)(?:password|passwd|pwd)\s*[=:]\s*\S+"),
    # Generic secret/token patterns
    re.compile(r"(?i)(?:secret|token)\s*[=:]\s*\S+"),
    # Private keys
    re.compile(r"-----BEGIN\s+(?:RSA\s+)?PRIVATE\s+KEY-----"),
    # Slack tokens
    re.compile(r"xox[bporas]-[0-9a-zA-Z-]+"),
]

_REDACTED = "[REDACTED]"


def contains_secrets(text: str) -> bool:
    """Return True if any sensitive patterns are found in text."""
    for pattern in SENSITIVE_PATTERNS:
        if pattern.search(text):
            return True
    return False


def filter_secrets(text: str) -> str:
    """Replace sensitive patterns in text with [REDACTED]."""
    result = text
    for pattern in SENSITIVE_PATTERNS:
        result = pattern.sub(_REDACTED, result)
    return result
