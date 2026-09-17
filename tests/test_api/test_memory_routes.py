"""Tests for Memory API endpoints."""

import pytest
from httpx import AsyncClient


@pytest.fixture
async def memory_id(client: AsyncClient) -> str:
    """Create a memory and return its id."""
    resp = await client.post("/memories", json={
        "memory_type": "user_preference",
        "key": "editor",
        "content": "vim",
        "tags": ["tools"],
    })
    assert resp.status_code == 200
    return resp.json()["id"]


class TestCreateMemory:
    @pytest.mark.asyncio
    async def test_create(self, client: AsyncClient) -> None:
        resp = await client.post("/memories", json={
            "memory_type": "user_preference",
            "key": "editor",
            "content": "vim",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["key"] == "editor"
        assert data["content"] == "vim"
        assert data["scope"] == "global"
        assert data["id"].startswith("MEM-")

    @pytest.mark.asyncio
    async def test_create_with_project(self, client: AsyncClient) -> None:
        resp = await client.post("/memories", json={
            "memory_type": "project_memory",
            "key": "stack",
            "content": "Python + FastAPI",
            "project_id": "proj-1",
        })
        assert resp.status_code == 200
        assert resp.json()["scope"] == "project"
        assert resp.json()["project_id"] == "proj-1"

    @pytest.mark.asyncio
    async def test_create_validation_empty_key(self, client: AsyncClient) -> None:
        resp = await client.post("/memories", json={
            "memory_type": "user_preference",
            "key": "",
            "content": "vim",
        })
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_create_validation_empty_content(self, client: AsyncClient) -> None:
        resp = await client.post("/memories", json={
            "memory_type": "user_preference",
            "key": "editor",
            "content": "",
        })
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_create_validation_invalid_type(self, client: AsyncClient) -> None:
        resp = await client.post("/memories", json={
            "memory_type": "invalid_type",
            "key": "editor",
            "content": "vim",
        })
        assert resp.status_code == 422


class TestListMemories:
    @pytest.mark.asyncio
    async def test_list_empty(self, client: AsyncClient) -> None:
        resp = await client.get("/memories")
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_list_after_create(
        self, client: AsyncClient, memory_id: str
    ) -> None:
        resp = await client.get("/memories")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["id"] == memory_id

    @pytest.mark.asyncio
    async def test_list_filter_by_type(
        self, client: AsyncClient, memory_id: str
    ) -> None:
        resp = await client.get("/memories", params={"memory_type": "decision"})
        assert resp.status_code == 200
        assert resp.json() == []

        resp = await client.get(
            "/memories", params={"memory_type": "user_preference"}
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 1


class TestGetMemory:
    @pytest.mark.asyncio
    async def test_get_existing(
        self, client: AsyncClient, memory_id: str
    ) -> None:
        resp = await client.get(f"/memories/{memory_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == memory_id
        assert resp.json()["content"] == "vim"

    @pytest.mark.asyncio
    async def test_get_not_found(self, client: AsyncClient) -> None:
        resp = await client.get("/memories/nonexistent")
        assert resp.status_code == 404


class TestUpdateMemory:
    @pytest.mark.asyncio
    async def test_update_content(
        self, client: AsyncClient, memory_id: str
    ) -> None:
        resp = await client.patch(
            f"/memories/{memory_id}", json={"content": "neovim"}
        )
        assert resp.status_code == 200
        assert resp.json()["content"] == "neovim"
        assert resp.json()["version"] == 2

    @pytest.mark.asyncio
    async def test_update_tags(
        self, client: AsyncClient, memory_id: str
    ) -> None:
        resp = await client.patch(
            f"/memories/{memory_id}", json={"tags": ["editor", "dev"]}
        )
        assert resp.status_code == 200
        assert resp.json()["tags"] == ["editor", "dev"]

    @pytest.mark.asyncio
    async def test_update_not_found(self, client: AsyncClient) -> None:
        resp = await client.patch(
            "/memories/nonexistent", json={"content": "x"}
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_update_empty_body(
        self, client: AsyncClient, memory_id: str
    ) -> None:
        resp = await client.patch(f"/memories/{memory_id}", json={})
        assert resp.status_code == 422


class TestDeleteMemory:
    @pytest.mark.asyncio
    async def test_delete_existing(
        self, client: AsyncClient, memory_id: str
    ) -> None:
        resp = await client.delete(f"/memories/{memory_id}")
        assert resp.status_code == 204

        resp = await client.get(f"/memories/{memory_id}")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_not_found(self, client: AsyncClient) -> None:
        resp = await client.delete("/memories/nonexistent")
        assert resp.status_code == 404


class TestSearchMemories:
    @pytest.mark.asyncio
    async def test_search(self, client: AsyncClient, memory_id: str) -> None:
        resp = await client.get("/memories/search", params={"q": "vim"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["content"] == "vim"

    @pytest.mark.asyncio
    async def test_search_no_results(self, client: AsyncClient) -> None:
        resp = await client.get("/memories/search", params={"q": "nonexistent"})
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_search_requires_query(self, client: AsyncClient) -> None:
        resp = await client.get("/memories/search")
        assert resp.status_code == 422
