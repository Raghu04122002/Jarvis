"""Tests for CORS middleware configuration."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_cors_allows_localhost_1420(client: AsyncClient) -> None:
    """CORS allows requests from Vite dev server."""
    resp = await client.options(
        "/health",
        headers={
            "Origin": "http://localhost:1420",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == "http://localhost:1420"


@pytest.mark.asyncio
async def test_cors_allows_tauri_origin(client: AsyncClient) -> None:
    """CORS allows requests from Tauri production."""
    resp = await client.options(
        "/health",
        headers={
            "Origin": "tauri://localhost",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == "tauri://localhost"


@pytest.mark.asyncio
async def test_cors_rejects_unknown_origin(client: AsyncClient) -> None:
    """CORS rejects requests from unknown origins."""
    resp = await client.options(
        "/health",
        headers={
            "Origin": "http://evil.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert "access-control-allow-origin" not in resp.headers
