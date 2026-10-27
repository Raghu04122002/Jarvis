"""Task list filters/search and the stale-planning sweep."""

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from jarvis.db.tables import TaskRow
from jarvis.events import EventBus
from jarvis.models.task import TaskStatus
from jarvis.services.task_service import TaskService


@pytest.mark.asyncio
async def test_list_filters_and_search(db_session: AsyncSession) -> None:
    svc = TaskService(EventBus())
    a = await svc.create_task(
        db_session,
        request="fix login bug",
        title="Fix login",
        project_id="p1",
        metadata={"agent_name": "claude_code", "conversation_id": "c1"},
    )
    await svc.create_task(db_session, request="add dark mode", title="Dark mode", project_id="p2")

    hits = await svc.list_tasks(db_session, query="LOGIN")
    assert [t.id for t in hits] == [a.id]
    assert hits[0].agent_name == "claude_code"
    assert hits[0].conversation_id == "c1"
    assert hits[0].project_id == "p1"

    assert len(await svc.list_tasks(db_session, project_id="p2")) == 1
    assert await svc.list_tasks(db_session, query="nothing matches") == []


@pytest.mark.asyncio
async def test_fail_stale_tasks(db_session: AsyncSession) -> None:
    svc = TaskService(EventBus())
    old = await svc.create_task(db_session, request="old", title="Old")
    fresh = await svc.create_task(db_session, request="fresh", title="Fresh")
    for t in (old, fresh):
        await svc.transition_task(db_session, t.id, TaskStatus.PLANNING)
    row = await db_session.get(TaskRow, old.id)
    assert row is not None
    row.updated_at = datetime.now(UTC) - timedelta(hours=1)
    await db_session.flush()

    failed = await svc.fail_stale_tasks(db_session, planning_timeout=timedelta(minutes=15))
    assert failed == [old.id]
    stale = await svc.get_task(db_session, old.id)
    assert stale.status == TaskStatus.FAILED
    assert stale.error is not None and "Stale" in stale.error
    assert (await svc.get_task(db_session, fresh.id)).status == TaskStatus.PLANNING
    # A stale task can be retried.
    await svc.transition_task(db_session, old.id, TaskStatus.PLANNING)


@pytest.mark.asyncio
async def test_list_tasks_api_search(client: AsyncClient) -> None:
    await client.post("/chat", json={"message": "Fix the login issue"})
    await client.post("/chat", json={"message": "Deploy the staging server"})
    resp = await client.get("/tasks", params={"q": "staging"})
    assert resp.status_code == 200
    titles = [t["title"] for t in resp.json()]
    assert titles == ["Deploy the staging server"]


@pytest.mark.asyncio
async def test_cancel_api_stops_agent(client: AsyncClient) -> None:
    from jarvis.api.dependencies import get_orchestrator

    resp = await client.post("/chat", json={"message": "Fix the login issue"})
    task_id = resp.json()["task_id"]
    cancelled: list[str] = []

    class _Agent:
        async def cancel(self) -> None:
            cancelled.append(task_id)

    get_orchestrator()._active_agents[task_id] = _Agent()  # type: ignore[assignment]
    resp = await client.post(f"/tasks/{task_id}/cancel")
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"
    assert cancelled == [task_id]
