"""Input validation utilities for security hardening."""

import re
from pathlib import Path

# Patterns that indicate shell injection attempts
_SHELL_INJECTION_PATTERNS = [
    re.compile(r";\s*\w"),  # semicolon followed by command
    re.compile(r"\|\s*\w"),  # pipe followed by command
    re.compile(r"&&\s*\w"),  # && followed by command
    re.compile(r"\|\|\s*\w"),  # || followed by command
    re.compile(r"`[^`]+`"),  # backtick command substitution
    re.compile(r"\$\([^)]+\)"),  # $() command substitution
]


class PathTraversalError(Exception):
    """Raised when a path attempts to escape allowed roots."""

    def __init__(self, path: str, reason: str = "") -> None:
        self.path = path
        msg = f"Path traversal blocked: {path!r}"
        if reason:
            msg += f" ({reason})"
        super().__init__(msg)


class ShellInjectionError(Exception):
    """Raised when shell injection patterns are detected in arguments."""

    def __init__(self, value: str) -> None:
        self.value = value
        super().__init__(f"Shell injection pattern detected in argument: {value!r}")


def validate_working_dir(working_dir: str, allowed_roots: list[str] | None = None) -> str:
    """Validate and resolve a working directory path.

    Returns the canonical (resolved) path. Raises PathTraversalError
    if the resolved path escapes allowed roots.
    """
    resolved = Path(working_dir).resolve()

    if not resolved.is_absolute():
        raise PathTraversalError(working_dir, "path is not absolute")

    if allowed_roots is not None:
        for root in allowed_roots:
            root_resolved = Path(root).resolve()
            try:
                resolved.relative_to(root_resolved)
                return str(resolved)
            except ValueError:
                continue
        raise PathTraversalError(
            working_dir,
            f"not under allowed roots: {allowed_roots}",
        )

    return str(resolved)


def is_path_safe(path: str, base_dir: str) -> bool:
    """Check if a resolved path stays within base_dir."""
    try:
        resolved = Path(path).resolve()
        base_resolved = Path(base_dir).resolve()
        resolved.relative_to(base_resolved)
        return True
    except ValueError:
        return False


def sanitize_tool_args(args: dict[str, object]) -> dict[str, object]:
    """Sanitize tool arguments by checking for shell injection patterns.

    Strips whitespace from string values and raises ShellInjectionError
    if dangerous patterns are detected.
    """
    sanitized: dict[str, object] = {}
    for key, value in args.items():
        if isinstance(value, str):
            stripped = value.strip()
            _check_shell_injection(stripped)
            sanitized[key] = stripped
        elif isinstance(value, list):
            clean_list: list[object] = []
            for item in value:
                if isinstance(item, str):
                    stripped_item = item.strip()
                    _check_shell_injection(stripped_item)
                    clean_list.append(stripped_item)
                else:
                    clean_list.append(item)
            sanitized[key] = clean_list
        else:
            sanitized[key] = value
    return sanitized


def _check_shell_injection(value: str) -> None:
    """Raise ShellInjectionError if value contains shell injection patterns."""
    for pattern in _SHELL_INJECTION_PATTERNS:
        if pattern.search(value):
            raise ShellInjectionError(value)
