"""Project resolver — resolves project name hints to project IDs."""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from jarvis.models.project import ProjectNotFoundError
from jarvis.services.project_service import ProjectService

logger = logging.getLogger(__name__)


class ProjectResolver:
    """Resolves project references from name hints to project IDs.

    Resolution order:
    1. If hint starts with "PROJ-" → try exact get_project()
    2. Else → find_by_name() case-insensitive substring
    3. Return first match ID, or fallback_id, or None
    """

    def __init__(self, project_service: ProjectService) -> None:
        self._project_service = project_service

    async def resolve(
        self,
        session: AsyncSession,
        hint: str | None,
        fallback_id: str | None = None,
    ) -> str | None:
        """Resolve a project hint to a project ID.

        Args:
            session: Database session.
            hint: A project name fragment or PROJ-ID.
            fallback_id: Returned when resolution fails.

        Returns:
            A project ID string, or fallback_id, or None.
        """
        if not hint:
            return fallback_id

        try:
            # Direct ID lookup
            if hint.startswith("PROJ-"):
                project = await self._project_service.get_project(session, hint)
                return project.id

            # Name-based search
            matches = await self._project_service.find_by_name(session, hint, limit=1)
            if matches:
                return matches[0].id
        except ProjectNotFoundError:
            logger.debug("Project not found for hint %r", hint)
        except Exception:
            logger.warning("Error resolving project hint %r", hint, exc_info=True)

        return fallback_id
