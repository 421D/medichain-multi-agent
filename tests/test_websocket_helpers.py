"""Tests for `_cdss_to_list` and `ConnectionManager` in app/api/websocket.py."""
import asyncio
from contextlib import suppress

import pytest

from app.api.websocket import ConnectionManager, _cdss_to_list


# ──────────────────────────── _cdss_to_list ─────────────────────────────

def test_cdss_to_list_returns_empty_on_none_or_empty():
    assert _cdss_to_list(None) == []
    assert _cdss_to_list({}) == []


def test_cdss_to_list_skips_error_entries_and_non_dicts():
    result = _cdss_to_list({
        "wells_score": {"error": "missing_param"},
        "curb65": "not a dict",
        "qsofa": {"score": 1},
    })
    # Only the qSOFA entry is well-formed.
    assert [r["tool_name"] for r in result] == ["qSOFA"]


def test_cdss_to_list_qsofa_high_risk_when_score_2_or_more():
    """qSOFA derives risk_level from the score: ≥2 == high, else low."""
    high = _cdss_to_list({"qsofa": {"score": 2, "recommendation": "ICU"}})[0]
    low = _cdss_to_list({"qsofa": {"score": 1, "recommendation": "Floor"}})[0]
    assert high["risk_level"] == "high"
    assert low["risk_level"] == "low"
    assert high["recommendation"] == "ICU"


def test_cdss_to_list_cha2ds2_vasc_three_band_mapping():
    """CHA2DS2-VASc: 0 -> low, 1 -> moderate, ≥2 -> high."""
    rows = [
        _cdss_to_list({"cha2ds2_vasc": {"score": s}})[0]["risk_level"]
        for s in (0, 1, 2, 5)
    ]
    assert rows == ["low", "moderate", "high", "high"]


def test_cdss_to_list_phq9_uses_total_score_field_and_severity():
    """PHQ-9 uniquely stores its number under `total_score`, not `score`."""
    out = _cdss_to_list({
        "phq9": {"total_score": 18, "severity": "moderately severe", "recommendation": "Refer"},
    })[0]
    assert out["score"] == 18
    # "moderately severe" is normalised to "high" via _CDSS_RISK_MAP.
    assert out["risk_level"] == "high"
    assert out["max_score"] == 27


def test_cdss_to_list_unknown_tool_falls_through_with_raw_name():
    """An unknown tool key still produces a row using the raw key as label."""
    out = _cdss_to_list({"experimental_score": {"score": 7, "risk_level": "moderate"}})[0]
    assert out["tool_name"] == "experimental_score"
    assert out["score"] == 7
    assert out["max_score"] is None  # unknown tool has no max in the table


# ─────────────────────────── ConnectionManager ──────────────────────────

class _FakeWebSocket:
    """Minimal stand-in for FastAPI's WebSocket — we only call accept()/close()."""
    def __init__(self):
        self.accepted = False
        self.closed = False

    async def accept(self):
        self.accepted = True

    async def close(self):
        self.closed = True


@pytest.mark.asyncio
async def test_connection_manager_connect_accepts_and_records_socket():
    mgr = ConnectionManager()
    ws = _FakeWebSocket()

    await mgr.connect("sess-1", ws)

    assert ws.accepted is True
    assert mgr.active["sess-1"] is ws


@pytest.mark.asyncio
async def test_connection_manager_replacing_socket_closes_old_and_cancels_task():
    """A new connect() for an existing session must close the previous socket
    AND cancel its still-running graph task — the comment in websocket.py:104-107
    explicitly says half-finished tasks would otherwise keep burning LLM tokens."""
    mgr = ConnectionManager()
    old_ws, new_ws = _FakeWebSocket(), _FakeWebSocket()

    await mgr.connect("sess-1", old_ws)

    # Pretend a long-running graph task is in flight for this session.
    async def _slow():
        await asyncio.sleep(60)

    task = asyncio.create_task(_slow())
    mgr.register_task("sess-1", task)

    # New WS replaces the old one.
    await mgr.connect("sess-1", new_ws)

    assert old_ws.closed is True
    assert new_ws.accepted is True
    assert mgr.active["sess-1"] is new_ws

    # The previously registered task should be cancelled, not still running.
    with suppress(asyncio.CancelledError):
        await task
    assert task.cancelled()


@pytest.mark.asyncio
async def test_connection_manager_disconnect_cancels_task_and_clears_state():
    mgr = ConnectionManager()
    ws = _FakeWebSocket()
    await mgr.connect("sess-2", ws)

    async def _busy():
        await asyncio.sleep(60)

    task = asyncio.create_task(_busy())
    mgr.register_task("sess-2", task)

    mgr.disconnect("sess-2")

    assert "sess-2" not in mgr.active
    assert "sess-2" not in mgr.tasks
    with suppress(asyncio.CancelledError):
        await task
    assert task.cancelled()


@pytest.mark.asyncio
async def test_connection_manager_disconnect_unknown_session_is_noop():
    """Idempotent: disconnect on a session we never tracked should not raise."""
    mgr = ConnectionManager()
    mgr.disconnect("never-existed")
    assert mgr.active == {}
    assert mgr.tasks == {}
