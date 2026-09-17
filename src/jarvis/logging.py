"""Structured logging setup for Jarvis.

Provides consistent log formatting with timestamps, levels, and module names.
Never logs secrets, API keys, passwords, or tokens.
"""

import logging
import sys

from jarvis.config import LoggingConfig

_CONFIGURED = False

# Fields that should never appear in logs
_REDACTED_FIELDS = frozenset(
    {
        "password",
        "secret",
        "token",
        "api_key",
        "apikey",
        "access_token",
        "refresh_token",
        "credential",
        "private_key",
    }
)


def is_sensitive_key(key: str) -> bool:
    """Check if a key name looks like it holds sensitive data."""
    return key.lower().replace("-", "_") in _REDACTED_FIELDS


def setup_logging(config: LoggingConfig) -> None:
    """Configure the root logger based on Jarvis config."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    level = getattr(logging, config.level.upper(), logging.INFO)

    if config.format == "json":
        fmt = (
            '{"timestamp":"%(asctime)s","level":"%(levelname)s",'
            '"module":"%(name)s","message":"%(message)s"}'
        )
    else:
        fmt = "%(asctime)s [%(levelname)-8s] %(name)s: %(message)s"

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(fmt, datefmt="%Y-%m-%dT%H:%M:%S"))

    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(handler)

    # Quiet noisy libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    _CONFIGURED = True


def reset_logging() -> None:
    """Reset logging state. Used in tests."""
    global _CONFIGURED
    _CONFIGURED = False
