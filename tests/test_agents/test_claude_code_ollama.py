"""Tests for routing the Claude Code agent to Ollama."""

from unittest.mock import patch

import pytest

from jarvis.agents.claude_code import ClaudeCodeAgent
from jarvis.agents.registry import claude_code_backend, create_default_registry
from jarvis.config import AgentsConfig


def test_anthropic_default_has_no_overrides() -> None:
    model, env = claude_code_backend(AgentsConfig())
    assert model is None
    assert env == {}


def test_anthropic_model_override() -> None:
    model, env = claude_code_backend(AgentsConfig(claude_code_model="opus"))
    assert model == "opus"
    assert env == {}


def test_ollama_routes_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OLLAMA_API_KEY", "k")
    cfg = AgentsConfig(claude_code_provider="ollama", ollama_base_url="https://ollama.com/")
    model, env = claude_code_backend(cfg)
    assert model == "gpt-oss:120b"
    assert env["ANTHROPIC_BASE_URL"] == "https://ollama.com"
    assert env["ANTHROPIC_AUTH_TOKEN"] == "k"
    assert env["ANTHROPIC_API_KEY"] == ""
    assert env["ANTHROPIC_DEFAULT_HAIKU_MODEL"] == "gpt-oss:20b"
    assert env["CLAUDE_CODE_AUTO_COMPACT_WINDOW"] == "128000"


def test_explicit_key_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OLLAMA_API_KEY", "env")
    cfg = AgentsConfig(claude_code_provider="ollama", ollama_api_key="cfg")
    assert claude_code_backend(cfg)[1]["ANTHROPIC_AUTH_TOKEN"] == "cfg"


def test_agent_applies_model_and_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "real-anthropic-key")
    monkeypatch.setenv("OLLAMA_API_KEY", "k")
    cfg = AgentsConfig(claude_code_provider="ollama")
    with patch("jarvis.agents.claude_code.shutil.which", return_value="/usr/bin/claude"):
        agent = create_default_registry().create("claude_code", cfg)
    assert isinstance(agent, ClaudeCodeAgent)
    assert agent._command("do it") == [
        "/usr/bin/claude", "--print", "--model", "gpt-oss:120b", "-p", "do it",
    ]
    env = agent._sanitized_env()
    assert env["ANTHROPIC_API_KEY"] == ""  # real key not leaked to Ollama
    assert env["ANTHROPIC_BASE_URL"] == "https://ollama.com"


def test_agent_command_without_model() -> None:
    with patch("jarvis.agents.claude_code.shutil.which", return_value="/usr/bin/claude"):
        agent = ClaudeCodeAgent()
    assert agent._command("x") == ["/usr/bin/claude", "--print", "-p", "x"]
