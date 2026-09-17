"""Tests for the secrets vault."""

import pytest

from jarvis.secrets.vault import SecretNotFoundError, SecretsVault


def test_get_existing_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEST_SECRET", "value123")
    vault = SecretsVault()
    assert vault.get("TEST_SECRET") == "value123"


def test_get_missing_secret() -> None:
    vault = SecretsVault()
    with pytest.raises(SecretNotFoundError):
        vault.get("DEFINITELY_NOT_SET_XYZZY")


def test_has_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEST_EXISTS", "yes")
    vault = SecretsVault()
    assert vault.has("TEST_EXISTS") is True
    assert vault.has("DEFINITELY_NOT_SET_XYZZY") is False
