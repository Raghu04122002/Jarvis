"""Memory API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from jarvis.api.dependencies import get_memory_service, get_session
from jarvis.models.memory import (
    CreateMemoryRequest,
    Memory,
    MemoryNotFoundError,
    MemorySummary,
    MemoryType,
    UpdateMemoryRequest,
)

router = APIRouter()


def _not_found(memory_id: str) -> HTTPException:
    return HTTPException(status_code=404, detail=f"Memory not found: {memory_id}")


@router.post("/memories")
async def create_memory(
    request: CreateMemoryRequest,
    session: AsyncSession = Depends(get_session),
) -> Memory:
    """Create a new memory entry."""
    service = get_memory_service()
    return await service.create_memory(
        session,
        memory_type=request.memory_type,
        key=request.key,
        content=request.content,
        project_id=request.project_id,
        tags=request.tags,
        metadata=request.metadata,
    )


@router.get("/memories")
async def list_memories(
    memory_type: MemoryType | None = None,
    project_id: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
) -> list[MemorySummary]:
    """List memories with optional filtering."""
    service = get_memory_service()
    return await service.list_memories(
        session, memory_type=memory_type, project_id=project_id, limit=limit
    )


@router.get("/memories/search")
async def search_memories(
    q: str = Query(min_length=1),
    memory_type: MemoryType | None = None,
    project_id: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
) -> list[Memory]:
    """Search memories by content and key."""
    service = get_memory_service()
    return await service.search(
        session, q, memory_type=memory_type, project_id=project_id, limit=limit
    )


@router.get("/memories/{memory_id}")
async def get_memory(
    memory_id: str,
    session: AsyncSession = Depends(get_session),
) -> Memory:
    """Get full memory details."""
    service = get_memory_service()
    try:
        return await service.get_memory(session, memory_id)
    except MemoryNotFoundError:
        raise _not_found(memory_id)


@router.patch("/memories/{memory_id}")
async def update_memory(
    memory_id: str,
    request: UpdateMemoryRequest,
    session: AsyncSession = Depends(get_session),
) -> Memory:
    """Update memory fields."""
    service = get_memory_service()
    fields = request.model_dump(exclude_unset=True)
    if not fields:
        raise HTTPException(status_code=422, detail="No fields to update")
    try:
        return await service.update_memory(session, memory_id, **fields)
    except MemoryNotFoundError:
        raise _not_found(memory_id)


@router.delete("/memories/{memory_id}", status_code=204)
async def delete_memory(
    memory_id: str,
    session: AsyncSession = Depends(get_session),
) -> Response:
    """Delete a memory entry."""
    service = get_memory_service()
    try:
        await service.delete_memory(session, memory_id)
    except MemoryNotFoundError:
        raise _not_found(memory_id)
    return Response(status_code=204)
