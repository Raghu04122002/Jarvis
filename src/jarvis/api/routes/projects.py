"""Project API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from jarvis.api.dependencies import get_project_service, get_session
from jarvis.models.project import (
    CreateProjectRequest,
    Project,
    ProjectNotFoundError,
    ProjectSummary,
    UpdateProjectRequest,
)

router = APIRouter()


def _not_found(project_id: str) -> HTTPException:
    return HTTPException(status_code=404, detail=f"Project not found: {project_id}")


@router.post("/projects")
async def create_project(
    request: CreateProjectRequest,
    session: AsyncSession = Depends(get_session),
) -> Project:
    """Create a new project in the registry."""
    service = get_project_service()
    return await service.create_project(
        session,
        name=request.name,
        local_path=request.local_path,
        github_repo=request.github_repo,
        default_branch=request.default_branch,
        stack=request.stack,
        preferred_agent=request.preferred_agent,
        deployment=request.deployment,
        instructions=request.instructions,
    )


@router.get("/projects")
async def list_projects(
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
) -> list[ProjectSummary]:
    """List all registered projects."""
    service = get_project_service()
    return await service.list_projects(session, limit=limit)


@router.get("/projects/{project_id}")
async def get_project(
    project_id: str,
    session: AsyncSession = Depends(get_session),
) -> Project:
    """Get full project details."""
    service = get_project_service()
    try:
        return await service.get_project(session, project_id)
    except ProjectNotFoundError:
        raise _not_found(project_id)


@router.patch("/projects/{project_id}")
async def update_project(
    project_id: str,
    request: UpdateProjectRequest,
    session: AsyncSession = Depends(get_session),
) -> Project:
    """Update project fields."""
    service = get_project_service()
    fields = request.model_dump(exclude_unset=True)
    if not fields:
        raise HTTPException(status_code=422, detail="No fields to update")
    try:
        return await service.update_project(session, project_id, **fields)
    except ProjectNotFoundError:
        raise _not_found(project_id)


@router.delete("/projects/{project_id}", status_code=204)
async def remove_project(
    project_id: str,
    session: AsyncSession = Depends(get_session),
) -> Response:
    """Remove a project from the registry."""
    service = get_project_service()
    try:
        await service.remove_project(session, project_id)
    except ProjectNotFoundError:
        raise _not_found(project_id)
    return Response(status_code=204)
