"""Runtime settings endpoints used by the desktop Settings page."""

from __future__ import annotations

import time
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from jarvis.api.dependencies import get_ai_service, get_settings_service
from jarvis.services.ai_service import AIServiceError
from jarvis.services.chat_tools import make_search_backend
from jarvis.services.settings_service import SettingsUpdate, SettingsView

router = APIRouter(tags=["settings"])


class CheckResult(BaseModel):
    ok: bool
    detail: str
    latency_ms: int | None = None


class ConnectionTestResponse(BaseModel):
    provider: Literal["anthropic", "ollama"]
    model: str
    ai: CheckResult
    web_search: CheckResult | None = None


@router.get("/settings")
async def get_settings() -> SettingsView:
    return get_settings_service().view()


@router.patch("/settings")
async def update_settings(patch: SettingsUpdate) -> SettingsView:
    try:
        return get_settings_service().update(patch)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@router.post("/settings/test")
async def test_connection() -> ConnectionTestResponse:
    """Make one tiny real call to the model (and the search backend, if any)."""
    ai = get_ai_service()
    cfg = get_settings_service().effective_ai_config()

    start = time.monotonic()
    if not ai.available:
        ai_result = CheckResult(ok=False, detail=f"No API key set for {ai.provider}.")
    else:
        try:
            reply = await ai.complete("Reply with exactly: OK", "ping")
            ai_result = CheckResult(
                ok=True,
                detail=f"Replied: {reply.strip()[:60] or '(empty)'}",
                latency_ms=int((time.monotonic() - start) * 1000),
            )
        except AIServiceError as e:
            ai_result = CheckResult(ok=False, detail=str(e))

    search_result: CheckResult | None = None
    backend = make_search_backend(cfg.web_search_provider, cfg.ollama_api_key)
    if backend is not None:
        start = time.monotonic()
        try:
            hits = await backend.search("weather", 1)
            search_result = CheckResult(
                ok=bool(hits),
                detail=f"{backend.name}: {len(hits)} result(s)",
                latency_ms=int((time.monotonic() - start) * 1000),
            )
        except Exception as e:  # noqa: BLE001 - report any backend failure to the user
            search_result = CheckResult(ok=False, detail=f"{backend.name}: {e}")

    return ConnectionTestResponse(
        provider=ai.provider,  # type: ignore[arg-type]
        model=ai.model,
        ai=ai_result,
        web_search=search_result,
    )
