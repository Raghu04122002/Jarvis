"""HTTP-level tests for the smart chat endpoint."""

import pytest
from httpx import ASGITransport, AsyncClient

from jarvis.api.dependencies import init_dependencies_with_db, reset_dependencies
from jarvis.db.engine import Database
from jarvis.db.tables import Base
from jarvis.main import create_app


@pytest.fixture
async def client() -> AsyncClient:
    db = Database(url="sqlite+aiosqlite://")
    async with db.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    reset_dependencies()
    init_dependencies_with_db(db)
    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
    reset_dependencies()
    await db.disconnect()


class TestSmartChatApi:
    @pytest.mark.asyncio
    async def test_query_returns_answer(self, client: AsyncClient) -> None:
        resp = await client.post("/chat", json={"message": "check my projects"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["answer"] is not None
        assert data["task_id"] is None
        assert data["status"] == "answered"

    @pytest.mark.asyncio
    async def test_action_creates_task(self, client: AsyncClient) -> None:
        resp = await client.post("/chat", json={"message": "deploy staging app"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["task_id"] is not None
        assert data["status"] == "planning"

    @pytest.mark.asyncio
    async def test_status_field_present(self, client: AsyncClient) -> None:
        resp = await client.post("/chat", json={"message": "hello"})
        assert resp.status_code == 200
        assert "status" in resp.json()

    @pytest.mark.asyncio
    async def test_plan_present_for_action(self, client: AsyncClient) -> None:
        resp = await client.post("/chat", json={"message": "build the frontend"})
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["plan"], list)
        assert len(data["plan"]) > 0

    @pytest.mark.asyncio
    async def test_message_field_always_present(self, client: AsyncClient) -> None:
        # Query
        resp1 = await client.post("/chat", json={"message": "status"})
        assert "message" in resp1.json()
        # Action
        resp2 = await client.post("/chat", json={"message": "do something"})
        assert "message" in resp2.json()
