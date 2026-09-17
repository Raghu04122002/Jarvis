"""Secrets vault — resolves secret references without exposing values.

Secrets are accessed by name. The vault resolves them from environment variables.
Values are never logged, never included in API responses, and never sent to LLM context.
"""

import logging
import os

logger = logging.getLogger(__name__)


class SecretNotFoundError(Exception):
    """Raised when a requested secret is not available."""


class SecretsVault:
    """Resolves secret references to values from environment variables.

    Usage:
        vault = SecretsVault()
        token = vault.get("GITHUB_TOKEN")
    """

    def get(self, name: str) -> str:
        """Retrieve a secret by name.

        Looks up the environment variable with the given name.
        Logs the lookup (but never the value).

        Raises:
            SecretNotFoundError: if the secret is not set.
        """
        value = os.environ.get(name)
        if value is None:
            logger.warning("Secret not found: %s", name)
            raise SecretNotFoundError(f"Secret {name!r} is not configured")
        logger.debug("Secret resolved: %s", name)
        return value

    def has(self, name: str) -> bool:
        """Check if a secret is available without retrieving it."""
        return name in os.environ

    def __repr__(self) -> str:
        return "SecretsVault()"
