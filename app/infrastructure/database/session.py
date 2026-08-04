"""
Database session factory — supports SQLite (dev), PostgreSQL, MySQL, MSSQL, Oracle via DATABASE_URL.
Uses SQLAlchemy v2 Async Engine.
"""
from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import settings


def _build_engine(database_url: str) -> AsyncEngine:
    """
    Factory that creates an async engine based on the DATABASE_URL scheme.
    Supports:
      - sqlite+aiosqlite://  (local dev)
      - postgresql+asyncpg://
      - mysql+aiomysql://
    """
    connect_args: dict = {}

    if database_url.startswith("sqlite"):
        # SQLite requires check_same_thread=False for async usage
        connect_args = {"check_same_thread": False}
        return create_async_engine(
            database_url,
            connect_args=connect_args,
            echo=settings.DEBUG,
        )

    # PostgreSQL / MySQL / others
    return create_async_engine(
        database_url,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
        echo=settings.DEBUG,
    )


# Module-level engine and session factory (created once at startup)
engine: AsyncEngine = _build_engine(settings.DATABASE_URL)

AsyncSessionFactory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields an async database session.
    Automatically commits on success and rolls back on exception.
    """
    async with AsyncSessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
