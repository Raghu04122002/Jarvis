"""Tests for the /health endpoint."""

import pytest
from httpx import AsyncClient

from jarvis import __version__


@pytest.mark.asyncio
async def test_health_returns_ok(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "jarvis"
    assert data["version"] == __version__
    assert "timestamp" in data


@pytest.mark.asyncio
async def test_health_returns_valid_timestamp(client: AsyncClient) -> None:
    from datetime import datetime

    response = await client.get("/health")
    data = response.json()
    # Should parse without error
    datetime.fromisoformat(data["timestamp"])
