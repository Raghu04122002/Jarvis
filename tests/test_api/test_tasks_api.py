"""Tests for the task API endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_chat_creates_task(client: AsyncClient) -> None:
    resp = await client.post("/chat", json={"message": "Fix the login issue"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["task_id"].startswith("TASK-")
    assert data["status"] == "planning"
    assert data["title"] == "Fix the login issue"
    assert len(data["plan"]) > 0
    assert "message" in data


@pytest.mark.asyncio
async def test_chat_empty_message(client: AsyncClient) -> None:
    resp = await client.post("/chat", json={"message": ""})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_chat_missing_message(client: AsyncClient) -> None:
    resp = await client.post("/chat", json={})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_tasks_empty(client: AsyncClient) -> None:
    resp = await client.get("/tasks")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_tasks_after_create(client: AsyncClient) -> None:
    await client.post("/chat", json={"message": "Create task 1"})
    await client.post("/chat", json={"message": "Build task 2"})
    resp = await client.get("/tasks")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_list_tasks_filter_by_status(client: AsyncClient) -> None:
    await client.post("/chat", json={"message": "Create a task"})
    resp = await client.get("/tasks", params={"status": "planning"})
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    resp = await client.get("/tasks", params={"status": "completed"})
    assert resp.status_code == 200
    assert len(resp.json()) == 0


@pytest.mark.asyncio
async def test_get_task(client: AsyncClient) -> None:
    chat_resp = await client.post("/chat", json={"message": "Fix something"})
    task_id = chat_resp.json()["task_id"]
    resp = await client.get(f"/tasks/{task_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == task_id
    assert data["request"] == "Fix something"
    assert data["status"] == "planning"
    assert len(data["plan"]) > 0


@pytest.mark.asyncio
async def test_get_task_not_found(client: AsyncClient) -> None:
    resp = await client.get("/tasks/TASK-nonexistent")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_cancel_task(client: AsyncClient) -> None:
    chat_resp = await client.post("/chat", json={"message": "Delete this file"})
    task_id = chat_resp.json()["task_id"]
    resp = await client.post(f"/tasks/{task_id}/cancel")
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"


@pytest.mark.asyncio
async def test_cancel_already_cancelled(client: AsyncClient) -> None:
    chat_resp = await client.post("/chat", json={"message": "Remove old configs"})
    task_id = chat_resp.json()["task_id"]
    await client.post(f"/tasks/{task_id}/cancel")
    resp = await client.post(f"/tasks/{task_id}/cancel")
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_cancel_not_found(client: AsyncClient) -> None:
    resp = await client.post("/tasks/TASK-nope/cancel")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_steps(client: AsyncClient) -> None:
    chat_resp = await client.post("/chat", json={"message": "Build this feature"})
    task_id = chat_resp.json()["task_id"]
    resp = await client.get(f"/tasks/{task_id}/steps")
    assert resp.status_code == 200
    steps = resp.json()
    assert len(steps) > 0
    assert steps[0]["sequence"] == 1
    assert steps[0]["status"] == "pending"


@pytest.mark.asyncio
async def test_get_steps_not_found(client: AsyncClient) -> None:
    resp = await client.get("/tasks/TASK-nope/steps")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_retry_not_failed(client: AsyncClient) -> None:
    chat_resp = await client.post("/chat", json={"message": "Run the tests"})
    task_id = chat_resp.json()["task_id"]
    resp = await client.post(f"/tasks/{task_id}/retry")
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_retry_not_found(client: AsyncClient) -> None:
    resp = await client.post("/tasks/TASK-nope/retry")
    assert resp.status_code == 404
