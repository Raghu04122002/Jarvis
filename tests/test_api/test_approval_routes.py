"""Tests for the approval API endpoints."""

import pytest
from httpx import AsyncClient

from jarvis.api.dependencies import get_approval_service, get_database
from jarvis.models.approval import RiskLevel


async def _create_approval(client: AsyncClient) -> str:
    """Helper: create an approval request directly via the service."""
    service = get_approval_service()
    db = get_database()
    async with db.session() as session:
        req = await service.create_request(
            session,
            task_id="TASK-test",
            tool_name="git",
            operation="push",
            risk_level=RiskLevel.REQUIRES_APPROVAL,
            description="Push to remote",
        )
        await session.commit()
        return req.id


@pytest.mark.asyncio
async def test_list_approvals_empty(client: AsyncClient) -> None:
    resp = await client.get("/approvals")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_approvals_after_create(client: AsyncClient) -> None:
    await _create_approval(client)
    resp = await client.get("/approvals")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["tool_name"] == "git"
    assert data[0]["operation"] == "push"


@pytest.mark.asyncio
async def test_list_approvals_filter_status(client: AsyncClient) -> None:
    await _create_approval(client)
    resp = await client.get("/approvals", params={"status": "pending"})
    assert resp.status_code == 200
    assert len(resp.json()) == 1

    resp = await client.get("/approvals", params={"status": "approved"})
    assert resp.status_code == 200
    assert len(resp.json()) == 0


@pytest.mark.asyncio
async def test_list_approvals_filter_task_id(client: AsyncClient) -> None:
    await _create_approval(client)
    resp = await client.get("/approvals", params={"task_id": "TASK-test"})
    assert resp.status_code == 200
    assert len(resp.json()) == 1

    resp = await client.get("/approvals", params={"task_id": "TASK-other"})
    assert resp.status_code == 200
    assert len(resp.json()) == 0


@pytest.mark.asyncio
async def test_get_approval(client: AsyncClient) -> None:
    approval_id = await _create_approval(client)
    resp = await client.get(f"/approvals/{approval_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == approval_id
    assert data["tool_name"] == "git"
    assert data["status"] == "pending"


@pytest.mark.asyncio
async def test_get_approval_not_found(client: AsyncClient) -> None:
    resp = await client.get("/approvals/APPR-nonexist")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_approve(client: AsyncClient) -> None:
    approval_id = await _create_approval(client)
    resp = await client.post(
        f"/approvals/{approval_id}/approve",
        json={"decided_by": "admin", "reason": "ok"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "approved"
    assert data["decided_by"] == "admin"
    assert data["decision_reason"] == "ok"


@pytest.mark.asyncio
async def test_approve_not_found(client: AsyncClient) -> None:
    resp = await client.post(
        "/approvals/APPR-nonexist/approve", json={}
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_approve_already_decided(client: AsyncClient) -> None:
    approval_id = await _create_approval(client)
    await client.post(f"/approvals/{approval_id}/approve", json={})
    resp = await client.post(f"/approvals/{approval_id}/approve", json={})
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_reject(client: AsyncClient) -> None:
    approval_id = await _create_approval(client)
    resp = await client.post(
        f"/approvals/{approval_id}/reject",
        json={"decided_by": "admin", "reason": "too risky"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "denied"
    assert data["decision_reason"] == "too risky"


@pytest.mark.asyncio
async def test_reject_not_found(client: AsyncClient) -> None:
    resp = await client.post(
        "/approvals/APPR-nonexist/reject", json={}
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_reject_already_decided(client: AsyncClient) -> None:
    approval_id = await _create_approval(client)
    await client.post(f"/approvals/{approval_id}/reject", json={})
    resp = await client.post(f"/approvals/{approval_id}/reject", json={})
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_approve_then_reject_fails(client: AsyncClient) -> None:
    approval_id = await _create_approval(client)
    await client.post(f"/approvals/{approval_id}/approve", json={})
    resp = await client.post(f"/approvals/{approval_id}/reject", json={})
    assert resp.status_code == 409
