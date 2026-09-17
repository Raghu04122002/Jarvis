"""Memory service — manages persistent memory entries with database persistence.

All memory business logic lives here, not in API route handlers.
"""

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Text, cast, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from jarvis.db.tables import MemoryRow
from jarvis.events import Event, EventBus, EventType
from jarvis.models.memory import (
    Memory,
    MemoryNotFoundError,
    MemoryScope,
    MemorySummary,
    MemoryType,
)

logger = logging.getLogger(__name__)


def _row_to_memory(row: MemoryRow) -> Memory:
    """Convert a database row to a Memory domain model."""
    return Memory(
        id=row.id,
        memory_type=MemoryType(row.memory_type),
        scope=MemoryScope(row.scope),
        project_id=row.project_id,
        key=row.key,
        content=row.content,
        tags=row.tags if isinstance(row.tags, list) else [],
        metadata=row.metadata_ if isinstance(row.metadata_, dict) else {},
        version=row.version,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _row_to_summary(row: MemoryRow) -> MemorySummary:
    """Convert a database row to a MemorySummary."""
    return MemorySummary(
        id=row.id,
        memory_type=MemoryType(row.memory_type),
        scope=MemoryScope(row.scope),
        project_id=row.project_id,
        key=row.key,
        tags=row.tags if isinstance(row.tags, list) else [],
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class MemoryService:
    """Manages memory creation, retrieval, search, and updates.

    Uses async database persistence via SQLAlchemy.
    """

    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus

    def _next_id(self) -> str:
        return f"MEM-{uuid.uuid4().hex[:8]}"

    async def create_memory(
        self,
        session: AsyncSession,
        memory_type: MemoryType,
        key: str,
        content: str,
        *,
        project_id: str | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Memory:
        now = datetime.now(UTC)
        memory_id = self._next_id()
        scope = MemoryScope.PROJECT if project_id else MemoryScope.GLOBAL
        row = MemoryRow(
            id=memory_id,
            memory_type=memory_type.value,
            scope=scope.value,
            project_id=project_id,
            key=key,
            content=content,
            tags=tags or [],
            metadata_=metadata or {},
            version=1,
            created_at=now,
            updated_at=now,
        )
        session.add(row)
        await session.flush()
        memory = _row_to_memory(row)
        self._event_bus.publish(
            Event(type=EventType.MEMORY_CREATED, task_id=memory_id)
        )
        return memory

    async def get_memory(self, session: AsyncSession, memory_id: str) -> Memory:
        row = await session.get(MemoryRow, memory_id)
        if row is None:
            raise MemoryNotFoundError(memory_id)
        return _row_to_memory(row)

    async def get_by_key(
        self,
        session: AsyncSession,
        key: str,
        *,
        memory_type: MemoryType | None = None,
        project_id: str | None = None,
    ) -> Memory:
        stmt = select(MemoryRow).where(MemoryRow.key == key)
        if memory_type is not None:
            stmt = stmt.where(MemoryRow.memory_type == memory_type.value)
        if project_id is not None:
            stmt = stmt.where(MemoryRow.project_id == project_id)
        result = await session.execute(stmt)
        row = result.scalars().first()
        if row is None:
            raise MemoryNotFoundError(key)
        return _row_to_memory(row)

    async def list_memories(
        self,
        session: AsyncSession,
        *,
        memory_type: MemoryType | None = None,
        project_id: str | None = None,
        tags: list[str] | None = None,
        limit: int = 50,
    ) -> list[MemorySummary]:
        stmt = select(MemoryRow)
        if memory_type is not None:
            stmt = stmt.where(MemoryRow.memory_type == memory_type.value)
        if project_id is not None:
            stmt = stmt.where(MemoryRow.project_id == project_id)
        if tags:
            for tag in tags:
                stmt = stmt.where(
                    cast(MemoryRow.tags, Text).ilike(f'%"{tag}"%')
                )
        stmt = stmt.order_by(MemoryRow.updated_at.desc()).limit(limit)
        result = await session.execute(stmt)
        rows = result.scalars().all()
        return [_row_to_summary(r) for r in rows]

    async def search(
        self,
        session: AsyncSession,
        query: str,
        *,
        memory_type: MemoryType | None = None,
        project_id: str | None = None,
        tags: list[str] | None = None,
        limit: int = 20,
    ) -> list[Memory]:
        pattern = f"%{query}%"
        stmt = select(MemoryRow).where(
            or_(
                MemoryRow.content.ilike(pattern),
                MemoryRow.key.ilike(pattern),
            )
        )
        if memory_type is not None:
            stmt = stmt.where(MemoryRow.memory_type == memory_type.value)
        if project_id is not None:
            stmt = stmt.where(MemoryRow.project_id == project_id)
        if tags:
            for tag in tags:
                stmt = stmt.where(
                    cast(MemoryRow.tags, Text).ilike(f'%"{tag}"%')
                )
        stmt = stmt.order_by(MemoryRow.updated_at.desc()).limit(limit)
        result = await session.execute(stmt)
        rows = result.scalars().all()
        return [_row_to_memory(r) for r in rows]

    async def update_memory(
        self,
        session: AsyncSession,
        memory_id: str,
        *,
        content: str | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Memory:
        row = await session.get(MemoryRow, memory_id)
        if row is None:
            raise MemoryNotFoundError(memory_id)

        if content is not None:
            row.content = content
        if tags is not None:
            row.tags = tags
        if metadata is not None:
            row.metadata_ = metadata

        row.updated_at = datetime.now(UTC)
        row.version += 1
        await session.flush()

        self._event_bus.publish(
            Event(type=EventType.MEMORY_UPDATED, task_id=memory_id)
        )
        return _row_to_memory(row)

    async def delete_memory(self, session: AsyncSession, memory_id: str) -> None:
        row = await session.get(MemoryRow, memory_id)
        if row is None:
            raise MemoryNotFoundError(memory_id)
        await session.delete(row)
        await session.flush()
        self._event_bus.publish(
            Event(type=EventType.MEMORY_DELETED, task_id=memory_id)
        )

    async def retrieve_context(
        self,
        session: AsyncSession,
        query: str,
        *,
        project_id: str | None = None,
        limit: int = 10,
    ) -> list[Memory]:
        """Retrieve relevant memories for context injection.

        Searches project-scoped memories first, then global.
        Project results come first, deduped, capped at limit.
        """
        pattern = f"%{query}%"
        results: list[Memory] = []
        seen_ids: set[str] = set()

        # Project-scoped memories first
        if project_id:
            stmt = (
                select(MemoryRow)
                .where(
                    or_(
                        MemoryRow.content.ilike(pattern),
                        MemoryRow.key.ilike(pattern),
                    )
                )
                .where(MemoryRow.project_id == project_id)
                .order_by(MemoryRow.updated_at.desc())
                .limit(limit)
            )
            result = await session.execute(stmt)
            for row in result.scalars().all():
                if row.id not in seen_ids:
                    results.append(_row_to_memory(row))
                    seen_ids.add(row.id)

        # Global memories
        if len(results) < limit:
            remaining = limit - len(results)
            stmt = (
                select(MemoryRow)
                .where(
                    or_(
                        MemoryRow.content.ilike(pattern),
                        MemoryRow.key.ilike(pattern),
                    )
                )
                .where(MemoryRow.scope == MemoryScope.GLOBAL.value)
                .order_by(MemoryRow.updated_at.desc())
                .limit(remaining)
            )
            result = await session.execute(stmt)
            for row in result.scalars().all():
                if row.id not in seen_ids:
                    results.append(_row_to_memory(row))
                    seen_ids.add(row.id)

        return results[:limit]
