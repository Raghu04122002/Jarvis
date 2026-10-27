"""Tests for schedule API routes."""

from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from jarvis.api.dependencies import init_dependencies_with_db, reset_dependencies
from jarvis.config import JarvisConfig, SchedulerConfig
from jarvis.db.engine import Database
from jarvis.db.tables import Base
from jarvis.main import create_app


@pytest.fixture
async def client() -> AsyncClient:
    database = Database(url="sqlite+aiosqlite://")
    async with database.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    config = JarvisConfig(scheduler=SchedulerConfig(enabled=False))
    app = create_app(config)
    init_dependencies_with_db(database)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c  # type: ignore[misc]
    reset_dependencies()
    await database.disconnect()


def _one_time_body(**overrides: object) -> dict:  # type: ignore[type-arg]
    body: dict = {  # type: ignore[type-arg]
        "name": "Test Schedule",
        "schedule_type": "one_time",
        "task_request": "Check production",
        "run_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
    }
    body.update(overrides)
    return body


def _interval_body(**overrides: object) -> dict:  # type: ignore[type-arg]
    body: dict = {  # type: ignore[type-arg]
        "name": "Interval Schedule",
        "schedule_type": "interval",
        "task_request": "Check metrics",
        "interval_seconds": 3600,
    }
    body.update(overrides)
    return body


class TestCreateSchedule:
    @pytest.mark.asyncio
    async def test_create_returns_201(self, client: AsyncClient) -> None:
        resp = await client.post("/schedules", json=_one_time_body())
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("SCHED-")
        assert data["status"] == "active"

    @pytest.mark.asyncio
    async def test_create_interval(self, client: AsyncClient) -> None:
        resp = await client.post("/schedules", json=_interval_body())
        assert resp.status_code == 201
        assert resp.json()["schedule_type"] == "interval"


class TestListSchedules:
    @pytest.mark.asyncio
    async def test_list_empty(self, client: AsyncClient) -> None:
        resp = await client.get("/schedules")
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_list_returns_created(self, client: AsyncClient) -> None:
        await client.post("/schedules", json=_one_time_body())
        resp = await client.get("/schedules")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    @pytest.mark.asyncio
    async def test_list_filter_by_status(self, client: AsyncClient) -> None:
        await client.post("/schedules", json=_one_time_body())
        resp = await client.get("/schedules", params={"status": "paused"})
        assert resp.status_code == 200
        assert len(resp.json()) == 0


class TestGetSchedule:
    @pytest.mark.asyncio
    async def test_get_existing(self, client: AsyncClient) -> None:
        create_resp = await client.post("/schedules", json=_one_time_body())
        sched_id = create_resp.json()["id"]
        resp = await client.get(f"/schedules/{sched_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == sched_id

    @pytest.mark.asyncio
    async def test_get_not_found(self, client: AsyncClient) -> None:
        resp = await client.get("/schedules/SCHED-nonexist")
        assert resp.status_code == 404


class TestUpdateSchedule:
    @pytest.mark.asyncio
    async def test_update_name(self, client: AsyncClient) -> None:
        create_resp = await client.post("/schedules", json=_one_time_body())
        sched_id = create_resp.json()["id"]
        resp = await client.patch(
            f"/schedules/{sched_id}", json={"name": "Updated Name"}
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated Name"

    @pytest.mark.asyncio
    async def test_update_not_found(self, client: AsyncClient) -> None:
        resp = await client.patch(
            "/schedules/SCHED-nonexist", json={"name": "Nope"}
        )
        assert resp.status_code == 404


class TestPauseSchedule:
    @pytest.mark.asyncio
    async def test_pause_active(self, client: AsyncClient) -> None:
        create_resp = await client.post("/schedules", json=_one_time_body())
        sched_id = create_resp.json()["id"]
        resp = await client.post(f"/schedules/{sched_id}/pause")
        assert resp.status_code == 200
        assert resp.json()["status"] == "paused"

    @pytest.mark.asyncio
    async def test_pause_not_active_409(self, client: AsyncClient) -> None:
        create_resp = await client.post("/schedules", json=_one_time_body())
        sched_id = create_resp.json()["id"]
        await client.post(f"/schedules/{sched_id}/pause")
        resp = await client.post(f"/schedules/{sched_id}/pause")
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_pause_not_found(self, client: AsyncClient) -> None:
        resp = await client.post("/schedules/SCHED-nonexist/pause")
        assert resp.status_code == 404


class TestResumeSchedule:
    @pytest.mark.asyncio
    async def test_resume_paused(self, client: AsyncClient) -> None:
        create_resp = await client.post("/schedules", json=_one_time_body())
        sched_id = create_resp.json()["id"]
        await client.post(f"/schedules/{sched_id}/pause")
        resp = await client.post(f"/schedules/{sched_id}/resume")
        assert resp.status_code == 200
        assert resp.json()["status"] == "active"

    @pytest.mark.asyncio
    async def test_resume_not_paused_409(self, client: AsyncClient) -> None:
        create_resp = await client.post("/schedules", json=_one_time_body())
        sched_id = create_resp.json()["id"]
        resp = await client.post(f"/schedules/{sched_id}/resume")
        assert resp.status_code == 409


class TestCancelSchedule:
    @pytest.mark.asyncio
    async def test_cancel_active(self, client: AsyncClient) -> None:
        create_resp = await client.post("/schedules", json=_one_time_body())
        sched_id = create_resp.json()["id"]
        resp = await client.post(f"/schedules/{sched_id}/cancel")
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"

    @pytest.mark.asyncio
    async def test_cancel_already_cancelled_409(self, client: AsyncClient) -> None:
        create_resp = await client.post("/schedules", json=_one_time_body())
        sched_id = create_resp.json()["id"]
        await client.post(f"/schedules/{sched_id}/cancel")
        resp = await client.post(f"/schedules/{sched_id}/cancel")
        assert resp.status_code == 409
