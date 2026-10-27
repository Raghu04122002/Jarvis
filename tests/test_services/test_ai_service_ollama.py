"""Tests for the Ollama provider in AIService."""

import json
from typing import Any

import httpx
import pytest

from jarvis.config import AIConfig
from jarvis.services import ai_service as ai_module
from jarvis.services.ai_service import AIService


@pytest.fixture(autouse=True)
def _no_env_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OLLAMA_API_KEY", raising=False)


def _patch_transport(monkeypatch: pytest.MonkeyPatch, handler: Any) -> list[httpx.Request]:
    """Route AIService's httpx.AsyncClient through a MockTransport."""
    seen: list[httpx.Request] = []
    real_client = httpx.AsyncClient

    def recording(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    def factory(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        kwargs["transport"] = httpx.MockTransport(recording)
        return real_client(*args, **kwargs)

    monkeypatch.setattr(ai_module.httpx, "AsyncClient", factory)
    return seen


def _ollama_cfg(**kw: Any) -> AIConfig:
    return AIConfig(provider="ollama", pxpipe_enabled=False, **kw)


def test_unavailable_without_key_for_cloud() -> None:
    svc = AIService(_ollama_cfg())
    assert svc.provider == "ollama"
    assert not svc.available


def test_key_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OLLAMA_API_KEY", "env-key")
    assert AIService(_ollama_cfg()).available


def test_local_daemon_needs_no_key() -> None:
    svc = AIService(_ollama_cfg(ollama_base_url="http://localhost:11434"))
    assert svc.available


async def test_chat_not_configured_message() -> None:
    reply = await AIService(_ollama_cfg()).chat("hi")
    assert "OLLAMA_API_KEY" in reply


async def test_chat_success(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _patch_transport(
        monkeypatch,
        lambda req: httpx.Response(
            200, json={"message": {"role": "assistant", "content": " Hello! "}, "done": True}
        ),
    )
    svc = AIService(_ollama_cfg(ollama_api_key="k", ollama_model="gpt-oss:120b"))
    reply = await svc.chat("hi", context="Current project: Jarvis")

    assert reply == "Hello!"
    req = seen[0]
    assert str(req.url) == "https://ollama.com/api/chat"
    assert req.headers["Authorization"] == "Bearer k"
    body = json.loads(req.content)
    assert body["model"] == "gpt-oss:120b"
    assert body["stream"] is False
    assert body["messages"][0]["role"] == "system"
    assert "Current project: Jarvis" in body["messages"][0]["content"]
    assert body["messages"][1] == {"role": "user", "content": "hi"}


async def test_chat_auth_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_transport(monkeypatch, lambda req: httpx.Response(401, json={"error": "unauthorized"}))
    reply = await AIService(_ollama_cfg(ollama_api_key="bad")).chat("hi")
    assert "OLLAMA_API_KEY" in reply


async def test_chat_api_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_transport(
        monkeypatch, lambda req: httpx.Response(404, json={"error": "model not found"})
    )
    reply = await AIService(_ollama_cfg(ollama_api_key="k")).chat("hi")
    assert reply == "AI service error: model not found"


async def test_chat_connection_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=req)

    _patch_transport(monkeypatch, boom)
    reply = await AIService(_ollama_cfg(ollama_api_key="k")).chat("hi")
    assert "Could not connect" in reply


def test_anthropic_remains_default() -> None:
    assert AIConfig().provider == "anthropic"


async def test_chat_rate_limited(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_transport(monkeypatch, lambda req: httpx.Response(429, json={"error": "limit"}))
    reply = await AIService(_ollama_cfg(ollama_api_key="k")).chat("hi")
    assert "usage limit" in reply


async def test_chat_needs_credits(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_transport(
        monkeypatch,
        lambda req: httpx.Response(402, json={"error": "Add usage credits to use cloud models"}),
    )
    reply = await AIService(_ollama_cfg(ollama_api_key="k")).chat("hi")
    assert "Add usage credits" in reply


@pytest.mark.parametrize(
    ("think", "expected"),
    [("low", "low"), ("true", True), ("false", False), ("", None)],
)
async def test_think_field(
    monkeypatch: pytest.MonkeyPatch, think: str, expected: object
) -> None:
    seen = _patch_transport(
        monkeypatch, lambda req: httpx.Response(200, json={"message": {"content": "ok"}})
    )
    await AIService(_ollama_cfg(ollama_api_key="k", ollama_think=think)).chat("hi")
    body = json.loads(seen[0].content)
    assert body.get("think") == expected


def test_load_dotenv_does_not_override_existing(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from jarvis.config import _load_dotenv

    env = tmp_path / ".env"
    env.write_text("# comment\nJARVIS_T_A=from_file\nexport JARVIS_T_B='quoted'\n")
    monkeypatch.setenv("JARVIS_T_A", "already_set")
    monkeypatch.delenv("JARVIS_T_B", raising=False)
    _load_dotenv(env)
    import os

    assert os.environ["JARVIS_T_A"] == "already_set"
    assert os.environ["JARVIS_T_B"] == "quoted"
    monkeypatch.delenv("JARVIS_T_B")
