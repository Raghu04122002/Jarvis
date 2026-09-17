"""Tests for the project API endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_project(client: AsyncClient) -> None:
    resp = await client.post(
        "/projects",
        json={"name": "Jarvis", "local_path": "/home/user/jarvis"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"].startswith("PROJ-")
    assert data["name"] == "Jarvis"
    assert data["local_path"] == "/home/user/jarvis"
    assert data["version"] == 1


@pytest.mark.asyncio
async def test_create_project_with_all_fields(client: AsyncClient) -> None:
    resp = await client.post(
        "/projects",
        json={
            "name": "WebApp",
            "local_path": "/home/user/webapp",
            "github_repo": "user/webapp",
            "default_branch": "develop",
            "stack": ["python", "react"],
            "preferred_agent": "claude",
            "deployment": {"env": "production"},
            "instructions": "Use ruff",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["github_repo"] == "user/webapp"
    assert data["stack"] == ["python", "react"]


@pytest.mark.asyncio
async def test_create_project_validation_error(client: AsyncClient) -> None:
    resp = await client.post("/projects", json={"name": "", "local_path": "/a"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_project_missing_fields(client: AsyncClient) -> None:
    resp = await client.post("/projects", json={})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_projects_empty(client: AsyncClient) -> None:
    resp = await client.get("/projects")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_projects_after_create(client: AsyncClient) -> None:
    await client.post("/projects", json={"name": "A", "local_path": "/a"})
    await client.post("/projects", json={"name": "B", "local_path": "/b"})
    resp = await client.get("/projects")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_list_projects_with_limit(client: AsyncClient) -> None:
    for i in range(5):
        await client.post("/projects", json={"name": f"P{i}", "local_path": f"/{i}"})
    resp = await client.get("/projects", params={"limit": 3})
    assert resp.status_code == 200
    assert len(resp.json()) == 3


@pytest.mark.asyncio
async def test_get_project(client: AsyncClient) -> None:
    create_resp = await client.post(
        "/projects", json={"name": "Test", "local_path": "/test"}
    )
    project_id = create_resp.json()["id"]
    resp = await client.get(f"/projects/{project_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == project_id
    assert data["name"] == "Test"


@pytest.mark.asyncio
async def test_get_project_not_found(client: AsyncClient) -> None:
    resp = await client.get("/projects/PROJ-nonexistent")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_project(client: AsyncClient) -> None:
    create_resp = await client.post(
        "/projects", json={"name": "Old", "local_path": "/old"}
    )
    project_id = create_resp.json()["id"]
    resp = await client.patch(f"/projects/{project_id}", json={"name": "New"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "New"
    assert data["version"] == 2


@pytest.mark.asyncio
async def test_update_project_not_found(client: AsyncClient) -> None:
    resp = await client.patch("/projects/PROJ-nope", json={"name": "X"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_project_empty_body(client: AsyncClient) -> None:
    create_resp = await client.post(
        "/projects", json={"name": "A", "local_path": "/a"}
    )
    project_id = create_resp.json()["id"]
    resp = await client.patch(f"/projects/{project_id}", json={})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_delete_project(client: AsyncClient) -> None:
    create_resp = await client.post(
        "/projects", json={"name": "Del", "local_path": "/del"}
    )
    project_id = create_resp.json()["id"]
    resp = await client.delete(f"/projects/{project_id}")
    assert resp.status_code == 204
    # Verify deleted
    get_resp = await client.get(f"/projects/{project_id}")
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_project_not_found(client: AsyncClient) -> None:
    resp = await client.delete("/projects/PROJ-nope")
    assert resp.status_code == 404
