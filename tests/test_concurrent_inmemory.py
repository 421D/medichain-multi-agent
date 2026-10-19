"""Concurrent request tests against the REST surface (in-memory SQLite)."""
import asyncio

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.database import get_db
from app.db.models import Base


@pytest_asyncio.fixture
async def app_client():
    """Per-test app + in-memory DB. SQLite needs StaticPool + check_same_thread=False
    so all async tasks share one connection (otherwise concurrent writers race against
    SQLite's BEGIN-IMMEDIATE locking). This is a test-only knob; production runs on
    PostgreSQL where pool_size handles concurrency natively."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestSession = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    from app.api.routes import session as session_routes

    app = FastAPI()
    app.include_router(session_routes.router)

    async def _get_db():
        async with TestSession() as s:
            yield s

    app.dependency_overrides[get_db] = _get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.mark.asyncio
async def test_concurrent_session_creates_produce_unique_ids(app_client: AsyncClient):
    """25 simultaneous POSTs must all succeed and yield 25 unique uuids."""
    N = 25
    responses = await asyncio.gather(*(
        app_client.post("/api/v1/sessions/", json={"title": f"Race-{i}"})
        for i in range(N)
    ))
    statuses = [r.status_code for r in responses]
    assert all(s == 200 for s in statuses), f"non-200s: {statuses}"

    ids = [r.json()["id"] for r in responses]
    assert len(set(ids)) == N, "duplicate session ids under concurrency"

    # Authoritative count from the listing endpoint
    listing = (await app_client.get("/api/v1/sessions/")).json()
    assert len(listing) == N


@pytest.mark.asyncio
async def test_parallel_reads_and_writes_are_consistent(app_client: AsyncClient):
    """Mix 10 creates + 10 stat reads concurrently — both classes of request
    must complete (no deadlock, no 5xx) and the final stats reflect the writes."""
    creates = [app_client.post("/api/v1/sessions/", json={"title": f"Mix-{i}"}) for i in range(10)]
    reads = [app_client.get("/api/v1/sessions/stats") for _ in range(10)]
    results = await asyncio.gather(*creates, *reads, return_exceptions=False)

    for r in results:
        assert r.status_code == 200, f"unexpected {r.status_code}: {r.text[:120]}"

    final_stats = (await app_client.get("/api/v1/sessions/stats")).json()
    assert final_stats["total_sessions"] == 10


@pytest.mark.asyncio
async def test_parallel_deletes_of_distinct_sessions(app_client: AsyncClient):
    """Independent deletes don't block each other and the count drops to 0."""
    ids = []
    for i in range(8):
        r = await app_client.post("/api/v1/sessions/", json={"title": f"Del-{i}"})
        ids.append(r.json()["id"])

    deletes = await asyncio.gather(*(app_client.delete(f"/api/v1/sessions/{sid}") for sid in ids))
    assert all(r.status_code == 200 for r in deletes)

    listing = (await app_client.get("/api/v1/sessions/")).json()
    assert listing == []


@pytest.mark.asyncio
async def test_double_delete_one_wins_one_404s(app_client: AsyncClient):
    """The same session deleted concurrently from two callers — exactly one
    delete logically succeeds. The losing caller may see 200 or 404 depending
    on transaction interleaving, but neither should 5xx."""
    sid = (await app_client.post("/api/v1/sessions/", json={"title": "Dup"})).json()["id"]

    a, b = await asyncio.gather(
        app_client.delete(f"/api/v1/sessions/{sid}"),
        app_client.delete(f"/api/v1/sessions/{sid}"),
    )
    statuses = sorted([a.status_code, b.status_code])
    # Both 200 (delete is idempotent at SQL level), or one 200 + one 404. Never 5xx.
    assert statuses in ([200, 200], [200, 404]), f"unexpected statuses {statuses}"

    # And the row really is gone afterwards.
    final = await app_client.get(f"/api/v1/sessions/{sid}")
    assert final.status_code == 404
