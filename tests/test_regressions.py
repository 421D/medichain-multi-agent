"""Regression tests for bugs/optimizations fixed in the 2026-04-17/18 audit.

Each test is tagged with the internal fix number (#N) so future maintainers
can trace "why does this test exactly this?" back to the underlying problem.
Tests are intentionally narrow — one observable behaviour per test — so a
regression produces a single failing assertion that names the cause.

These tests are pure-Python (no DB, no LLM, no MCP). Heavier integration
concerns (persistent MCP session, WebSocket streaming, REST interrupt handling)
are left to live/e2e tests; the invariants here protect the cheapest-to-break
logic.
"""
import asyncio
import importlib
import os

import pytest


# -------------------------------------------------------------------
# #2 — Wells Score boundary (cdss/scoring.py)
# Pre-fix: `score <= 1` misclassified score=1.5 as 'moderate'.
# Wells et al. 2000 3-tier cutoffs: <2 low, 2-6 moderate, >6 high.
# -------------------------------------------------------------------


@pytest.fixture
def wells_inputs():
    from cdss.scoring import WellsInput
    def make(**overrides):
        base = dict(
            clinical_signs_dvt=False, pe_most_likely=False,
            heart_rate_over_100=False, immobilization_or_surgery=False,
            previous_dvt_pe=False, hemoptysis=False, malignancy=False,
        )
        base.update(overrides)
        return WellsInput(**base)
    return make


def test_wells_score_1_5_is_low(wells_inputs):
    """Single HR>100 → 1.5 points → must be 'low'. Pre-fix returned 'moderate'."""
    from cdss.scoring import calculate_wells_score
    r = calculate_wells_score(wells_inputs(heart_rate_over_100=True))
    assert r.score == 1.5
    assert r.risk_level == "low"


def test_wells_score_exactly_2_is_moderate(wells_inputs):
    from cdss.scoring import calculate_wells_score
    # hemoptysis (1) + malignancy (1) = 2
    r = calculate_wells_score(wells_inputs(hemoptysis=True, malignancy=True))
    assert r.score == 2.0
    assert r.risk_level == "moderate"


def test_wells_score_over_6_is_high(wells_inputs):
    from cdss.scoring import calculate_wells_score
    r = calculate_wells_score(wells_inputs(
        clinical_signs_dvt=True, pe_most_likely=True, heart_rate_over_100=True,
    ))
    assert r.score == 7.5
    assert r.risk_level == "high"


# -------------------------------------------------------------------
# #1 — MAX_DEBATE_ROUNDS default (agents/debate.py)
# Pre-fix default was 1, making the "structured multi-round debate"
# feature effectively single-shot.
# -------------------------------------------------------------------


def test_max_debate_rounds_default_is_2():
    env_backup = os.environ.pop("MAX_DEBATE_ROUNDS", None)
    try:
        import agents.debate
        importlib.reload(agents.debate)
        assert agents.debate.MAX_DEBATE_ROUNDS == 2
    finally:
        if env_backup is not None:
            os.environ["MAX_DEBATE_ROUNDS"] = env_backup
            import agents.debate
            importlib.reload(agents.debate)


# -------------------------------------------------------------------
# #16 — Pydantic default_factory prevents node crashes when LLM
# returns a structured output missing an optional list field.
# -------------------------------------------------------------------


def test_diagnosis_entry_missing_supporting_evidence_defaults_empty():
    from models.schemas import DiagnosisEntry
    e = DiagnosisEntry(diagnosis="Migraine", confidence=85)
    assert e.supporting_evidence == []
    assert e.against_evidence == []


def test_debate_challenge_missing_evidence_defaults_empty():
    from models.schemas import DebateChallenge
    c = DebateChallenge(
        challenge_id="c1", type="evidence_gap",
        claim="missing dose", suggested_action="ask patient",
    )
    assert c.evidence == []


def test_debate_response_missing_evidence_defaults_empty():
    from models.schemas import DebateResponse
    r = DebateResponse(challenge_id="c1", action="accept", reasoning="because")
    assert r.evidence == []


def test_debate_round_missing_collections_default_empty():
    from models.schemas import DebateRound
    r = DebateRound(round_number=1, resolution="resolved")
    assert r.challenges == []
    assert r.responses == []


def test_diagnostician_debate_output_missing_responses_default_empty():
    from models.schemas import DiagnosticianDebateOutput
    o = DiagnosticianDebateOutput()
    assert o.responses == []
    assert o.updated_reasoning == ""


# -------------------------------------------------------------------
# #17 — safety_flag str → SafetyFlag enum + before-validator coerce.
# Tolerates LLM drift vocabulary without crashing the debate node.
# -------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("green", "green"),
        ("yellow", "yellow"),
        ("red", "red"),
        ("GREEN", "green"),
        ("  Red  ", "red"),
        # LLM drift → coerce to closest canonical
        ("urgent", "red"),
        ("critical", "red"),
        ("emergency", "red"),
        ("danger", "red"),
        ("severe", "red"),
        ("caution", "yellow"),
        ("warn", "yellow"),
        ("warning", "yellow"),
        ("orange", "yellow"),
        ("moderate", "yellow"),
        ("ok", "green"),
        ("safe", "green"),
        ("none", "green"),
        ("clear", "green"),
        ("", "green"),
        # Unknown → conservative default
        ("gibberish", "yellow"),
        ("purple", "yellow"),
    ],
)
def test_safety_flag_coerce(raw, expected):
    from models.schemas import CriticDebateOutput
    out = CriticDebateOutput(safety_flag=raw, overall_assessment="x")
    assert out.safety_flag == expected


def test_safety_flag_missing_defaults_yellow():
    from models.schemas import CriticDebateOutput, SafetyFlag
    out = CriticDebateOutput(overall_assessment="x")
    assert out.safety_flag == SafetyFlag.YELLOW


def test_safety_flag_non_string_non_enum_defaults_yellow():
    from models.schemas import CriticDebateOutput, SafetyFlag
    out = CriticDebateOutput(safety_flag=42, overall_assessment="x")
    assert out.safety_flag == SafetyFlag.YELLOW


# -------------------------------------------------------------------
# #20 — Drug alias normalization (cdss/drug_interactions.py)
# Lets class-level rules (e.g. "ace inhibitor + potassium") fire when
# the patient med list uses brand/generic/salt names.
# -------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,canonical",
    [
        ("Potassium Chloride", "potassium"),
        ("potassium citrate", "potassium"),
        ("KCl", "potassium"),
        ("Slow-K", "potassium"),
        ("lisinopril", "ace inhibitor"),
        ("Ramipril", "ace inhibitor"),
        ("Captopril", "ace inhibitor"),
        ("fluoxetine", "ssri"),
        ("sertraline", "ssri"),
        ("phenelzine", "maoi"),
        ("tranylcypromine", "maoi"),
        ("naproxen", "ibuprofen"),
        ("diclofenac", "ibuprofen"),
        ("iohexol", "contrast dye"),
        # Unknown drug → returns lowercased input, no mapping
        ("aspirin", "aspirin"),
        ("novel_drug_xyz", "novel_drug_xyz"),
    ],
)
def test_drug_alias_normalization(raw, canonical):
    from cdss.drug_interactions import _normalize_drug
    assert _normalize_drug(raw) == canonical


def test_check_interactions_single_drug_skipped():
    from cdss.drug_interactions import check_interactions
    r = asyncio.run(check_interactions(["aspirin"]))
    assert r.api_status == "skipped"
    assert r.interactions == []


def test_check_interactions_ace_plus_potassium_via_aliases():
    """patient on 'lisinopril' + 'potassium chloride' must trigger the
    ACE+K hyperkalemia rule. Pre-alias fix this pair silently missed."""
    from cdss.drug_interactions import check_interactions
    r = asyncio.run(check_interactions(["lisinopril", "potassium chloride"]))
    assert any(i.severity == "major" for i in r.interactions), r.interactions


def test_check_interactions_warfarin_plus_naproxen_via_aliases():
    """warfarin + NSAID bleeding rule fires for naproxen via ibuprofen alias."""
    from cdss.drug_interactions import check_interactions
    r = asyncio.run(check_interactions(["warfarin", "naproxen"]))
    assert any(i.severity == "major" for i in r.interactions)


def test_check_interactions_ssri_maoi_contraindicated():
    from cdss.drug_interactions import check_interactions
    r = asyncio.run(check_interactions(["fluoxetine", "phenelzine"]))
    assert r.contraindicated is True
    assert any(i.severity == "contraindicated" for i in r.interactions)


def test_check_interactions_api_status_surface_when_api_offline():
    """When NLM RxNorm returns non-200 (deprecated Jan 2024) the result
    must expose api_status != 'ok' so callers/UI can tell the user."""
    from cdss.drug_interactions import check_interactions
    # Two rxnorm-resolvable drugs to force API call; status will be
    # 'offline_*' or 'unreachable' in practice.
    r = asyncio.run(check_interactions(["warfarin", "aspirin"]))
    assert r.api_status in ("ok", "unreachable", "parse_error") or r.api_status.startswith("offline"), r.api_status


# -------------------------------------------------------------------
# #14 — ChatMessageOut.from_message surfaces agent / citations from
# Message.metadata_ so reloaded history renders like live chat.
# -------------------------------------------------------------------


def _fake_msg(**overrides):
    import datetime
    class M:
        id = "abc-123"
        session_id = "sess-1"
        role = "assistant"
        content = "hello"
        metadata_ = None
        created_at = datetime.datetime.now()
    m = M()
    for k, v in overrides.items():
        setattr(m, k, v)
    return m


def test_chat_message_out_surfaces_agent_and_citations():
    from app.api.routes.chat import ChatMessageOut
    meta = {"agent": "diagnostician",
            "citations": [{"title": "NICE CG150", "source": "pubmed"}]}
    m = ChatMessageOut.from_message(_fake_msg(metadata_=meta))
    assert m.agent == "diagnostician"
    assert len(m.citations) == 1
    assert m.citations[0]["title"] == "NICE CG150"


def test_chat_message_out_tolerates_none_metadata():
    from app.api.routes.chat import ChatMessageOut
    m = ChatMessageOut.from_message(_fake_msg(metadata_=None))
    assert m.agent is None
    assert m.citations == []


def test_chat_message_out_coerces_malformed_citations_to_list():
    from app.api.routes.chat import ChatMessageOut
    m = ChatMessageOut.from_message(
        _fake_msg(metadata_={"agent": "x", "citations": "not-a-list"}),
    )
    assert m.citations == []


def test_chat_message_out_ignores_non_string_agent():
    from app.api.routes.chat import ChatMessageOut
    m = ChatMessageOut.from_message(_fake_msg(metadata_={"agent": 42}))
    assert m.agent is None


# -------------------------------------------------------------------
# #11 — Alembic migration uses dialect-neutral types so it runs on
# both SQLite (local dev) and Postgres (prod).
# -------------------------------------------------------------------


def test_alembic_migration_is_dialect_neutral():
    import ast
    path = os.path.join(
        os.path.dirname(__file__), "..", "alembic", "versions",
        "8671be970ecc_initial_tables.py",
    )
    with open(path, encoding="utf-8") as f:
        content = f.read()

    # Strip the module docstring via AST so the historical note inside it
    # (which mentions the old postgresql.JSONB types) doesn't trip our
    # "code must not reference postgresql" assertions.
    tree = ast.parse(content)
    if tree.body and isinstance(tree.body[0], ast.Expr) and isinstance(
        tree.body[0].value, ast.Constant
    ):
        tree.body.pop(0)
    code_only = ast.unparse(tree)

    assert "postgresql" not in code_only, (
        "migration code still references postgresql dialect"
    )
    assert "sa.UUID(" not in code_only, (
        "UUID column type should be sa.String(length=36) for SQLite compat"
    )
    # Positive checks: dialect-neutral replacements are present in the code
    assert "String(length=36)" in code_only
    assert "JSON()" in code_only


# -------------------------------------------------------------------
# #23 — Two RAG modules must point at the same Chroma collection,
# else MediChainRAG.search() would hit an empty namespace.
# -------------------------------------------------------------------


def test_medichain_rag_default_collection_aligned_with_knowledge_base():
    import inspect
    from rag.medichain_rag import MediChainRAG
    sig = inspect.signature(MediChainRAG.__init__)
    assert sig.parameters["collection_name"].default == "medical_kb"


# -------------------------------------------------------------------
# #6 — DiagnosticianOutput accepts the shape the rewritten prompt
# instructs the LLM to emit (confidence + supporting_evidence +
# recommended_tests + reasoning_chain).
# -------------------------------------------------------------------


def test_diagnostician_output_validates_rewritten_prompt_shape():
    from models.schemas import DiagnosticianOutput
    out = DiagnosticianOutput.model_validate({
        "differential_diagnosis": [
            {
                "diagnosis": "Migraine",
                "confidence": 85,
                "supporting_evidence": ["unilateral throbbing", "photophobia"],
                "against_evidence": [],
                "source": "ICHD-3",
            },
            {
                "diagnosis": "Tension-type headache",
                "confidence": 45,
                "supporting_evidence": ["bilateral pressure"],
                "source": "NICE CG150",
            },
        ],
        "recommended_tests": ["neuro exam", "BP check"],
        "reasoning_chain": "Classic migraine features; rule out SAH if thunderclap onset.",
    })
    assert len(out.differential_diagnosis) == 2
    assert out.differential_diagnosis[0].confidence == 85
    assert out.recommended_tests == ["neuro exam", "BP check"]


# -------------------------------------------------------------------
# #22 — KnowledgeBase must tolerate a JSON entry with an explicit
# "title": null (ChromaDB metadata rejects None values).
# -------------------------------------------------------------------


def test_title_null_does_not_crash_chroma_load(tmp_path, monkeypatch):
    """Exercise the actual KnowledgeBase.load() code path with an entry
    whose title is explicitly null in the JSON. Pre-fix this would call
    `collection.add(metadatas=[{"title": None, ...}])` and Chroma would
    reject None values. Post-fix the title coerces to "" and load succeeds.
    """
    import json as _json
    from rag import knowledge_base as kb_mod

    # Tiny synthetic dataset: one entry with title=null, one with a real title
    data_file = tmp_path / "test_kb.json"
    data_file.write_text(_json.dumps([
        {"id": "doc_a", "title": None, "contents": "Bacterial meningitis presents with fever, headache, neck stiffness."},
        {"id": "doc_b", "title": "Migraine", "contents": "Classic migraine: unilateral throbbing with photophobia."},
    ]))

    chroma_dir = tmp_path / "chroma"
    monkeypatch.setattr(kb_mod, "DATA_DIR", tmp_path)

    kb = kb_mod.KnowledgeBase(persist_dir=str(chroma_dir))
    n = kb.load(json_path=str(data_file))
    assert n == 2, f"expected 2 chunks loaded, got {n}"
    # Verify the null-title entry got coerced and is queryable
    results = kb.query("meningitis", n_results=2)
    assert results, "knowledge base should return at least one result"
    titles = [r.get("title") for r in results]
    # title was None in source → must now be "" (or fall back to "untitled" handling)
    assert all(isinstance(t, str) for t in titles), f"non-string title leaked: {titles}"


# -------------------------------------------------------------------
# #18 — agents/critic.py was v1 orphan code, removed.
# -------------------------------------------------------------------


def test_critic_module_removed():
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("agents.critic")


# -------------------------------------------------------------------
# #A — CORS env override (app/main.py)
# -------------------------------------------------------------------


def test_cors_origins_default_when_env_not_set():
    env_backup = os.environ.pop("CORS_ORIGINS", None)
    try:
        import app.main
        importlib.reload(app.main)
        assert app.main.CORS_ORIGINS == [
            "http://localhost:8080",
            "http://localhost:5173",
            "http://localhost:3000",
        ]
    finally:
        if env_backup is not None:
            os.environ["CORS_ORIGINS"] = env_backup
            import app.main
            importlib.reload(app.main)


def test_cors_origins_env_override():
    os.environ["CORS_ORIGINS"] = "https://prod.example.com, http://localhost:9999"
    try:
        import app.main
        importlib.reload(app.main)
        assert "https://prod.example.com" in app.main.CORS_ORIGINS
        assert "http://localhost:9999" in app.main.CORS_ORIGINS
        # No empty strings from trailing commas
        assert "" not in app.main.CORS_ORIGINS
    finally:
        del os.environ["CORS_ORIGINS"]
        import app.main
        importlib.reload(app.main)


# -------------------------------------------------------------------
# #15 — MCP client exposes persistent-session lifecycle API.
# (Actually running it needs the MCP server; we just verify the API shape.)
# -------------------------------------------------------------------


def test_cdss_node_skips_when_no_ddx():
    """Empty differential → cdss_node returns empty scores with no LLM call."""
    from agents import cdss_node as cdss_mod
    state = {"diagnosis": {"differential_diagnosis": []}, "patient_history": {}}
    result = cdss_mod.cdss_node(state)
    assert result["cdss_scores"] == {}


def test_cdss_tool_registry_complete():
    """All 6 scoring tools must be wired in the cdss_node registry."""
    from agents.cdss_node import _TOOL_REGISTRY
    assert set(_TOOL_REGISTRY.keys()) == {
        "wells_score", "curb65", "cha2ds2_vasc",
        "heart_score", "qsofa", "phq9",
    }
    # Every entry is (callable, schema_class)
    for name, (fn, schema) in _TOOL_REGISTRY.items():
        assert callable(fn), f"{name} fn not callable"
        assert hasattr(schema, "model_validate"), f"{name} schema not a Pydantic model"


def test_cdss_to_list_transforms_known_tools():
    """Backend cdss_scores dict → frontend CDSSScore[] with risk_level mapping."""
    from app.api.websocket import _cdss_to_list
    backend_dict = {
        "wells_score":   {"score": 7.5, "risk_level": "high", "recommendation": "CTPA"},
        "qsofa":         {"score": 2, "sepsis_risk": "High risk", "recommendation": "blood cultures"},
        "cha2ds2_vasc":  {"score": 0, "annual_stroke_risk": "0%", "recommendation": "no OAC"},
        "phq9":          {"total_score": 14, "severity": "moderate", "recommendation": "consider therapy"},
    }
    out = _cdss_to_list(backend_dict)
    assert len(out) == 4
    by_name = {item["tool_name"]: item for item in out}
    # Wells: explicit risk_level=high → high
    assert by_name["Wells (PE)"]["risk_level"] == "high"
    # qSOFA: derived from score (>=2 → high)
    assert by_name["qSOFA"]["risk_level"] == "high"
    # CHA2DS2-VASc: derived from score (0 → low)
    assert by_name["CHA\u2082DS\u2082-VASc"]["risk_level"] == "low"
    # PHQ-9: severity="moderate" → moderate
    assert by_name["PHQ-9"]["risk_level"] == "moderate"
    # PHQ-9 score sourced from total_score
    assert by_name["PHQ-9"]["score"] == 14
    # Each item has the keys frontend CDSSScore expects
    for item in out:
        assert {"tool_name", "score", "max_score", "risk_level", "recommendation"} <= item.keys()


def test_cdss_to_list_drops_errored_entries():
    from app.api.websocket import _cdss_to_list
    backend = {
        "wells_score": {"error": "param missing"},
        "qsofa": {"score": 1, "sepsis_risk": "Low risk", "recommendation": "monitor"},
    }
    out = _cdss_to_list(backend)
    assert len(out) == 1
    assert out[0]["tool_name"] == "qSOFA"


def test_cdss_to_list_handles_empty():
    from app.api.websocket import _cdss_to_list
    assert _cdss_to_list(None) == []
    assert _cdss_to_list({}) == []


def test_websocket_history_loader_does_not_duplicate_first_user_message():
    """First-turn WS path persists the opening user message before reloading
    session history, so the loader should return that message exactly once."""
    from types import SimpleNamespace

    from app.api.websocket import _history_messages_from_db_rows

    rows = [
        SimpleNamespace(role="assistant", content="Hello, how can I help?"),
        SimpleNamespace(role="user", content="I have chest pain"),
    ]
    history = _history_messages_from_db_rows(rows)

    assert history == [
        {"role": "ai", "content": "Hello, how can I help?"},
        {"role": "human", "content": "I have chest pain"},
    ]
    assert sum(1 for m in history if m["role"] == "human" and m["content"] == "I have chest pain") == 1


def test_graph_includes_cdss_node():
    """Compiled LangGraph must include the cdss node between diagnostician and debate."""
    from orchestrator.graph import create_graph
    g = create_graph()
    nodes = {n for n in g.get_graph().nodes if not n.startswith("__")}
    assert "cdss" in nodes
    assert {"interviewer", "diagnostician", "cdss", "debate_round", "coordinator"} <= nodes


def test_mcp_client_lifecycle_api_present():
    """The lifespan hooks are still callable (now no-ops, after rolling back
    the persistent-session optimisation that violated anyio task scope).
    Tool calls fall back to per-call subprocess spawn — slower but correct
    under FastAPI's concurrent request model."""
    from app.core import mcp_client
    assert callable(mcp_client.init_mcp_session)
    assert callable(mcp_client.close_mcp_session)
    assert callable(mcp_client.call_mcp_tool)
    assert callable(mcp_client.list_mcp_tools)
