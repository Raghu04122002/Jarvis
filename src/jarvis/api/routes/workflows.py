"""Workflow API routes — endpoints for triggering multi-step workflows."""

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from jarvis.api.dependencies import (
    get_agent_execution_service,
    get_approval_service,
    get_database,
    get_event_bus,
    get_memory_service,
    get_project_service,
    get_session,
    get_tool_registry,
)
from jarvis.services.task_service import TaskService
from jarvis.workflows.dev_workflow import DevWorkflow
from jarvis.workflows.models import DevWorkflowRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/workflows", tags=["workflows"])


async def _run_dev_workflow_background(
    workflow: DevWorkflow,
    issue_number: int,
    project_id: str,
    priority: str,
) -> None:
    """Run dev workflow in background with its own session."""
    db = get_database()
    async with db.session() as session:
        try:
            await workflow.run(session, issue_number, project_id, priority)
            await session.commit()
        except Exception:
            logger.exception("Dev workflow failed for issue #%d", issue_number)


@router.post("/dev", status_code=202)
async def start_dev_workflow(
    request_body: DevWorkflowRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    """Start a dev workflow for a GitHub issue.

    Returns 202 with task_id. Workflow runs in background.
    Frontend monitors progress via SSE.
    """
    from jarvis.agents.registry import create_default_registry
    from jarvis.agents.router import AgentRouter

    config = request.app.state.config
    event_bus = get_event_bus()
    task_service = TaskService(event_bus)

    registry = create_default_registry()
    agent_router = AgentRouter(registry, config.agents)

    workflow = DevWorkflow(
        task_service=task_service,
        agent_execution_service=get_agent_execution_service(),
        project_service=get_project_service(),
        memory_service=get_memory_service(),
        approval_service=get_approval_service(),
        tool_registry=get_tool_registry(),
        agent_registry=registry,
        agent_router=agent_router,
        event_bus=event_bus,
        workflow_config=config.workflow,
        agents_config=config.agents,
    )

    # Create a quick task to get the ID for the response
    task = await task_service.create_task(
        session,
        request=f"Dev workflow: issue #{request_body.issue_number}",
        title=f"Dev workflow: issue #{request_body.issue_number}",
        project_id=request_body.project_id,
        metadata={"workflow": "dev", "issue_number": str(request_body.issue_number)},
    )

    background_tasks.add_task(
        _run_dev_workflow_background,
        workflow,
        request_body.issue_number,
        request_body.project_id,
        request_body.priority,
    )

    msg = f"Dev workflow started for issue #{request_body.issue_number}"
    return {"task_id": task.id, "message": msg}
