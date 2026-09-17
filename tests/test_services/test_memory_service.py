"""Tests for the MemoryService with async database persistence."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from jarvis.db.engine import Database
from jarvis.db.tables import Base
from jarvis.events import Event, EventBus, EventType
from jarvis.models.memory import MemoryNotFoundError, MemoryScope, MemoryType
from jarvis.services.memory_service import MemoryService


@pytest.fixture
def event_bus() -> EventBus:
    return EventBus()


@pytest.fixture
def service(event_bus: EventBus) -> MemoryService:
    return MemoryService(event_bus)


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


class TestCreateMemory:
    @pytest.mark.asyncio
    async def test_create_returns_memory(
        self, service: MemoryService, session: AsyncSession
    ) -> None:
        mem = await service.create_memory(
            session,
            memory_type=MemoryType.USER_PREFERENCE,
            key="editor",
            content="vim",
        )
        assert mem.id.startswith("MEM-")
        assert mem.memory_type == MemoryType.USER_PREFERENCE
        assert mem.key == "editor"
        assert mem.content == "vim"
        assert mem.scope == MemoryScope.GLOBAL
        assert mem.version == 1

    @pytest.mark.asyncio
    async def test_create_with_project_sets_project_scope(
        self, service: MemoryService, session: AsyncSession
    ) -> None:
        mem = await service.create_memory(
            session,
            memory_type=MemoryType.PROJECT_MEMORY,
            key="stack",
            content="Python + FastAPI",
            project_id="proj-1",
        )
        assert mem.scope == MemoryScope.PROJECT
        assert mem.project_id == "proj-1"

    @pytest.mark.asyncio
    async def test_create_with_tags_and_metadata(
        self, service: MemoryService, session: AsyncSession
    ) -> None:
        mem = await service.create_memory(
            session,
            memory_type=MemoryType.DECISION,
            key="db-choice",
            content="Use PostgreSQL",
            tags=["architecture", "database"],
            metadata={"reason": "better JSON support"},
        )
        assert mem.tags == ["architecture", "database"]
        assert mem.metadata == {"reason": "better JSON support"}

    @pytest.mark.asyncio
    async def test_unique_ids(
        self, service: MemoryService, session: AsyncSession
    ) -> None:
        m1 = await service.create_memory(
            session, memory_type=MemoryType.USER_PREFERENCE, key="a", content="a"
        )
        m2 = await service.create_memory(
            session, memory_type=MemoryType.USER_PREFERENCE, key="b", content="b"
        )
        assert m1.id != m2.id


class TestGetMemory:
    @pytest.mark.asyncio
    async def test_get_existing(
        self, service: MemoryService, session: AsyncSession
    ) -> None:
        created = await service.create_memory(
            session, memory_type=MemoryType.USER_PREFERENCE, key="a", content="a"
        )
        fetched = await service.get_memory(session, created.id)
        assert fetched.id == created.id
        assert fetched.content == "a"

    @pytest.mark.asyncio
    async def test_get_not_found(
        self, service: MemoryService, session: AsyncSession
    ) -> None:
        with pytest.raises(MemoryNotFoundError):
            await service.get_memory(session, "nonexistent")


class TestGetByKey:
    @pytest.mark.asyncio
    async def test_get_by_key(
        self, service: MemoryService, session: AsyncSession
    ) -> None:
        await service.create_memory(
            session, memory_type=MemoryType.USER_PREFERENCE, key="theme", content="dark"
        )
        fetched = await service.get_by_key(session, "theme")
        assert fetched.content == "dark"

    @pytest.mark.asyncio
    async def test_get_by_key_with_type_filter(
        self, service: MemoryService, session: AsyncSession
    ) -> None:
        await service.create_memory(
            session, memory_type=MemoryType.USER_PREFERENCE, key="theme", content="dark"
        )
        await service.create_memory(
            session, memory_type=MemoryType.DECISION, key="theme", content="light theme chosen"
        )
        fetched = await service.get_by_key(
            session, "theme", memory_type=MemoryType.DECISION
        )
        assert fetched.content == "light theme chosen"

    @pytest.mark.asyncio
    async def test_get_by_key_with_project_filter(
        self, service: MemoryService, session: AsyncSession
    ) -> None:
        await service.create_memory(
            session, memory_type=MemoryType.PROJECT_MEMORY, key="stack",
            content="global stack", project_id=None,
        )
        await service.create_memory(
            session, memory_type=MemoryType.PROJECT_MEMORY, key="stack",
            content="project stack", project_id="proj-1",
        )
        fetched = await service.get_by_key(session, "stack", project_id="proj-1")
        assert fetched.content == "project stack"

    @pytest.mark.asyncio
    async def test_get_by_key_not_found(
        self, service: MemoryService, session: AsyncSession
    ) -> None:
        with pytest.raises(MemoryNotFoundError):
            await service.get_by_key(session, "nonexistent")


class TestListMemories:
    @pytest.mark.asyncio
    async def test_list_empty(
        self, service: MemoryService, session: AsyncSession
    ) -> None:
        result = await service.list_memories(session)
        assert result == []

    @pytest.mark.asyncio
    async def test_list_returns_summaries(
        self, service: MemoryService, session: AsyncSession
    ) -> None:
        await service.create_memory(
            session, memory_type=MemoryType.USER_PREFERENCE, key="a", content="a"
        )
        await service.create_memory(
            session, memory_type=MemoryType.DECISION, key="b", content="b"
        )
        result = await service.list_memories(session)
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_list_filter_by_type(
        self, service: MemoryService, session: AsyncSession
    ) -> None:
        await service.create_memory(
            session, memory_type=MemoryType.USER_PREFERENCE, key="a", content="a"
        )
        await service.create_memory(
            session, memory_type=MemoryType.DECISION, key="b", content="b"
        )
        result = await service.list_memories(
            session, memory_type=MemoryType.DECISION
        )
        assert len(result) == 1
        assert result[0].key == "b"

    @pytest.mark.asyncio
    async def test_list_filter_by_project(
        self, service: MemoryService, session: AsyncSession
    ) -> None:
        await service.create_memory(
            session, memory_type=MemoryType.PROJECT_MEMORY, key="a",
            content="a", project_id="proj-1",
        )
        await service.create_memory(
            session, memory_type=MemoryType.PROJECT_MEMORY, key="b",
            content="b", project_id="proj-2",
        )
        result = await service.list_memories(session, project_id="proj-1")
        assert len(result) == 1
        assert result[0].key == "a"

    @pytest.mark.asyncio
    async def test_list_filter_by_tags(
        self, service: MemoryService, session: AsyncSession
    ) -> None:
        await service.create_memory(
            session, memory_type=MemoryType.DECISION, key="a",
            content="a", tags=["arch", "db"],
        )
        await service.create_memory(
            session, memory_type=MemoryType.DECISION, key="b",
            content="b", tags=["arch"],
        )
        await service.create_memory(
            session, memory_type=MemoryType.DECISION, key="c",
            content="c", tags=["other"],
        )
        result = await service.list_memories(session, tags=["arch"])
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_list_respects_limit(
        self, service: MemoryService, session: AsyncSession
    ) -> None:
        for i in range(5):
            await service.create_memory(
                session, memory_type=MemoryType.USER_PREFERENCE,
                key=f"k{i}", content=f"c{i}",
            )
        result = await service.list_memories(session, limit=3)
        assert len(result) == 3


class TestSearch:
    @pytest.mark.asyncio
    async def test_search_by_content(
        self, service: MemoryService, session: AsyncSession
    ) -> None:
        await service.create_memory(
            session, memory_type=MemoryType.DECISION, key="db",
            content="Use PostgreSQL for persistence",
        )
        await service.create_memory(
            session, memory_type=MemoryType.DECISION, key="cache",
            content="Use Redis for caching",
        )
        result = await service.search(session, "PostgreSQL")
        assert len(result) == 1
        assert result[0].key == "db"

    @pytest.mark.asyncio
    async def test_search_by_key(
        self, service: MemoryService, session: AsyncSession
    ) -> None:
        await service.create_memory(
            session, memory_type=MemoryType.DECISION, key="postgresql-choice",
            content="Decided to use PG",
        )
        result = await service.search(session, "postgresql")
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_search_no_results(
        self, service: MemoryService, session: AsyncSession
    ) -> None:
        result = await service.search(session, "nonexistent")
        assert result == []

    @pytest.mark.asyncio
    async def test_search_filter_by_type(
        self, service: MemoryService, session: AsyncSession
    ) -> None:
        await service.create_memory(
            session, memory_type=MemoryType.DECISION, key="a",
            content="Use Python",
        )
        await service.create_memory(
            session, memory_type=MemoryType.USER_PREFERENCE, key="b",
            content="Python 3.12",
        )
        result = await service.search(
            session, "Python", memory_type=MemoryType.DECISION
        )
        assert len(result) == 1
        assert result[0].key == "a"

    @pytest.mark.asyncio
    async def test_search_filter_by_tags(
        self, service: MemoryService, session: AsyncSession
    ) -> None:
        await service.create_memory(
            session, memory_type=MemoryType.DECISION, key="a",
            content="Use Python", tags=["lang"],
        )
        await service.create_memory(
            session, memory_type=MemoryType.DECISION, key="b",
            content="Use Python too", tags=["other"],
        )
        result = await service.search(session, "Python", tags=["lang"])
        assert len(result) == 1
        assert result[0].key == "a"


class TestUpdateMemory:
    @pytest.mark.asyncio
    async def test_update_content(
        self, service: MemoryService, session: AsyncSession
    ) -> None:
        mem = await service.create_memory(
            session, memory_type=MemoryType.USER_PREFERENCE, key="editor",
            content="vim",
        )
        updated = await service.update_memory(session, mem.id, content="neovim")
        assert updated.content == "neovim"
        assert updated.version == 2

    @pytest.mark.asyncio
    async def test_update_tags(
        self, service: MemoryService, session: AsyncSession
    ) -> None:
        mem = await service.create_memory(
            session, memory_type=MemoryType.DECISION, key="a",
            content="a", tags=["old"],
        )
        updated = await service.update_memory(session, mem.id, tags=["new", "tags"])
        assert updated.tags == ["new", "tags"]

    @pytest.mark.asyncio
    async def test_update_metadata(
        self, service: MemoryService, session: AsyncSession
    ) -> None:
        mem = await service.create_memory(
            session, memory_type=MemoryType.DECISION, key="a", content="a",
        )
        updated = await service.update_memory(
            session, mem.id, metadata={"source": "user"}
        )
        assert updated.metadata == {"source": "user"}

    @pytest.mark.asyncio
    async def test_update_not_found(
        self, service: MemoryService, session: AsyncSession
    ) -> None:
        with pytest.raises(MemoryNotFoundError):
            await service.update_memory(session, "nonexistent", content="x")

    @pytest.mark.asyncio
    async def test_update_increments_version(
        self, service: MemoryService, session: AsyncSession
    ) -> None:
        mem = await service.create_memory(
            session, memory_type=MemoryType.USER_PREFERENCE, key="a", content="a",
        )
        assert mem.version == 1
        updated = await service.update_memory(session, mem.id, content="b")
        assert updated.version == 2
        updated2 = await service.update_memory(session, updated.id, content="c")
        assert updated2.version == 3


class TestDeleteMemory:
    @pytest.mark.asyncio
    async def test_delete_existing(
        self, service: MemoryService, session: AsyncSession
    ) -> None:
        mem = await service.create_memory(
            session, memory_type=MemoryType.USER_PREFERENCE, key="a", content="a",
        )
        await service.delete_memory(session, mem.id)
        with pytest.raises(MemoryNotFoundError):
            await service.get_memory(session, mem.id)

    @pytest.mark.asyncio
    async def test_delete_not_found(
        self, service: MemoryService, session: AsyncSession
    ) -> None:
        with pytest.raises(MemoryNotFoundError):
            await service.delete_memory(session, "nonexistent")


class TestRetrieveContext:
    @pytest.mark.asyncio
    async def test_retrieve_global_memories(
        self, service: MemoryService, session: AsyncSession
    ) -> None:
        await service.create_memory(
            session, memory_type=MemoryType.USER_PREFERENCE, key="lang",
            content="Always use Python",
        )
        result = await service.retrieve_context(session, "Python")
        assert len(result) == 1
        assert result[0].content == "Always use Python"

    @pytest.mark.asyncio
    async def test_retrieve_project_first(
        self, service: MemoryService, session: AsyncSession
    ) -> None:
        await service.create_memory(
            session, memory_type=MemoryType.USER_PREFERENCE, key="global-pref",
            content="Use Python globally",
        )
        await service.create_memory(
            session, memory_type=MemoryType.PROJECT_MEMORY, key="project-pref",
            content="Use Python in project", project_id="proj-1",
        )
        result = await service.retrieve_context(
            session, "Python", project_id="proj-1"
        )
        assert len(result) == 2
        # Project-scoped should come first
        assert result[0].project_id == "proj-1"

    @pytest.mark.asyncio
    async def test_retrieve_respects_limit(
        self, service: MemoryService, session: AsyncSession
    ) -> None:
        for i in range(15):
            await service.create_memory(
                session, memory_type=MemoryType.USER_PREFERENCE,
                key=f"pref-{i}", content=f"Python preference {i}",
            )
        result = await service.retrieve_context(session, "Python", limit=5)
        assert len(result) == 5

    @pytest.mark.asyncio
    async def test_retrieve_no_duplicates(
        self, service: MemoryService, session: AsyncSession
    ) -> None:
        # A global memory should not appear twice
        await service.create_memory(
            session, memory_type=MemoryType.USER_PREFERENCE, key="pref",
            content="Use Python",
        )
        result = await service.retrieve_context(
            session, "Python", project_id="proj-1"
        )
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_retrieve_empty(
        self, service: MemoryService, session: AsyncSession
    ) -> None:
        result = await service.retrieve_context(session, "nonexistent")
        assert result == []


class TestEvents:
    @pytest.mark.asyncio
    async def test_create_publishes_event(
        self, service: MemoryService, session: AsyncSession, event_bus: EventBus
    ) -> None:
        events: list[Event] = []
        event_bus.subscribe(EventType.MEMORY_CREATED, events.append)
        mem = await service.create_memory(
            session, memory_type=MemoryType.USER_PREFERENCE, key="a", content="a",
        )
        assert len(events) == 1
        assert events[0].task_id == mem.id

    @pytest.mark.asyncio
    async def test_update_publishes_event(
        self, service: MemoryService, session: AsyncSession, event_bus: EventBus
    ) -> None:
        events: list[Event] = []
        event_bus.subscribe(EventType.MEMORY_UPDATED, events.append)
        mem = await service.create_memory(
            session, memory_type=MemoryType.USER_PREFERENCE, key="a", content="a",
        )
        await service.update_memory(session, mem.id, content="b")
        assert len(events) == 1
        assert events[0].task_id == mem.id

    @pytest.mark.asyncio
    async def test_delete_publishes_event(
        self, service: MemoryService, session: AsyncSession, event_bus: EventBus
    ) -> None:
        events: list[Event] = []
        event_bus.subscribe(EventType.MEMORY_DELETED, events.append)
        mem = await service.create_memory(
            session, memory_type=MemoryType.USER_PREFERENCE, key="a", content="a",
        )
        await service.delete_memory(session, mem.id)
        assert len(events) == 1
        assert events[0].task_id == mem.id


class TestPersistence:
    @pytest.mark.asyncio
    async def test_memory_persists_across_sessions(
        self, service: MemoryService, svc_db: Database
    ) -> None:
        # Create in one session
        async with svc_db.session() as s1:
            mem = await service.create_memory(
                s1, memory_type=MemoryType.USER_PREFERENCE, key="persist-test",
                content="persisted value",
            )
            await s1.commit()

        # Read in another session
        async with svc_db.session() as s2:
            fetched = await service.get_memory(s2, mem.id)
            assert fetched.content == "persisted value"
