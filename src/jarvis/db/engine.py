"""Database engine and session management."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from jarvis.config import DatabaseConfig

logger = logging.getLogger(__name__)


class Database:
    """Async database connection manager.

    Usage:
        db = Database(config.database)
        await db.connect()
        async with db.session() as session:
            ...
        await db.disconnect()
    """

    def __init__(self, config: DatabaseConfig | None = None, *, url: str = "") -> None:
        if url:
            db_url = url
        elif config is not None:
            db_url = config.async_url
        else:
            raise ValueError("Either config or url must be provided")

        # SQLite needs special connect_args for async
        connect_args: dict[str, bool] = {}
        if db_url.startswith("sqlite"):
            connect_args = {"check_same_thread": False}

        self._engine: AsyncEngine = create_async_engine(
            db_url,
            echo=False,
            pool_pre_ping=not db_url.startswith("sqlite"),
            connect_args=connect_args,
        )
        self._session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
            self._engine,
            expire_on_commit=False,
        )

    async def connect(self) -> None:
        """Verify the database connection."""
        logger.info("Database engine ready")

    async def disconnect(self) -> None:
        """Close all database connections."""
        await self._engine.dispose()
        logger.info("Database connections closed")

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        """Yield an async database session."""
        async with self._session_factory() as session:
            yield session

    @property
    def engine(self) -> AsyncEngine:
        return self._engine
