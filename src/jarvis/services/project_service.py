"""Project service — manages project registry operations with database persistence.

All project business logic lives here, not in API route handlers.
"""

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from jarvis.db.tables import ProjectRow
from jarvis.events import Event, EventBus, EventType
from jarvis.models.project import Project, ProjectNotFoundError, ProjectSummary

logger = logging.getLogger(__name__)


def _row_to_project(row: ProjectRow) -> Project:
    """Convert a database row to a Project domain model."""
    return Project(
        id=row.id,
        name=row.name,
        local_path=row.local_path,
        github_repo=row.github_repo,
        default_branch=row.default_branch,
        stack=row.stack if isinstance(row.stack, list) else [],
        preferred_agent=row.preferred_agent,
        deployment=row.deployment if isinstance(row.deployment, dict) else {},
        instructions=row.instructions,
        version=row.version,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _row_to_summary(row: ProjectRow) -> ProjectSummary:
    """Convert a database row to a ProjectSummary."""
    return ProjectSummary(
        id=row.id,
        name=row.name,
        local_path=row.local_path,
        stack=row.stack if isinstance(row.stack, list) else [],
        preferred_agent=row.preferred_agent,
        created_at=row.created_at,
    )


class ProjectService:
    """Manages project creation, retrieval, and updates.

    Uses async database persistence via SQLAlchemy.
    """

    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus

    def _next_id(self) -> str:
        return f"PROJ-{uuid.uuid4().hex[:8]}"

    async def create_project(
        self,
        session: AsyncSession,
        name: str,
        local_path: str,
        *,
        github_repo: str | None = None,
        default_branch: str = "main",
        stack: list[str] | None = None,
        preferred_agent: str | None = None,
        deployment: dict[str, str] | None = None,
        instructions: str = "",
    ) -> Project:
        now = datetime.now(UTC)
        project_id = self._next_id()
        row = ProjectRow(
            id=project_id,
            name=name,
            local_path=local_path,
            github_repo=github_repo,
            default_branch=default_branch,
            stack=stack or [],
            preferred_agent=preferred_agent,
            deployment=deployment or {},
            instructions=instructions,
            version=1,
            created_at=now,
            updated_at=now,
        )
        session.add(row)
        await session.flush()
        project = _row_to_project(row)
        self._event_bus.publish(
            Event(type=EventType.PROJECT_CREATED, task_id=project_id)
        )
        return project

    async def get_project(self, session: AsyncSession, project_id: str) -> Project:
        row = await session.get(ProjectRow, project_id)
        if row is None:
            raise ProjectNotFoundError(project_id)
        return _row_to_project(row)

    async def list_projects(
        self,
        session: AsyncSession,
        *,
        limit: int = 50,
    ) -> list[ProjectSummary]:
        stmt = select(ProjectRow).order_by(ProjectRow.created_at.desc()).limit(limit)
        result = await session.execute(stmt)
        rows = result.scalars().all()
        return [_row_to_summary(r) for r in rows]

    async def update_project(
        self,
        session: AsyncSession,
        project_id: str,
        **fields: str | list[str] | dict[str, str] | None,
    ) -> Project:
        row = await session.get(ProjectRow, project_id)
        if row is None:
            raise ProjectNotFoundError(project_id)

        updatable = {
            "name", "local_path", "github_repo", "default_branch",
            "stack", "preferred_agent", "deployment", "instructions",
        }
        for key, value in fields.items():
            if key in updatable and value is not None:
                setattr(row, key, value)

        row.updated_at = datetime.now(UTC)
        row.version += 1
        await session.flush()

        self._event_bus.publish(
            Event(type=EventType.PROJECT_UPDATED, task_id=project_id)
        )
        return _row_to_project(row)

    async def remove_project(self, session: AsyncSession, project_id: str) -> None:
        row = await session.get(ProjectRow, project_id)
        if row is None:
            raise ProjectNotFoundError(project_id)
        await session.delete(row)
        await session.flush()
        self._event_bus.publish(
            Event(type=EventType.PROJECT_DELETED, task_id=project_id)
        )
