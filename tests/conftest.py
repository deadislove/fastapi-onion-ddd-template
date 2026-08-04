"""
Pytest configuration and shared fixtures for integration tests.
Uses an in-memory SQLite database for fast, isolated tests.
"""
from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.application.services.auth_service import AuthService, ITokenRevocationStore
from app.application.services.event_dispatcher import IEventDispatcher
from app.domain.events import DomainEvent
from app.infrastructure.database.models import Base
from app.infrastructure.database.session import get_db_session
from app.infrastructure.dependencies import (
    _password_hasher,
    _token_service,
    get_auth_service,
    get_event_dispatcher,
)
from app.infrastructure.security.rate_limiter import limiter
from app.main import app


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """slowapi's Limiter is a process-wide singleton — reset its counters before each
    test so one test's requests don't push a later test over the per-route limit."""
    limiter.reset()
    yield


class _FakeTokenRevocationStore(ITokenRevocationStore):
    """In-memory stand-in for RedisTokenRevocationStore — keeps tests hermetic (no Redis needed)."""

    def __init__(self) -> None:
        self._revoked: set[str] = set()

    async def revoke(self, jti: str, ttl_seconds: int) -> None:
        self._revoked.add(jti)

    async def is_revoked(self, jti: str) -> bool:
        return jti in self._revoked


class _CapturingEventDispatcher(IEventDispatcher):
    """Records every published domain event in-memory so tests can assert on them,
    instead of only trusting that LoggingEventDispatcher was wired up correctly."""

    def __init__(self) -> None:
        self.events: list[DomainEvent] = []

    async def publish(self, event: DomainEvent) -> None:
        self.events.append(event)


@pytest.fixture
def captured_events() -> _CapturingEventDispatcher:
    return _CapturingEventDispatcher()


# ─── Test Database Setup ──────────────────────────────────────────────────────
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False,
)

TestSessionFactory = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def create_test_tables():
    """Create all tables once per test session."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def rollback_after_test():
    """Wrap each test in a transaction that is rolled back after the test."""
    async with test_engine.connect() as conn:
        await conn.begin()
        session = AsyncSession(bind=conn, expire_on_commit=False)
        try:
            yield session
        finally:
            await session.close()
            await conn.rollback()


@pytest_asyncio.fixture
async def db_session(rollback_after_test: AsyncSession) -> AsyncSession:
    """Provide the test database session."""
    return rollback_after_test


@pytest_asyncio.fixture
async def client(db_session: AsyncSession, captured_events: _CapturingEventDispatcher) -> AsyncClient:
    """
    Provide an async HTTP test client with the test DB session injected.
    """
    async def override_get_db():
        yield db_session

    # One store per test (not per request) so revocation state persists across the
    # multiple HTTP calls a single test makes (e.g. login -> refresh -> reuse old token).
    revocation_store = _FakeTokenRevocationStore()

    def override_get_auth_service() -> AuthService:
        return AuthService(
            password_hasher=_password_hasher,
            token_service=_token_service,
            revocation_store=revocation_store,
        )

    app.dependency_overrides[get_db_session] = override_get_db
    app.dependency_overrides[get_auth_service] = override_get_auth_service
    app.dependency_overrides[get_event_dispatcher] = lambda: captured_events

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
