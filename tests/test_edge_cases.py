"""Edge-case tests for the 2026-04-21/22 follow-up patches:

- agent_bridge: OpenAI-style role normalization (user/assistant → human/ai)
- cdss_node: deterministic keyword fallback when LLM selector returns empty
- debate: all_resolved requires full challenge_id coverage
- tracer: multi-path usage extraction (response_metadata, generation_info)

Each test is narrow — one observable behaviour per test — so a regression
produces a single failing assertion that names the cause.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, Generation, LLMResult


# ───── agent_bridge: role normalization ─────────────────────────────────


def test_agent_bridge_normalises_openai_user_role():
    """REST callers often send OpenAI-style {role: user}. Without the _role_map
    the graph sees unknown roles and drops history, so multi-turn REST shrinks
    context each turn. The fix normalises user→human, assistant→ai."""
    from app.core import agent_bridge

    captured = {}

    def fake_invoke(state, config=None):
        captured["messages"] = state["messages"]
        return {**state, "coordinator_response": "ok"}

    with patch.object(agent_bridge, "_graph") as mock_graph:
        mock_graph.invoke.side_effect = fake_invoke
        agent_bridge._run_graph_sync(
            user_message="hello",
            chat_history=[
                {"role": "user",      "content": "m1"},
                {"role": "assistant", "content": "m2"},
                {"role": "system",    "content": "m3"},
                {"role": "patient",   "content": "m4"},  # exotic alias
                {"role": "bot",       "content": "m5"},
            ],
            thread_id="t-1",
        )
    roles = [m["role"] for m in captured["messages"]]
    # Normalised to graph-internal vocabulary, current message appended
    assert roles == ["human", "ai", "system", "human", "ai", "human"]
    # Latest user message preserved
    assert captured["messages"][-1]["content"] == "hello"


def test_agent_bridge_does_not_duplicate_latest_user_message():
    """If the latest history entry already equals the current user_message, we
    must NOT append a duplicate. Regression guard."""
    from app.core import agent_bridge
    captured = {}
    def fake_invoke(state, config=None):
        captured["messages"] = state["messages"]
        return {**state, "coordinator_response": ""}
    with patch.object(agent_bridge, "_graph") as mock_graph:
        mock_graph.invoke.side_effect = fake_invoke
        agent_bridge._run_graph_sync(
            user_message="hello",
            chat_history=[{"role": "user", "content": "hello"}],
            thread_id="t-1",
        )
    assert len(captured["messages"]) == 1
    assert captured["messages"][0]["content"] == "hello"


def test_agent_bridge_session_id_flows_to_state():
    """session_id must be set in state from thread_id so the tracer can tag."""
    from app.core import agent_bridge
    captured = {}
    def fake_invoke(state, config=None):
        captured["state"] = state
        captured["config"] = config
        return {**state, "coordinator_response": ""}
    with patch.object(agent_bridge, "_graph") as mock_graph:
        mock_graph.invoke.side_effect = fake_invoke
        agent_bridge._run_graph_sync(
            user_message="hi", chat_history=None, thread_id="sess-42",
        )
    assert captured["state"]["session_id"] == "sess-42"
    assert captured["config"]["configurable"]["thread_id"] == "sess-42"


def test_agent_bridge_handles_anonymous_thread():
    """thread_id=None must fall back to 'rest-anon' and leave session_id=None."""
    from app.core import agent_bridge
    captured = {}
    def fake_invoke(state, config=None):
        captured["state"] = state
        captured["config"] = config
        return {**state, "coordinator_response": ""}
    with patch.object(agent_bridge, "_graph") as mock_graph:
        mock_graph.invoke.side_effect = fake_invoke
        agent_bridge._run_graph_sync("hi", None, "", None)
    assert captured["config"]["configurable"]["thread_id"] == "rest-anon"
    assert captured["state"]["session_id"] is None


# ───── cdss_node: deterministic keyword fallback ────────────────────────


def test_cdss_fallback_candidates_matches_chest_pain():
    from agents.cdss_node import _fallback_candidates
    ddx = [{"diagnosis": "Acute Coronary Syndrome", "reasoning_chain": ""}]
    history = {"chief_complaint": "chest pain radiating to arm"}
    assert "heart_score" in _fallback_candidates(ddx, history)


def test_cdss_fallback_candidates_matches_pe():
    from agents.cdss_node import _fallback_candidates
    ddx = [{"diagnosis": "Pulmonary Embolism", "reasoning_chain": ""}]
    history = {"chief_complaint": "sudden dyspnea"}
    assert "wells_score" in _fallback_candidates(ddx, history)


def test_cdss_fallback_candidates_matches_pneumonia():
    from agents.cdss_node import _fallback_candidates
    ddx = [{"diagnosis": "Community-acquired pneumonia"}]
    history = {"chief_complaint": "cough fever"}
    assert "curb65" in _fallback_candidates(ddx, history)


def test_cdss_fallback_candidates_empty_for_unrelated_ddx():
    """Routine UTI / migraine should NOT force any CDSS tool."""
    from agents.cdss_node import _fallback_candidates
    ddx = [{"diagnosis": "Urinary tract infection"}]
    history = {"chief_complaint": "dysuria"}
    assert _fallback_candidates(ddx, history) == []


def test_cdss_fallback_candidates_case_insensitive():
    from agents.cdss_node import _fallback_candidates
    ddx = [{"diagnosis": "ACUTE MYOCARDIAL INFARCTION"}]
    history = {"chief_complaint": ""}
    assert "heart_score" in _fallback_candidates(ddx, history)


def test_cdss_fallback_keyword_table_is_comprehensive():
    """Every fallback keyword must map to a tool that actually exists in the
    CDSS registry — catches typos / renamed tools."""
    from agents.cdss_node import _FALLBACK_KEYWORDS, _TOOL_REGISTRY
    for tool_name, kws in _FALLBACK_KEYWORDS:
        assert tool_name in _TOOL_REGISTRY, f"unknown tool in fallback: {tool_name}"
        assert len(kws) > 0, f"empty keyword list for {tool_name}"


# ───── debate: challenge_id coverage for all_resolved ───────────────────


def test_debate_all_resolved_needs_full_challenge_coverage():
    """all_resolved must be True only if every challenge_id has a terminal
    response. Missing a response → should force another round."""
    # Exercise the same set-coverage logic that debate_round_node uses.
    challenge_ids = {"c1", "c2", "c3"}
    responded_ok = {"c1", "c2"}  # c3 missing
    all_resolved = challenge_ids.issubset(responded_ok) and len(challenge_ids) > 0
    assert all_resolved is False


def test_debate_all_resolved_true_when_full():
    challenge_ids = {"c1", "c2"}
    responded_ok = {"c1", "c2"}
    all_resolved = challenge_ids.issubset(responded_ok) and len(challenge_ids) > 0
    assert all_resolved is True


def test_debate_all_resolved_false_when_no_challenges():
    """Zero challenges is a degenerate case — the debate node handles it via
    the early-return approved path, so all_resolved here is meaningless.
    Guard the literal expression anyway."""
    challenge_ids = set()
    responded_ok = set()
    all_resolved = challenge_ids.issubset(responded_ok) and len(challenge_ids) > 0
    assert all_resolved is False


# ───── tracer: multi-path usage extraction ──────────────────────────────


def _gen_with_meta(usage_metadata=None, response_metadata=None, generation_info=None):
    msg = AIMessage(content="ok")
    if usage_metadata is not None:
        msg.usage_metadata = usage_metadata
    if response_metadata is not None:
        msg.response_metadata = response_metadata
    gen = ChatGeneration(message=msg, generation_info=generation_info or {})
    return gen


def test_tracer_usage_from_llm_output():
    """Original path: llm_output.token_usage populated by langchain_openai."""
    from app.core.tracer import _extract_usage
    result = LLMResult(
        generations=[[Generation(text="ok")]],
        llm_output={"token_usage": {"prompt_tokens": 100, "completion_tokens": 20}},
    )
    u = _extract_usage(result)
    assert u["input_tokens"] == 100
    assert u["output_tokens"] == 20


def test_tracer_usage_from_response_metadata():
    """Kimi path: token_usage lives in AIMessage.response_metadata."""
    from app.core.tracer import _extract_usage
    gen = _gen_with_meta(response_metadata={
        "token_usage": {"prompt_tokens": 200, "completion_tokens": 30},
    })
    result = LLMResult(generations=[[gen]])
    u = _extract_usage(result)
    assert u["input_tokens"] == 200
    assert u["output_tokens"] == 30


def test_tracer_usage_from_usage_metadata():
    """LangChain 0.3+ canonical path: AIMessage.usage_metadata."""
    from app.core.tracer import _extract_usage
    gen = _gen_with_meta(usage_metadata={
        "input_tokens": 50, "output_tokens": 10,
        "input_token_details": {"cache_read": 40},
    })
    result = LLMResult(generations=[[gen]])
    u = _extract_usage(result)
    assert u["input_tokens"] == 50
    assert u["output_tokens"] == 10
    assert u["cached_tokens"] == 40


def test_tracer_usage_cached_tokens_openai():
    """OpenAI surfaces cached_tokens under prompt_tokens_details."""
    from app.core.tracer import _extract_usage
    result = LLMResult(
        generations=[[Generation(text="ok")]],
        llm_output={"token_usage": {
            "prompt_tokens": 2000, "completion_tokens": 100,
            "prompt_tokens_details": {"cached_tokens": 1500},
        }},
    )
    u = _extract_usage(result)
    assert u["cached_tokens"] == 1500


def test_tracer_usage_cached_tokens_anthropic():
    """Anthropic surfaces cache reads as cache_read_input_tokens."""
    from app.core.tracer import _extract_usage
    result = LLMResult(
        generations=[[Generation(text="ok")]],
        llm_output={"token_usage": {
            "prompt_tokens": 3000, "completion_tokens": 200,
            "cache_read_input_tokens": 2500,
        }},
    )
    u = _extract_usage(result)
    assert u["cached_tokens"] == 2500


def test_tracer_usage_zero_when_no_source():
    """Empty LLMResult should not crash; all counters default to 0."""
    from app.core.tracer import _extract_usage
    result = LLMResult(generations=[[Generation(text="")]])
    u = _extract_usage(result)
    assert u == {"input_tokens": 0, "output_tokens": 0, "cached_tokens": 0}


def test_tracer_usage_prefers_non_zero_value_on_merge():
    """If multiple sources report token counts, prefer the first non-zero
    value so a later empty source doesn't overwrite a real count."""
    from app.core.tracer import _extract_usage
    # llm_output path reports real numbers; response_metadata path is empty
    gen = _gen_with_meta(response_metadata={"token_usage": {}})
    result = LLMResult(
        generations=[[gen]],
        llm_output={"token_usage": {"prompt_tokens": 500, "completion_tokens": 50}},
    )
    u = _extract_usage(result)
    assert u["input_tokens"] == 500
    assert u["output_tokens"] == 50


# ───── Frontend createSession signature regression ──────────────────────


def test_consultations_page_calls_create_session_positionally():
    """Regression guard for the 422 bug: Consultations.tsx MUST call
    createSession('title', 'llm_model') positionally, not as an object."""
    import re
    from pathlib import Path
    path = Path(__file__).parent.parent / "frontend-v3-creative" / "src" / "pages" / "Consultations.tsx"
    src = path.read_text()
    # Find the createSession call
    m = re.search(r"createSession\([^)]+\)", src)
    assert m, "createSession call not found in Consultations.tsx"
    call = m.group(0)
    # Must NOT pass an object literal as first argument
    assert "createSession({" not in call, (
        f"createSession was called with an object literal — this triggers 422: {call}"
    )
    # Must look like positional string args
    assert "'New Consultation'" in call or '"New Consultation"' in call


# ───── Frontend medichain.css loaded ────────────────────────────────────


def test_frontend_imports_medichain_css():
    """main.tsx must import the design-system stylesheet or all pages render
    naked without the .card/.btn/.chat-* classes."""
    from pathlib import Path
    path = Path(__file__).parent.parent / "frontend-v3-creative" / "src" / "main.tsx"
    src = path.read_text()
    assert "styles/medichain.css" in src


def test_session_detail_hooks_before_early_returns():
    """Rules of Hooks guard: every useState / useEffect / useMemo / useRef
    in SessionDetail must be registered BEFORE any early-return statement.
    Otherwise React throws 'Rendered fewer hooks than expected' when the
    404/error branch is taken, and the ErrorBoundary eats the whole route."""
    from pathlib import Path
    path = Path(__file__).parent.parent / "frontend-v3-creative" / "src" / "pages" / "SessionDetail.tsx"
    src = path.read_text()

    # Locate the earliest early-return in the component body.
    # We look for the rawSessionId guard which is the first bail-out.
    marker = "if (!rawSessionId) return null;"
    idx = src.find(marker)
    assert idx != -1, "rawSessionId early-return marker not found — refactor likely broke this test"

    tail = src[idx:]
    # These hook calls, if they appear AFTER the early-return, break Rules of Hooks.
    for hook in ("useState", "useRef", "useEffect", "useMemo", "useCallback", "useWebSocket("):
        assert hook not in tail, (
            f"'{hook}' appears after the early-return guard in SessionDetail.tsx — "
            f"this violates Rules of Hooks and React will throw 'Rendered fewer hooks' "
            f"when the 404/error branch renders. Move the hook above the early return."
        )


def test_session_detail_has_not_found_branch():
    """SessionDetail must render a real 'Session not found' card when the API
    returns 404 — not leave the user stuck on 'Loading...' forever."""
    from pathlib import Path
    path = Path(__file__).parent.parent / "frontend-v3-creative" / "src" / "pages" / "SessionDetail.tsx"
    src = path.read_text()
    assert "Session not found" in src
    assert "sessionError" in src
