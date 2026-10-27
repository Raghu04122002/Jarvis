"""Task API endpoints."""

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from jarvis.api.dependencies import (
    get_approval_service,
    get_database,
    get_orchestrator,
    get_permission_gate,
    get_session,
    get_tool_registry,
)
from jarvis.models.agent import AgentExecution
from jarvis.models.step import TaskStep
from jarvis.models.task import (
    ChatRequest,
    InvalidTransitionError,
    Task,
    TaskPriority,
    TaskStatus,
    TaskSummary,
)
from jarvis.permissions.gate import ApprovalRequiredError, PermissionDeniedError
from jarvis.services.task_service import TaskNotFoundError
from jarvis.tools.base import InvalidOperationError, ToolError
from jarvis.tools.registry import ToolNotFoundError

router = APIRouter()
logger = logging.getLogger(__name__)


def _not_found(task_id: str) -> HTTPException:
    return HTTPException(status_code=404, detail=f"Task not found: {task_id}")


@router.post("/chat")
async def chat(
    request: ChatRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
) -> dict[str, str | list[str] | None]:
    """Accept a natural-language request, classify intent, and route accordingly."""
    orchestrator = get_orchestrator()
    response = await orchestrator.handle_chat(session, request, background_tasks=background_tasks)
    return response.model_dump()


def _sse(event: dict[str, Any]) -> str:
    return f"event: {event['type']}\ndata: {json.dumps(event, default=str)}\n\n"


@router.post("/chat/stream")
async def chat_stream(
    request: ChatRequest, background_tasks: BackgroundTasks
) -> StreamingResponse:
    """Same as ``POST /chat`` but streams Server-Sent Events.

    Events: ``token`` {text}, ``tool_start`` {id, name, label, args},
    ``tool_end`` {id, name, ok, output}, ``task_created`` {task_id, title},
    ``done`` {response: ChatResponse}, ``error`` {message}.
    """
    orchestrator = get_orchestrator()
    db = get_database()

    async def events() -> AsyncIterator[str]:
        async with db.session() as session:
            try:
                async for event in orchestrator.stream_chat(
                    session, request, background_tasks=background_tasks
                ):
                    if event["type"] == "done":
                        event = {"type": "done", "response": event["response"].model_dump()}
                    yield _sse(event)
                await session.commit()
            except Exception:
                logger.exception("Chat stream failed")
                yield _sse({"type": "error", "message": "Something went wrong. Please try again."})

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        background=background_tasks,
    )


@router.get("/tasks")
async def list_tasks(
    status: TaskStatus | None = None,
    priority: TaskPriority | None = None,
    project_id: str | None = None,
    q: str | None = Query(None, max_length=200, description="Search title and request"),
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
) -> list[TaskSummary]:
    """List tasks with optional filtering and search."""
    orchestrator = get_orchestrator()
    return await orchestrator.task_service.list_tasks(
        session, status=status, priority=priority, project_id=project_id, query=q, limit=limit
    )


@router.get("/tasks/{task_id}")
async def get_task(
    task_id: str,
    session: AsyncSession = Depends(get_session),
) -> Task:
    """Get full task details including plan and execution history."""
    orchestrator = get_orchestrator()
    try:
        return await orchestrator.task_service.get_task(session, task_id)
    except TaskNotFoundError:
        raise _not_found(task_id)


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(
    task_id: str,
    session: AsyncSession = Depends(get_session),
) -> Task:
    """Cancel a pending or running task."""
    orchestrator = get_orchestrator()
    try:
        task = await orchestrator.task_service.cancel_task(session, task_id)
        await session.commit()
    except TaskNotFoundError:
        raise _not_found(task_id)
    except InvalidTransitionError as e:
        raise HTTPException(status_code=409, detail=str(e))
    # Stop the agent process too, so a cancelled task stops doing work.
    await orchestrator.cancel_agent_for_task(task_id)
    return task


@router.post("/tasks/{task_id}/retry")
async def retry_task(
    task_id: str,
    session: AsyncSession = Depends(get_session),
) -> Task:
    """Retry a failed task by moving it back to PLANNING."""
    orchestrator = get_orchestrator()
    try:
        task = await orchestrator.task_service.get_task(session, task_id)
    except TaskNotFoundError:
        raise _not_found(task_id)
    if task.status != TaskStatus.FAILED:
        raise HTTPException(
            status_code=409,
            detail=f"Only failed tasks can be retried. Current status: {task.status}",
        )
    try:
        return await orchestrator.task_service.transition_task(
            session, task_id, TaskStatus.PLANNING
        )
    except InvalidTransitionError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("/tasks/{task_id}/steps")
async def get_steps(
    task_id: str,
    session: AsyncSession = Depends(get_session),
) -> list[TaskStep]:
    """Get the execution steps for a task."""
    orchestrator = get_orchestrator()
    try:
        return await orchestrator.task_service.get_steps(session, task_id)
    except TaskNotFoundError:
        raise _not_found(task_id)


@router.post("/tasks/{task_id}/dispatch")
async def dispatch_task(
    task_id: str,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    """Dispatch a task to an agent for execution.

    The task must be in PLANNING status. Returns immediately;
    the agent runs in the background.
    """
    orchestrator = get_orchestrator()
    try:
        task = await orchestrator.task_service.get_task(session, task_id)
    except TaskNotFoundError:
        raise _not_found(task_id)

    if task.status != TaskStatus.PLANNING:
        raise HTTPException(
            status_code=409,
            detail=f"Task must be in PLANNING status to dispatch. Current status: {task.status}",
        )

    async def _run_dispatch() -> None:
        db = get_database()
        async with db.session() as bg_session:
            try:
                await orchestrator.dispatch_task(bg_session, task_id)
            except Exception:
                import logging

                logging.getLogger(__name__).exception(
                    "Background dispatch failed for task %s", task_id
                )

    background_tasks.add_task(_run_dispatch)
    return {"task_id": task_id, "message": "Task dispatched to agent"}


@router.get("/tasks/{task_id}/executions")
async def list_executions(
    task_id: str,
    session: AsyncSession = Depends(get_session),
) -> list[AgentExecution]:
    """List agent execution records for a task."""
    orchestrator = get_orchestrator()
    try:
        await orchestrator.task_service.get_task(session, task_id)
    except TaskNotFoundError:
        raise _not_found(task_id)

    if orchestrator.agent_execution_service is None:
        raise HTTPException(status_code=500, detail="Agent execution service not configured")

    return await orchestrator.agent_execution_service.list_executions_for_task(session, task_id)


class ToolExecuteRequest(BaseModel):
    """Request body for tool execution."""

    working_dir: str
    kwargs: dict[str, str | int | list[str]] = {}


class ToolExecuteResponse(BaseModel):
    """Response from tool execution."""

    success: bool
    output: str
    error: str | None = None
    exit_code: int = 0


@router.post("/tasks/{task_id}/tools/{tool_name}/{operation}")
async def execute_tool(
    task_id: str,
    tool_name: str,
    operation: str,
    request: ToolExecuteRequest,
    session: AsyncSession = Depends(get_session),
) -> ToolExecuteResponse:
    """Execute a tool operation in the context of a task."""
    orchestrator = get_orchestrator()
    try:
        await orchestrator.task_service.get_task(session, task_id)
    except TaskNotFoundError:
        raise _not_found(task_id)

    registry = get_tool_registry()
    gate = get_permission_gate()

    try:
        tool = registry.get(tool_name)
    except ToolNotFoundError:
        raise HTTPException(status_code=404, detail=f"Tool not found: {tool_name}")

    try:
        risk_level = tool.risk_level_for(operation)
    except InvalidOperationError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid operation '{operation}' for tool '{tool_name}'",
        )

    try:
        gate.check(tool_name, operation, risk_level)
    except ApprovalRequiredError as e:
        approval_service = get_approval_service()
        approval = await approval_service.create_request(
            session,
            task_id=task_id,
            tool_name=tool_name,
            operation=operation,
            risk_level=risk_level,
            description=str(e),
            context={"working_dir": request.working_dir, "kwargs": request.kwargs},
        )
        raise HTTPException(
            status_code=403,
            detail={"message": str(e), "approval_id": approval.id},
        )
    except PermissionDeniedError as e:
        raise HTTPException(status_code=403, detail=str(e))

    try:
        result = await tool.execute(operation, request.working_dir, **request.kwargs)
    except ToolError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return ToolExecuteResponse(
        success=result.success,
        output=result.output,
        error=result.error,
        exit_code=result.exit_code,
    )
