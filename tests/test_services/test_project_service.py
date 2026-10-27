"""Tests for the ProjectService with async database persistence."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from jarvis.db.engine import Database
from jarvis.db.tables import Base
from jarvis.events import EventBus
from jarvis.models.project import ProjectNotFoundError
from jarvis.services.project_service import ProjectService


@pytest.fixture
def event_bus() -> EventBus:
    return EventBus()


@pytest.fixture
def service(event_bus: EventBus) -> ProjectService:
    return ProjectService(event_bus)


@pytest.fixture
async def svc_db() -> Database:
    """Dedicated database for service tests."""
    database = Database(url="sqlite+aiosqlite://")
    async with database.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield database  # type: ignore[misc]
    await database.disconnect()


@pytest.fixture
async def session(svc_db: Database) -> AsyncSession:
    async with svc_db.session() as s:
        yield s  # type: ignore[misc]


class TestCreateProject:
    @pytest.mark.asyncio
    async def test_create_returns_project(
        self, service: ProjectService, session: AsyncSession
    ) -> None:
        project = await service.create_project(
            session, name="Jarvis", local_path="/home/user/jarvis"
        )
        assert project.id.startswith("PROJ-")
        assert project.name == "Jarvis"
        assert project.local_path == "/home/user/jarvis"
        assert project.version == 1

    @pytest.mark.asyncio
    async def test_create_with_all_fields(
        self, service: ProjectService, session: AsyncSession
    ) -> None:
        project = await service.create_project(
            session,
            name="WebApp",
            local_path="/home/user/webapp",
            github_repo="user/webapp",
            default_branch="develop",
            stack=["python", "react"],
            preferred_agent="claude",
            deployment={"env": "production"},
            instructions="Use ruff for linting",
        )
        assert project.github_repo == "user/webapp"
        assert project.default_branch == "develop"
        assert project.stack == ["python", "react"]
        assert project.preferred_agent == "claude"
        assert project.deployment == {"env": "production"}
        assert project.instructions == "Use ruff for linting"

    @pytest.mark.asyncio
    async def test_unique_ids(self, service: ProjectService, session: AsyncSession) -> None:
        p1 = await service.create_project(session, name="A", local_path="/a")
        p2 = await service.create_project(session, name="B", local_path="/b")
        assert p1.id != p2.id


class TestGetProject:
    @pytest.mark.asyncio
    async def test_get_existing(self, service: ProjectService, session: AsyncSession) -> None:
        created = await service.create_project(session, name="A", local_path="/a")
        fetched = await service.get_project(session, created.id)
        assert fetched.id == created.id
        assert fetched.name == "A"

    @pytest.mark.asyncio
    async def test_get_nonexistent(self, service: ProjectService, session: AsyncSession) -> None:
        with pytest.raises(ProjectNotFoundError):
            await service.get_project(session, "PROJ-nonexistent")


class TestListProjects:
    @pytest.mark.asyncio
    async def test_list_empty(self, service: ProjectService, session: AsyncSession) -> None:
        assert await service.list_projects(session) == []

    @pytest.mark.asyncio
    async def test_list_returns_summaries(
        self, service: ProjectService, session: AsyncSession
    ) -> None:
        await service.create_project(session, name="A", local_path="/a")
        await service.create_project(session, name="B", local_path="/b")
        summaries = await service.list_projects(session)
        assert len(summaries) == 2
        assert summaries[0].name in ("A", "B")

    @pytest.mark.asyncio
    async def test_limit(self, service: ProjectService, session: AsyncSession) -> None:
        for i in range(5):
            await service.create_project(session, name=f"P{i}", local_path=f"/{i}")
        assert len(await service.list_projects(session, limit=3)) == 3


class TestFindByName:
    @pytest.mark.asyncio
    async def test_exact_name_match(self, service: ProjectService, session: AsyncSession) -> None:
        await service.create_project(session, name="MinaarTech", local_path="/mt")
        results = await service.find_by_name(session, "MinaarTech")
        assert len(results) == 1
        assert results[0].name == "MinaarTech"

    @pytest.mark.asyncio
    async def test_substring_match(self, service: ProjectService, session: AsyncSession) -> None:
        await service.create_project(session, name="MinaarTech", local_path="/mt")
        results = await service.find_by_name(session, "minaar")
        assert len(results) == 1
        assert results[0].name == "MinaarTech"

    @pytest.mark.asyncio
    async def test_case_insensitive(self, service: ProjectService, session: AsyncSession) -> None:
        await service.create_project(session, name="MinaarTech", local_path="/mt")
        results = await service.find_by_name(session, "MINAARTECH")
        assert len(results) == 1
        assert results[0].name == "MinaarTech"

    @pytest.mark.asyncio
    async def test_no_match_empty_list(
        self, service: ProjectService, session: AsyncSession
    ) -> None:
        await service.create_project(session, name="MinaarTech", local_path="/mt")
        results = await service.find_by_name(session, "NoSuchProject")
        assert results == []

    @pytest.mark.asyncio
    async def test_multiple_matches_ordered(
        self, service: ProjectService, session: AsyncSession
    ) -> None:
        await service.create_project(session, name="AppAlpha", local_path="/a")
        await service.create_project(session, name="AppBeta", local_path="/b")
        await service.create_project(session, name="Other", local_path="/o")
        results = await service.find_by_name(session, "App")
        assert len(results) == 2
        assert results[0].name == "AppAlpha"
        assert results[1].name == "AppBeta"

    @pytest.mark.asyncio
    async def test_limit_respected(self, service: ProjectService, session: AsyncSession) -> None:
        for i in range(5):
            await service.create_project(session, name=f"Proj{i}", local_path=f"/{i}")
        results = await service.find_by_name(session, "Proj", limit=3)
        assert len(results) == 3


class TestUpdateProject:
    @pytest.mark.asyncio
    async def test_update_name(self, service: ProjectService, session: AsyncSession) -> None:
        project = await service.create_project(session, name="Old", local_path="/old")
        updated = await service.update_project(session, project.id, name="New")
        assert updated.name == "New"
        assert updated.version == 2

    @pytest.mark.asyncio
    async def test_update_multiple_fields(
        self, service: ProjectService, session: AsyncSession
    ) -> None:
        project = await service.create_project(session, name="A", local_path="/a")
        updated = await service.update_project(
            session, project.id, stack=["python", "react"], preferred_agent="claude"
        )
        assert updated.stack == ["python", "react"]
        assert updated.preferred_agent == "claude"

    @pytest.mark.asyncio
    async def test_update_nonexistent(
        self, service: ProjectService, session: AsyncSession
    ) -> None:
        with pytest.raises(ProjectNotFoundError):
            await service.update_project(session, "PROJ-nope", name="X")


class TestRemoveProject:
    @pytest.mark.asyncio
    async def test_remove_existing(self, service: ProjectService, session: AsyncSession) -> None:
        project = await service.create_project(session, name="A", local_path="/a")
        await service.remove_project(session, project.id)
        with pytest.raises(ProjectNotFoundError):
            await service.get_project(session, project.id)

    @pytest.mark.asyncio
    async def test_remove_nonexistent(
        self, service: ProjectService, session: AsyncSession
    ) -> None:
        with pytest.raises(ProjectNotFoundError):
            await service.remove_project(session, "PROJ-nope")


class TestPersistence:
    @pytest.mark.asyncio
    async def test_project_persists_across_sessions(
        self, service: ProjectService, svc_db: Database
    ) -> None:
        async with svc_db.session() as s1:
            project = await service.create_project(s1, name="Persist", local_path="/p")
            await s1.commit()
        async with svc_db.session() as s2:
            fetched = await service.get_project(s2, project.id)
            assert fetched.name == "Persist"

    @pytest.mark.asyncio
    async def test_update_persists_across_sessions(
        self, service: ProjectService, svc_db: Database
    ) -> None:
        async with svc_db.session() as s1:
            project = await service.create_project(s1, name="A", local_path="/a")
            await service.update_project(s1, project.id, name="B")
            await s1.commit()
        async with svc_db.session() as s2:
            fetched = await service.get_project(s2, project.id)
            assert fetched.name == "B"
            assert fetched.version == 2

    @pytest.mark.asyncio
    async def test_remove_persists_across_sessions(
        self, service: ProjectService, svc_db: Database
    ) -> None:
        async with svc_db.session() as s1:
            project = await service.create_project(s1, name="A", local_path="/a")
            await s1.commit()
        async with svc_db.session() as s2:
            await service.remove_project(s2, project.id)
            await s2.commit()
        async with svc_db.session() as s3:
            with pytest.raises(ProjectNotFoundError):
                await service.get_project(s3, project.id)
