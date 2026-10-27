"""Tests for the project resolver."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from jarvis.models.project import Project, ProjectNotFoundError
from jarvis.orchestrator.resolver import ProjectResolver
from jarvis.services.project_service import ProjectService


def _mock_project(project_id: str = "PROJ-abc123", name: str = "TestProject") -> Project:
    return Project(id=project_id, name=name, local_path="/test")


@pytest.fixture
def mock_service() -> MagicMock:
    return MagicMock(spec=ProjectService)


@pytest.fixture
def session() -> AsyncMock:
    return AsyncMock(spec=AsyncSession)


class TestProjectResolver:
    @pytest.mark.asyncio
    async def test_none_hint_returns_fallback(
        self, mock_service: MagicMock, session: AsyncMock
    ) -> None:
        resolver = ProjectResolver(mock_service)
        result = await resolver.resolve(session, None, fallback_id="PROJ-fallback")
        assert result == "PROJ-fallback"

    @pytest.mark.asyncio
    async def test_empty_hint_returns_fallback(
        self, mock_service: MagicMock, session: AsyncMock
    ) -> None:
        resolver = ProjectResolver(mock_service)
        result = await resolver.resolve(session, "", fallback_id="PROJ-fb")
        assert result == "PROJ-fb"

    @pytest.mark.asyncio
    async def test_proj_id_exact_lookup(
        self, mock_service: MagicMock, session: AsyncMock
    ) -> None:
        project = _mock_project("PROJ-exact")
        mock_service.get_project = AsyncMock(return_value=project)
        resolver = ProjectResolver(mock_service)
        result = await resolver.resolve(session, "PROJ-exact")
        assert result == "PROJ-exact"
        mock_service.get_project.assert_awaited_once_with(session, "PROJ-exact")

    @pytest.mark.asyncio
    async def test_name_substring_lookup(
        self, mock_service: MagicMock, session: AsyncMock
    ) -> None:
        project = _mock_project("PROJ-found", "MinaarTech")
        mock_service.find_by_name = AsyncMock(return_value=[project])
        resolver = ProjectResolver(mock_service)
        result = await resolver.resolve(session, "MinaarTech")
        assert result == "PROJ-found"

    @pytest.mark.asyncio
    async def test_name_not_found_returns_fallback(
        self, mock_service: MagicMock, session: AsyncMock
    ) -> None:
        mock_service.find_by_name = AsyncMock(return_value=[])
        resolver = ProjectResolver(mock_service)
        result = await resolver.resolve(session, "NoMatch", fallback_id="PROJ-fb")
        assert result == "PROJ-fb"

    @pytest.mark.asyncio
    async def test_name_not_found_returns_none(
        self, mock_service: MagicMock, session: AsyncMock
    ) -> None:
        mock_service.find_by_name = AsyncMock(return_value=[])
        resolver = ProjectResolver(mock_service)
        result = await resolver.resolve(session, "NoMatch")
        assert result is None

    @pytest.mark.asyncio
    async def test_proj_id_not_found(
        self, mock_service: MagicMock, session: AsyncMock
    ) -> None:
        mock_service.get_project = AsyncMock(
            side_effect=ProjectNotFoundError("PROJ-missing")
        )
        resolver = ProjectResolver(mock_service)
        result = await resolver.resolve(session, "PROJ-missing", fallback_id="PROJ-fb")
        assert result == "PROJ-fb"

    @pytest.mark.asyncio
    async def test_exception_returns_fallback(
        self, mock_service: MagicMock, session: AsyncMock
    ) -> None:
        mock_service.find_by_name = AsyncMock(side_effect=RuntimeError("db error"))
        resolver = ProjectResolver(mock_service)
        result = await resolver.resolve(session, "Boom", fallback_id="PROJ-safe")
        assert result == "PROJ-safe"
