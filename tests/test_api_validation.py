"""Input validation tests for the REST API (sessions + agents)."""
import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.database import get_db
from app.db.models import Base


@pytest_asyncio.fixture
async def app_client():
    """Build a fresh app + in-memory DB for each test — no cross-test leakage."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    TestSession = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    from app.api.routes import session as session_routes
    from app.api.routes import agents as agents_routes

    app = FastAPI()
    app.include_router(session_routes.router)
    app.include_router(agents_routes.router)

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
async def test_create_session_uses_defaults_when_body_omitted(app_client: AsyncClient):
    """SessionCreate has defaults for both fields → empty body should still 201."""
    r = await app_client.post("/api/v1/sessions/", json={})
    assert r.status_code == 200
    data = r.json()
    assert data["title"] == "New Consultation"
    assert data["llm_model"] == "gpt-4"
    assert data["status"] == "active"


@pytest.mark.asyncio
async def test_create_session_accepts_explicit_fields(app_client: AsyncClient):
    r = await app_client.post(
        "/api/v1/sessions/",
        json={"title": "Chest pain workup", "llm_model": "kimi"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["title"] == "Chest pain workup"
    assert body["llm_model"] == "kimi"
    assert body["id"]  # uuid present


@pytest.mark.asyncio
async def test_create_session_rejects_wrong_field_type(app_client: AsyncClient):
    """Pydantic must reject `title=42` (not a string) with 422."""
    r = await app_client.post("/api/v1/sessions/", json={"title": 42, "llm_model": "kimi"})
    assert r.status_code == 422
    assert "title" in r.text


@pytest.mark.asyncio
async def test_create_session_handles_unicode_title(app_client: AsyncClient):
    """Medical contexts include Chinese / Spanish — make sure UTF-8 round-trips."""
    payload = {"title": "胸痛 — 病史询问", "llm_model": "kimi"}
    r = await app_client.post("/api/v1/sessions/", json=payload)
    assert r.status_code == 200
    assert r.json()["title"] == payload["title"]


@pytest.mark.asyncio
async def test_get_session_404_on_unknown_id(app_client: AsyncClient):
    r = await app_client.get("/api/v1/sessions/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_get_session_404_on_garbage_id(app_client: AsyncClient):
    """Session id is a string PK; an invalid format is just a non-existent row."""
    r = await app_client.get("/api/v1/sessions/not-a-real-id")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_session_round_trip_create_get_delete(app_client: AsyncClient):
    """Happy path: create → fetch → delete → 404 on subsequent fetch."""
    created = (await app_client.post("/api/v1/sessions/", json={"title": "RT"})).json()
    sid = created["id"]

    fetched = (await app_client.get(f"/api/v1/sessions/{sid}")).json()
    assert fetched["id"] == sid
    assert fetched["title"] == "RT"

    deleted = await app_client.delete(f"/api/v1/sessions/{sid}")
    assert deleted.status_code == 200

    again = await app_client.get(f"/api/v1/sessions/{sid}")
    assert again.status_code == 404


@pytest.mark.asyncio
async def test_delete_unknown_session_returns_404(app_client: AsyncClient):
    r = await app_client.delete("/api/v1/sessions/does-not-exist")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_stats_returns_dashboard_schema(app_client: AsyncClient):
    """Frontend dashboard relies on these exact keys — schema is part of the contract."""
    r = await app_client.get("/api/v1/sessions/stats")
    assert r.status_code == 200
    body = r.json()
    for key in ("total_sessions", "active_sessions", "total_messages", "latest_session_date"):
        assert key in body, f"missing {key} in stats payload"


@pytest.mark.asyncio
async def test_list_sessions_empty_returns_array(app_client: AsyncClient):
    """Empty DB must return [] not null — frontend `.map()` would crash on null."""
    r = await app_client.get("/api/v1/sessions/")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


@pytest.mark.asyncio
async def test_agent_status_endpoint_healthy_shape(app_client: AsyncClient):
    """/api/v1/agents/status must always be reachable and report a healthy/degraded structure."""
    r = await app_client.get("/api/v1/agents/status")
    assert r.status_code == 200
    body = r.json()
    assert "status" in body
