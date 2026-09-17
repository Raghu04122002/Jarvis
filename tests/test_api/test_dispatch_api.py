"""Tests for dispatch and executions API endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_dispatch_success(client: AsyncClient) -> None:
    """Dispatch a task that is in PLANNING status."""
    # Create a task via chat
    resp = await client.post("/chat", json={"message": "Fix login bug", "project_id": None})
    assert resp.status_code == 200
    task_id = resp.json()["task_id"]

    # Task should be in PLANNING after chat
    task_resp = await client.get(f"/tasks/{task_id}")
    assert task_resp.json()["status"] == "planning"

    # Dispatch (returns immediately, background task runs)
    dispatch_resp = await client.post(f"/tasks/{task_id}/dispatch")
    assert dispatch_resp.status_code == 200
    data = dispatch_resp.json()
    assert data["task_id"] == task_id
    assert "dispatched" in data["message"].lower()


@pytest.mark.asyncio
async def test_dispatch_not_found(client: AsyncClient) -> None:
    resp = await client.post("/tasks/TASK-nonexist/dispatch")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_dispatch_wrong_status(client: AsyncClient) -> None:
    """Dispatch should fail with 409 if task is not in PLANNING."""
    # Create a task (it starts as CREATED before transitioning to PLANNING)
    # We need to get it stuck in a non-PLANNING state
    resp = await client.post("/chat", json={"message": "Fix login bug"})
    task_id = resp.json()["task_id"]

    # Cancel it first
    await client.post(f"/tasks/{task_id}/cancel")

    # Try to dispatch a cancelled task
    dispatch_resp = await client.post(f"/tasks/{task_id}/dispatch")
    assert dispatch_resp.status_code == 409
    assert "PLANNING" in dispatch_resp.json()["detail"]


@pytest.mark.asyncio
async def test_list_executions(client: AsyncClient) -> None:
    """List executions for a task (initially empty)."""
    resp = await client.post("/chat", json={"message": "Fix login bug"})
    task_id = resp.json()["task_id"]

    exec_resp = await client.get(f"/tasks/{task_id}/executions")
    assert exec_resp.status_code == 200
    assert exec_resp.json() == []


@pytest.mark.asyncio
async def test_list_executions_not_found(client: AsyncClient) -> None:
    resp = await client.get("/tasks/TASK-nonexist/executions")
    assert resp.status_code == 404
