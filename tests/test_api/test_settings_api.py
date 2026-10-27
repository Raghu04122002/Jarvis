"""Tests for the runtime settings API and SettingsService."""

import json
from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient

from jarvis.config import AIConfig
from jarvis.services.ai_service import AIService
from jarvis.services.settings_service import SettingsService, SettingsUpdate, mask


def test_mask_never_reveals_key() -> None:
    assert mask("").set is False
    m = mask("abcdefghijklmnop1234")
    assert m.set and m.hint == "1234"
    assert mask("short").hint == ""  # too short to show any of it


def test_update_persists_and_reconfigures(tmp_path: Path) -> None:
    ai = AIService(AIConfig(pxpipe_enabled=False))
    path = tmp_path / "settings.json"
    svc = SettingsService(AIConfig(pxpipe_enabled=False), ai, None, path=path)
    assert ai.provider == "anthropic" and not ai.available

    view = svc.update(
        SettingsUpdate(
            provider="ollama",
            ollama_model="gpt-oss:120b",
            keys={"ollama": "secret-ollama-key-9876"},
            persona="Be terse.",
        )
    )
    assert ai.provider == "ollama" and ai.model == "gpt-oss:120b" and ai.available
    assert view.keys["ollama"].set and view.keys["ollama"].hint == "9876"
    assert view.keys["ollama"].source == "settings"
    assert "secret-ollama-key-9876" not in view.model_dump_json()

    saved = json.loads(path.read_text())
    assert saved["provider"] == "ollama" and saved["persona"] == "Be terse."
    assert path.stat().st_mode & 0o077 == 0  # owner-only

    # A fresh service picks the file up again
    ai2 = AIService(AIConfig(pxpipe_enabled=False))
    svc2 = SettingsService(AIConfig(pxpipe_enabled=False), ai2, None, path=path)
    svc2.apply()
    assert ai2.provider == "ollama" and ai2.available

    # Empty string clears the stored key and falls back to config (none here)
    view = svc.update(SettingsUpdate(keys={"ollama": ""}))
    assert not view.keys["ollama"].set and not ai.available


def test_unknown_key_rejected(tmp_path: Path) -> None:
    svc = SettingsService(AIConfig(pxpipe_enabled=False), None, None, path=tmp_path / "s.json")
    with pytest.raises(ValueError):
        svc.update(SettingsUpdate(keys={"openai": "x"}))


@pytest.mark.asyncio
async def test_settings_endpoints(client: AsyncClient) -> None:
    resp = await client.get("/settings")
    assert resp.status_code == 200
    data = resp.json()
    assert data["provider"] == "anthropic"
    names = {t["name"] for t in data["tools"]}
    assert {"create_task", "list_tasks"} <= names
    assert all(t["enabled"] for t in data["tools"])

    resp = await client.patch(
        "/settings", json={"disabled_tools": ["list_tasks"], "persona": "Pirate voice."}
    )
    assert resp.status_code == 200
    tools: dict[str, Any] = {t["name"]: t for t in resp.json()["tools"]}
    assert tools["list_tasks"]["enabled"] is False
    assert resp.json()["persona"] == "Pirate voice."

    resp = await client.patch("/settings", json={"keys": {"nope": "x"}})
    assert resp.status_code == 422

    resp = await client.put("/settings", json={"persona": "Via PUT."})
    assert resp.status_code == 200
    assert resp.json()["persona"] == "Via PUT."

    resp = await client.post("/settings/test")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ai"]["ok"] is False  # no key configured in tests
    assert "No API key" in body["ai"]["detail"]


@pytest.mark.asyncio
async def test_disabled_tool_and_persona_reach_the_prompt(client: AsyncClient) -> None:
    from jarvis.api.dependencies import get_orchestrator

    await client.patch("/settings", json={"disabled_tools": ["list_tasks"], "persona": "Zebra"})
    orch = get_orchestrator()
    box = orch._chat_toolbox(None, None)  # type: ignore[arg-type]
    assert "list_tasks" not in box.names and "create_task" in box.names
    assert orch._persona == "Zebra"
