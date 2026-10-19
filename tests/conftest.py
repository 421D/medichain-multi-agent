"""Shared pytest fixtures — SQLite in-memory async DB + FastAPI test client."""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.models import Base

# In-memory SQLite — isolated per test session, no PostgreSQL needed
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(TEST_DB_URL, echo=False)
TestSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture
async def db():
    """Yield a fresh async DB session with all tables created."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with TestSessionLocal() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client(db: AsyncSession):
    """Yield an httpx AsyncClient wired to the FastAPI app with test DB."""
    from fastapi import FastAPI
    from app.api.routes import session as session_routes
    from app.api.routes import agents as agents_routes

    app = FastAPI()
    app.include_router(session_routes.router)
    app.include_router(agents_routes.router)

    # Override the DB dependency to use our test session
    from app.db.database import get_db

    async def _override_get_db():
        async with TestSessionLocal() as s:
            yield s

    app.dependency_overrides[get_db] = _override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
