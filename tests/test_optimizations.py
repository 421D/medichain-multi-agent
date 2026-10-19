"""Tests covering the 7-item optimization pass (Q1/Q5, S2/S3/S5/S6/S7).

Each test documents which optimization it guards and names the observable
behaviour so a future regression produces a single failing assertion that
points back at the root cause.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest


# ───── Q1: LLM tracer ─────────────────────────────────────────────────────


def test_tracer_writes_jsonl_line_per_call(tmp_path, monkeypatch):
    """MediChainTracer.on_llm_end must append one JSONL record with the
    expected schema (node, model, latency_ms, input_tokens, output_tokens,
    cached_tokens, session_id)."""
    from app.core import tracer as tracer_mod
    monkeypatch.setattr(tracer_mod, "TRACE_DIR", tmp_path)

    from langchain_core.outputs import LLMResult, Generation
    from uuid import uuid4

    t = tracer_mod.MediChainTracer(node="diagnostician", session_id="sess-1", model_hint="kimi-latest")
    rid = uuid4()
    t.on_chat_model_start(
        serialized={"kwargs": {"model": "kimi-latest"}, "name": "ChatOpenAI"},
        messages=[[]],
        run_id=rid,
    )
    result = LLMResult(
        generations=[[Generation(text="ok")]],
        llm_output={"token_usage": {"prompt_tokens": 1234, "completion_tokens": 56,
                                      "prompt_tokens_details": {"cached_tokens": 800}}},
    )
    t.on_llm_end(result, run_id=rid)

    lines = list((tmp_path / f"{tracer_mod.datetime.now(tracer_mod.timezone.utc).strftime('%Y-%m-%d')}.jsonl").read_text().splitlines())
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert rec["node"] == "diagnostician"
    assert rec["model"] == "kimi-latest"
    assert rec["input_tokens"] == 1234
    assert rec["output_tokens"] == 56
    assert rec["cached_tokens"] == 800
    assert rec["session_id"] == "sess-1"
    assert rec["error"] is None
    assert rec["latency_ms"] >= 0


def test_tracer_disabled_via_env(tmp_path, monkeypatch):
    """MEDICHAIN_TRACE=0 must make tracer a no-op (no file written)."""
    from app.core import tracer as tracer_mod
    monkeypatch.setattr(tracer_mod, "TRACE_DIR", tmp_path)
    monkeypatch.setenv("MEDICHAIN_TRACE", "0")

    from langchain_core.outputs import LLMResult, Generation
    from uuid import uuid4
    t = tracer_mod.MediChainTracer(node="test")
    rid = uuid4()
    t.on_chat_model_start(serialized={}, messages=[[]], run_id=rid)
    t.on_llm_end(LLMResult(generations=[[Generation(text="")]]), run_id=rid)

    # Directory may exist but must not contain today's jsonl
    files = list(tmp_path.glob("*.jsonl"))
    assert files == [], f"tracer wrote despite MEDICHAIN_TRACE=0: {files}"


def test_tracer_summarize_shape(tmp_path, monkeypatch):
    from app.core import tracer as tracer_mod
    monkeypatch.setattr(tracer_mod, "TRACE_DIR", tmp_path)

    today = tracer_mod.datetime.now(tracer_mod.timezone.utc).strftime('%Y-%m-%d')
    (tmp_path / f"{today}.jsonl").write_text(
        json.dumps({"ts": "x", "run_id": "a", "parent_run_id": None,
                    "node": "diagnostician", "model": "kimi", "latency_ms": 1000,
                    "input_tokens": 1000, "output_tokens": 100, "cached_tokens": 500,
                    "session_id": "s", "error": None}) + "\n" +
        json.dumps({"ts": "x", "run_id": "b", "parent_run_id": None,
                    "node": "diagnostician", "model": "kimi", "latency_ms": 2000,
                    "input_tokens": 2000, "output_tokens": 200, "cached_tokens": 1000,
                    "session_id": "s", "error": None}) + "\n"
    )
    summary = tracer_mod.summarize_today()
    assert summary["calls"] == 2
    stats = summary["per_node"]["diagnostician"]
    assert stats["calls"] == 2
    assert stats["total_in"] == 3000
    assert stats["total_cached"] == 1500
    assert stats["cache_hit_rate"] == 0.5
    assert stats["avg_latency_ms"] == 1500


def test_get_llm_attaches_tracer_callback(monkeypatch):
    """Every ChatOpenAI instance produced by get_llm must carry a
    MediChainTracer in its callbacks so LLM calls are observed."""
    monkeypatch.setenv("KIMI_API_KEY", "test-key")
    from agents.base import get_llm
    from app.core.tracer import MediChainTracer

    llm = get_llm(node="test_node", session_id="s-42")
    # ChatOpenAI stores callbacks on the instance or its callback manager
    assert llm.callbacks is not None
    assert any(isinstance(cb, MediChainTracer) for cb in llm.callbacks)


def test_get_llm_enables_streaming(monkeypatch):
    """S2/S6: streaming=True is required for LangGraph stream_mode='messages'
    to emit per-token events."""
    monkeypatch.setenv("KIMI_API_KEY", "test-key")
    from agents.base import get_llm
    llm = get_llm(node="t")
    assert getattr(llm, "streaming", False) is True, "streaming must be on for token events"


# ───── S5: prompt slimming ─────────────────────────────────────────────────


def test_diagnostician_prompt_is_slimmed():
    """S5: the Diagnostician system prompt was trimmed to <=300 tokens of
    text. Approximate with character count; ~4 char/tok heuristic."""
    from prompts.diagnostician_prompt import DIAGNOSTICIAN_SYSTEM_PROMPT
    # ≤ 1400 chars ≈ ≤ 350 tokens, plenty of headroom
    assert len(DIAGNOSTICIAN_SYSTEM_PROMPT) < 1400, (
        f"prompt bloated back up to {len(DIAGNOSTICIAN_SYSTEM_PROMPT)} chars"
    )
    # Still mentions the invariants we need
    for keyword in ("differential", "confidence", "supporting_evidence", "reasoning_chain"):
        assert keyword in DIAGNOSTICIAN_SYSTEM_PROMPT, f"missing keyword: {keyword}"


def test_cdss_prompt_lists_all_six_tools():
    """CDSS selector prompt must still describe all 6 scoring tools after S5."""
    from prompts.cdss_prompt import CDSS_SELECTOR_SYSTEM_PROMPT
    for tool in ("wells_score", "curb65", "cha2ds2_vasc", "heart_score", "qsofa", "phq9"):
        assert tool in CDSS_SELECTOR_SYSTEM_PROMPT, f"CDSS prompt lost tool: {tool}"


def test_critic_debate_prompt_keeps_safety_flag_rules():
    from prompts.critic_debate_prompt import CRITIC_DEBATE_SYSTEM_PROMPT
    for token in ("red", "yellow", "green", "safety_concern", "missed_diagnosis"):
        assert token in CRITIC_DEBATE_SYSTEM_PROMPT, f"lost token: {token}"


def test_diagnostician_retriever_uses_top_3():
    """S5: retrieval was dropped from top_k=5 to top_k=3."""
    import agents.diagnostician
    import inspect
    src = inspect.getsource(agents.diagnostician.diagnostician_node)
    assert "top_k=3" in src, "diagnostician should retrieve top_k=3 after S5"


# ───── S3: Interviewer batch questioning ───────────────────────────────────


def test_interviewer_prompt_enables_batch_questioning():
    """S3: interviewer should ask 3-5 questions at once."""
    from prompts.interviewer_prompt import INTERVIEWER_SYSTEM_PROMPT
    # Must mention batch questioning (3-5 numbered questions)
    assert "3-5" in INTERVIEWER_SYSTEM_PROMPT, "lost batch instruction"
    assert "numbered" in INTERVIEWER_SYSTEM_PROMPT.lower()


# ───── S2/S6: llm_token WebSocket event ────────────────────────────────────


def test_websocket_event_type_has_llm_token():
    """Frontend WebSocketEvent union must include 'llm_token'."""
    path = Path(__file__).parent.parent / "frontend-v3-creative" / "src" / "types" / "medichain.ts"
    content = path.read_text()
    assert "'llm_token'" in content, "llm_token event missing from frontend union"


def test_websocket_streams_coordinator_tokens_only():
    """_run_graph must route `messages`-mode payloads to llm_token events but
    only for the coordinator node (other agents emit JSON fragments)."""
    import inspect
    from app.api import websocket as ws_mod
    src = inspect.getsource(ws_mod._run_graph)
    # Structural assertions: multi-mode streaming + coordinator filter + llm_token event
    assert 'stream_mode=["updates", "messages"]' in src
    assert 'if node != "coordinator"' in src
    assert '"llm_token"' in src


# ───── S7: retriever cache ─────────────────────────────────────────────────


def test_retriever_caches_identical_queries():
    """S7: two identical retrieve() calls with same top_k must hit the cache
    the second time (1 hit, 1 miss)."""
    from rag.retriever import Retriever

    # Fake KB that counts underlying queries
    mock_kb = MagicMock()
    mock_kb.query.return_value = [{"title": "X", "text": "x", "source": "t"}]

    r = Retriever(mock_kb)
    r.retrieve("chest pain with sob", top_k=3)
    r.retrieve("chest pain with sob", top_k=3)
    stats = r.cache_stats()
    assert stats["hits"] == 1
    assert stats["misses"] == 1
    assert mock_kb.query.call_count == 1, "KB should only be queried once"


def test_retriever_cache_distinguishes_top_k():
    from rag.retriever import Retriever
    mock_kb = MagicMock()
    mock_kb.query.return_value = []
    r = Retriever(mock_kb)
    r.retrieve("q", top_k=3)
    r.retrieve("q", top_k=5)
    # Different top_k → cache miss → 2 underlying calls
    assert mock_kb.query.call_count == 2


def test_retriever_cache_eviction():
    """LRU should cap at _CACHE_MAX entries."""
    from rag.retriever import Retriever
    mock_kb = MagicMock()
    mock_kb.query.return_value = []
    r = Retriever(mock_kb)
    r._CACHE_MAX = 3  # shrink for test
    for i in range(5):
        r.retrieve(f"q-{i}", top_k=3)
    stats = r.cache_stats()
    assert stats["size"] <= 3


def test_retriever_clear_cache():
    from rag.retriever import Retriever
    mock_kb = MagicMock()
    mock_kb.query.return_value = []
    r = Retriever(mock_kb)
    r.retrieve("q", top_k=3)
    r.retrieve("q", top_k=3)
    assert r.cache_stats()["hits"] == 1
    r.clear_cache()
    assert r.cache_stats() == {"hits": 0, "misses": 0, "size": 0, "hit_rate": 0.0}


# ───── Q5: prompt caching helpers ──────────────────────────────────────────


def test_anthropic_cache_marker_applies_to_system_message():
    from app.core.prompt_cache import apply_anthropic_cache_marker
    from langchain_core.messages import SystemMessage, HumanMessage

    msgs = [SystemMessage(content="static"), HumanMessage(content="dynamic")]
    out = apply_anthropic_cache_marker(msgs)
    assert isinstance(out[0].content, list)
    assert out[0].content[0]["cache_control"] == {"type": "ephemeral"}
    # HumanMessage unchanged
    assert out[1].content == "dynamic"


def test_cache_hit_rate_safe_on_zero_denominator():
    from app.core.prompt_cache import cache_hit_rate
    assert cache_hit_rate(0, 0) == 0.0
    assert cache_hit_rate(100, 0) == 0.0
    assert cache_hit_rate(100, 50) == 0.5
    # Clamp
    assert cache_hit_rate(100, 200) == 1.0


# ───── State schema: session_id propagation ────────────────────────────────


def test_graph_state_has_session_id_field():
    """session_id must flow through state so tracer can tag per-session traces."""
    from orchestrator.state import GraphState
    annotations = GraphState.__annotations__
    assert "session_id" in annotations
    assert "llm_model" in annotations
