"""Shared test fixtures with async SQLite database for isolation."""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from jarvis.api.dependencies import init_dependencies_with_db, reset_dependencies
from jarvis.config import JarvisConfig
from jarvis.db.engine import Database
from jarvis.db.tables import Base
from jarvis.main import create_app


@pytest.fixture
def config() -> JarvisConfig:
    return JarvisConfig()


@pytest.fixture
async def db() -> Database:
    """Create an async in-memory SQLite database for tests."""
    database = Database(url="sqlite+aiosqlite://")
    async with database.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield database  # type: ignore[misc]
    await database.disconnect()


@pytest.fixture
async def db_session(db: Database) -> AsyncSession:
    """Yield a database session for direct service tests."""
    async with db.session() as session:
        yield session  # type: ignore[misc]


@pytest.fixture
def app(db: Database, config: JarvisConfig):  # type: ignore[no-untyped-def]
    reset_dependencies()
    init_dependencies_with_db(db)
    return create_app(config)


@pytest.fixture
async def client(app):  # type: ignore[no-untyped-def]
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    reset_dependencies()


@pytest.fixture(autouse=True)
def _clear_news_cache() -> None:
    """News reports are cached per (query, day); keep tests independent."""
    from jarvis.services import news_search

    news_search._cache.clear()
