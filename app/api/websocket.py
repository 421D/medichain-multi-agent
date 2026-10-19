"""
WebSocket handler — real-time LangGraph multi-turn agent streaming.

Replaces Sprint 1 echo stub with full interrupt/resume support:
- Interviewer asks follow-up questions via LangGraph interrupt()
- Client sends answers, graph resumes with Command(resume=...)
- All agent events (transition, reasoning, messages, diagnosis) streamed to client
"""

import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from langgraph.types import Command
from sqlalchemy import select

from app.db.database import async_session
from app.db.models import AgentLog, Message

router = APIRouter()
logger = logging.getLogger(__name__)

AGENT_LABELS = {
    "interviewer": "Interviewer",
    "diagnostician": "Diagnostician",
    "critic": "Critic",
    "cdss": "CDSS",
    "debate_round": "Debate",
    "coordinator": "Coordinator",
}


# --- CDSS dict → frontend CDSSScore[] transform ---
# Backend stores cdss_scores as a dict keyed by tool name; frontend wants a
# list of {tool_name, score, max_score, risk_level, recommendation}.
_CDSS_DISPLAY = {
    "wells_score":  ("Wells (PE)",      12.5, "risk_level"),
    "curb65":       ("CURB-65",          5,   "severity"),
    "cha2ds2_vasc": ("CHA\u2082DS\u2082-VASc", 9, None),  # derive from score
    "heart_score":  ("HEART",            10,  "risk_level"),
    "qsofa":        ("qSOFA",            3,   None),  # derive from score
    "phq9":         ("PHQ-9",            27,  "severity"),
}
_CDSS_RISK_MAP = {
    "low": "low", "minimal": "low", "mild": "low",
    "moderate": "moderate", "mod": "moderate",
    "high": "high", "moderately severe": "high",
    "severe": "critical", "critical": "critical",
}


def _cdss_to_list(cdss_scores: dict | None) -> list[dict]:
    """Flatten the backend cdss_scores dict into the frontend CDSSScore[] shape."""
    if not cdss_scores:
        return []
    out = []
    for tool_name, data in cdss_scores.items():
        if not isinstance(data, dict) or "error" in data:
            continue
        display_name, max_score, risk_field = _CDSS_DISPLAY.get(tool_name, (tool_name, None, None))
        # PHQ-9 stores its score under "total_score"; everything else under "score".
        score = data.get("score", data.get("total_score", 0))
        # Score → frontend risk_level enum (low/moderate/high/critical).
        if tool_name == "qsofa":
            raw_risk = "high" if (score or 0) >= 2 else "low"
        elif tool_name == "cha2ds2_vasc":
            s = int(score or 0)
            raw_risk = "low" if s == 0 else ("moderate" if s == 1 else "high")
        elif risk_field:
            raw_risk = (data.get(risk_field) or "").lower()
        else:
            raw_risk = "moderate"
        # First word handles "moderately severe" → match "moderately"? no, take whole string
        risk_level = _CDSS_RISK_MAP.get(raw_risk, "moderate")
        out.append({
            "tool_name": display_name,
            "score": score,
            "max_score": max_score,
            "risk_level": risk_level,
            "recommendation": data.get("recommendation", ""),
        })
    return out


def _history_messages_from_db_rows(messages: list[Message]) -> list[dict]:
    """Convert persisted Message rows into LangGraph chat history shape.

    The first-turn WebSocket path persists the current user message before
    it reloads the session history from the database, so the returned rows
    already include that opening message. Callers must therefore use this
    history as-is and must not append `user_message` again.
    """
    history_messages: list[dict] = []
    for m in messages:
        role = "human" if m.role == "user" else "ai"
        history_messages.append({"role": role, "content": m.content})
    return history_messages


class ConnectionManager:
    def __init__(self):
        self.active: dict[str, WebSocket] = {}
        # Track the running graph task per session so we can cancel it when a
        # new connection replaces the old one. Without this, a half-finished
        # _run_graph keeps consuming LLM tokens for a socket nobody listens to.
        self.tasks: dict[str, asyncio.Task] = {}

    async def connect(self, session_id: str, ws: WebSocket):
        old = self.active.get(session_id)
        if old:
            try:
                await old.close()
            except Exception:
                pass
        old_task = self.tasks.pop(session_id, None)
        if old_task and not old_task.done():
            old_task.cancel()
        await ws.accept()
        self.active[session_id] = ws
        logger.info("WebSocket connected: session=%s", session_id)

    def register_task(self, session_id: str, task: asyncio.Task):
        """Record the in-flight graph task so a future connect() can cancel it."""
        self.tasks[session_id] = task

    def disconnect(self, session_id: str):
        self.active.pop(session_id, None)
        task = self.tasks.pop(session_id, None)
        if task and not task.done():
            task.cancel()
        logger.info("WebSocket disconnected: session=%s", session_id)


manager = ConnectionManager()


def _ws_msg(
    msg_type: str,
    agent: str | None = None,
    content: str | None = None,
    data: dict | None = None,
) -> str:
    """Build a JSON WebSocket message string."""
    payload: dict = {"type": msg_type}
    if agent is not None:
        payload["agent"] = agent
    if content is not None:
        payload["content"] = content
    if data is not None:
        payload["data"] = data
    return json.dumps(payload, ensure_ascii=False)


async def _persist_log(
    session_id: str | None,
    agent_name: str,
    action: str,
    content: str | None = None,
    data: dict | None = None,
):
    """Best-effort persistence of an agent event to the database."""
    if not session_id:
        return
    try:
        async with async_session() as db:
            log = AgentLog(
                session_id=session_id,
                agent_name=agent_name or "unknown",
                action=action,
                output_data={"content": content} if content else data,
            )
            db.add(log)
            await db.commit()
    except Exception as e:
        logger.warning("Failed to persist agent log: %s", e)


async def _persist_message(
    session_id: str | None,
    role: str,
    content: str,
    agent: str | None = None,
):
    """Best-effort persistence of a chat message to the database."""
    if not session_id or not content:
        return
    try:
        async with async_session() as db:
            msg = Message(
                session_id=session_id,
                role=role,
                content=content,
                metadata_={"agent": agent} if agent else None,
            )
            db.add(msg)
            await db.commit()
    except Exception as e:
        logger.warning("Failed to persist message: %s", e)


async def _send_agent_logs(websocket: WebSocket, logs: list[dict], session_id: str | None = None):
    """Send agent reasoning logs to the client and persist them."""
    for log in logs:
        agent = log.get("agent", "")
        action = log.get("action", "")
        reasoning = log.get("reasoning") or log.get("detail") or ""
        content_text = None

        if action == "llm_call" and reasoning:
            content_text = f"[{AGENT_LABELS.get(agent, agent)}] {reasoning}"
        elif action == "rag_retrieval":
            count = log.get("results_count", 0)
            content_text = f"Retrieved {count} relevant medical knowledge entries"
        elif action == "diagnosis_complete":
            preview = log.get("reasoning_preview", "")
            n = log.get("diagnoses_count", 0)
            content_text = f"Generated {n} differential diagnoses\n{preview}"
        elif action == "review_complete":
            approval = log.get("approval", False)
            safety = log.get("safety_flag", "")
            issues = log.get("issues_count", 0)
            status = "APPROVED" if approval else "DENIED"
            content_text = f"Review {status} | Safety: {safety} | Issues: {issues}"
        elif action == "response_generated":
            content_text = "Synthesising final patient-facing response..."
        elif agent == "cdss" and action == "scores_computed":
            tools = log.get("tools_run") or []
            count = log.get("count", 0)
            selector = log.get("selector_reasoning", "")
            if count:
                content_text = f"CDSS ran {count} tool(s): {', '.join(tools)}"
            else:
                content_text = f"CDSS selector: no applicable scoring tools for current DDx"
            if selector:
                content_text += f" — {selector}"
        elif agent == "cdss" and action == "skip":
            content_text = f"CDSS skipped: {log.get('reason', 'no DDx available')}"
        elif agent == "cdss" and action == "error":
            content_text = f"CDSS error: {log.get('detail', 'unknown')}"
        elif agent == "cdss" and action == "fallback":
            tools = log.get("tools_run") or []
            content_text = f"CDSS fallback triggered — ran {', '.join(tools)} via deterministic rules"

        if content_text:
            await websocket.send_text(
                _ws_msg("agent_reasoning", agent=agent, content=content_text)
            )
            await _persist_log(session_id, agent, action or "reasoning", content=content_text)


async def _run_graph(
    websocket: WebSocket,
    graph,
    graph_input,
    config: dict,
    is_resume: bool = False,
    session_id: str | None = None,
):
    """Run LangGraph and stream node-level updates + LLM tokens to the client.

    Uses LangGraph's multi-mode streaming:
      - "updates": node-level state diffs, same as before (drives agent_transition,
        diagnosis_result, debate_challenge/response, interrupt handling).
      - "messages": (AIMessageChunk, metadata) tuples emitted per LLM token when
        the LLM has streaming=True. We forward Coordinator tokens to the client
        as `llm_token` events for a streaming typewriter UX. Other agents
        emit JSON fragments that aren't useful to render so we drop them.
    """
    try:
        if is_resume:
            stream_input = Command(resume=graph_input)
        else:
            stream_input = graph_input

        prev_agent = None
        # Captured during the cdss node's update event. graph.get_state() at
        # end-of-stream occasionally returns an empty cdss_scores dict under
        # LangGraph 0.2.60's TypedDict default-merge semantics, so we keep
        # our own copy to fall back on when writing diagnosis_result.
        captured_cdss: dict = {}

        async for mode, payload in graph.astream(
            stream_input, config=config, stream_mode=["updates", "messages"]
        ):
            # ── LLM token stream (S2/S6) ────────────────────────────────
            if mode == "messages":
                try:
                    message_chunk, metadata = payload
                except (TypeError, ValueError):
                    continue
                node = (metadata or {}).get("langgraph_node", "")
                # Only stream Coordinator tokens — other nodes emit
                # structured-output JSON fragments that would confuse the UI.
                if node != "coordinator":
                    continue
                token = getattr(message_chunk, "content", "") or ""
                if token:
                    await websocket.send_text(
                        _ws_msg("llm_token", agent="coordinator", content=token)
                    )
                continue

            # ── Node updates (existing logic) ───────────────────────────
            if mode != "updates":
                continue
            chunk = payload
            for node_name, update in chunk.items():
                # --- Handle interrupt (interviewer asking a question) ---
                if node_name == "__interrupt__":
                    # graph.get_state is sync; offload so we don't block the event loop
                    state = await asyncio.to_thread(graph.get_state, config)
                    for task in state.tasks:
                        if hasattr(task, "interrupts"):
                            for intr in task.interrupts:
                                val = intr.value if hasattr(intr, "value") else intr
                                if isinstance(val, dict):
                                    question = val.get("question", "")
                                else:
                                    question = str(val)
                                if question:
                                    await websocket.send_text(
                                        _ws_msg(
                                            "agent_message",
                                            agent="interviewer",
                                            content=question,
                                        )
                                    )
                                    await _persist_message(session_id, "assistant", question, agent="interviewer")
                    continue

                if not isinstance(update, dict):
                    continue

                # --- Agent transition event ---
                if node_name in AGENT_LABELS and node_name != prev_agent:
                    transition_content = f"{AGENT_LABELS[node_name]} is now working"
                    await websocket.send_text(
                        _ws_msg(
                            "agent_transition",
                            agent=node_name,
                            content=transition_content,
                        )
                    )
                    await _persist_log(session_id, node_name, "transition", content=transition_content)
                    prev_agent = node_name

                # --- Agent reasoning logs ---
                agent_logs = update.get("agent_logs", [])
                if agent_logs:
                    await _send_agent_logs(websocket, agent_logs, session_id)

                # --- Interviewer completion ---
                if node_name == "interviewer" and update.get("patient_history"):
                    reasoning_content = "History collection complete, handing off to Diagnostician"
                    await websocket.send_text(
                        _ws_msg(
                            "agent_reasoning",
                            agent="interviewer",
                            content=reasoning_content,
                        )
                    )
                    await _persist_log(session_id, "interviewer", "reasoning", content=reasoning_content)

                # --- Diagnostician completion ---
                if node_name == "diagnostician" and update.get("diagnosis"):
                    reasoning_content = "Differential diagnosis complete, handing off to Debate Round"
                    await websocket.send_text(
                        _ws_msg(
                            "agent_reasoning",
                            agent="diagnostician",
                            content=reasoning_content,
                        )
                    )
                    await _persist_log(session_id, "diagnostician", "reasoning", content=reasoning_content)

                # --- Critic completion (V1 legacy, kept for backward compat) ---
                if node_name == "critic":
                    critic_review = update.get("critic_review", {})
                    current_agent = update.get("current_agent", "")

                    if critic_review.get("approval") or current_agent == "complete":
                        critic_content = "Review approved, handing off to Coordinator"
                        await websocket.send_text(
                            _ws_msg(
                                "agent_reasoning",
                                agent="critic",
                                content=critic_content,
                            )
                        )
                        await _persist_log(session_id, "critic", "reasoning", content=critic_content)
                    elif critic_review.get("redirect_to"):
                        redirect = critic_review["redirect_to"]
                        critic_content = f"Review denied, redirecting to {AGENT_LABELS.get(redirect, redirect)}"
                        await websocket.send_text(
                            _ws_msg(
                                "agent_reasoning",
                                agent="critic",
                                content=critic_content,
                            )
                        )
                        await _persist_log(session_id, "critic", "reasoning", content=critic_content)

                # --- CDSS node completion: capture the scores dict ---
                # The transition / scores_computed agent_log lines are emitted
                # via the generic agent_logs handler above. Here we just stash
                # the raw cdss_scores dict so the coordinator handler can
                # write it into diagnosis_result even if graph.get_state()
                # returns it empty (see captured_cdss declaration).
                if node_name == "cdss":
                    cdss_update = update.get("cdss_scores")
                    if isinstance(cdss_update, dict) and cdss_update:
                        captured_cdss = cdss_update

                # --- Debate Round completion (V2) ---
                # Streams the structured Critic<->Diagnostician debate to the
                # frontend DebateView component in real time.
                if node_name == "debate_round":
                    current_agent = update.get("current_agent", "")
                    debate_outcome = update.get("debate_outcome") or {}
                    debate_rounds = update.get("debate_rounds") or []

                    # Emit individual challenge/response events from the latest round
                    if debate_rounds:
                        latest_round = debate_rounds[-1]
                        round_num = latest_round.get("round_number", len(debate_rounds))
                        for challenge in latest_round.get("challenges", []) or []:
                            await websocket.send_text(
                                _ws_msg("debate_challenge", agent="critic", data=challenge)
                            )
                            await _persist_log(
                                session_id, "debate_round", "debate_challenge",
                                content=f"R{round_num} challenge: {challenge.get('claim', '')[:100]}",
                            )
                        for response in latest_round.get("responses", []) or []:
                            await websocket.send_text(
                                _ws_msg("debate_response", agent="diagnostician", data=response)
                            )
                            await _persist_log(
                                session_id, "debate_round", "debate_response",
                                content=f"R{round_num} response: {response.get('action', '')}",
                            )

                    # Round summary as reasoning text
                    if current_agent == "complete" and debate_outcome:
                        verdict = debate_outcome.get("final_verdict", "resolved")
                        total = debate_outcome.get("total_challenges", 0)
                        accepted = debate_outcome.get("accepted", 0)
                        summary = (
                            f"Debate concluded after {len(debate_rounds)} round(s): "
                            f"{verdict} ({accepted}/{total} challenges accepted). "
                            f"Handing off to Coordinator."
                        )
                        await websocket.send_text(
                            _ws_msg("agent_reasoning", agent="debate_round", content=summary)
                        )
                        await _persist_log(session_id, "debate_round", "reasoning", content=summary)
                    elif current_agent == "debate":
                        await websocket.send_text(
                            _ws_msg(
                                "agent_reasoning",
                                agent="debate_round",
                                content="Unresolved challenges, continuing to next round...",
                            )
                        )

                # --- Coordinator completion (final response) ---
                if node_name == "coordinator":
                    coordinator_response = update.get("coordinator_response", "")
                    state = await asyncio.to_thread(graph.get_state, config)
                    state_vals = state.values if state else {}
                    diagnosis = state_vals.get("diagnosis", {})
                    critic_review = state_vals.get("critic_review", {})

                    await websocket.send_text(
                        _ws_msg(
                            "agent_message",
                            agent="coordinator",
                            content=coordinator_response,
                        )
                    )
                    await _persist_message(session_id, "assistant", coordinator_response, agent="coordinator")

                    debate_outcome = state_vals.get("debate_outcome", {})
                    # Prefer the live state value, fall back to whatever we
                    # captured during the cdss node update (see captured_cdss
                    # declaration for why this fallback exists).
                    cdss_scores = state_vals.get("cdss_scores") or captured_cdss

                    diagnosis_data = {
                        "differential_diagnosis": (diagnosis or {}).get(
                            "differential_diagnosis", []
                        ),
                        "recommended_tests": (diagnosis or {}).get(
                            "recommended_tests", []
                        ),
                        "reasoning_chain": (diagnosis or {}).get(
                            "reasoning_chain", ""
                        ),
                        "critic_review": critic_review or {},
                        "debate_outcome": debate_outcome or {},
                        "cdss_scores": _cdss_to_list(cdss_scores),
                        "coordinator_response": coordinator_response,
                    }
                    await websocket.send_text(
                        _ws_msg(
                            "diagnosis_result",
                            agent="coordinator",
                            content="Diagnostic workflow complete",
                            data=diagnosis_data,
                        )
                    )
                    await _persist_log(
                        session_id, "coordinator", "diagnosis_result",
                        data=diagnosis_data,
                    )
                    # Mark session as completed
                    try:
                        async with async_session() as db:
                            from app.db.models import Session
                            result = await db.execute(
                                select(Session).where(Session.id == session_id)
                            )
                            s = result.scalar_one_or_none()
                            if s:
                                s.status = "completed"
                                await db.commit()
                    except Exception as e:
                        logger.warning("Failed to mark session completed: %s", e)

    except Exception as e:
        logger.exception("Error running graph")
        await websocket.send_text(_ws_msg("error", content=str(e)))


@router.websocket("/ws/{session_id}")
async def websocket_chat(ws: WebSocket, session_id: str):
    await manager.connect(session_id, ws)

    # Access the graph and session tracker from app.state (set in lifespan)
    app = ws.app
    graph = getattr(app.state, "graph", None)

    if graph is None:
        await ws.send_text(
            _ws_msg("error", content="LangGraph not initialized. Server is starting up.")
        )
        await ws.close()
        manager.disconnect(session_id)
        return

    # Use the session_id as the LangGraph thread_id for checkpointer-based resume
    config = {"configurable": {"thread_id": session_id}}

    # graph_started is a connection-local flag that gates "first message" vs
    # "resume" path. On a fresh connection we must not assume False — if the
    # previous connection got interrupted mid-interview (interviewer asked a
    # follow-up, user's browser dropped), the LangGraph checkpoint still holds
    # a pending interrupt. Starting fresh would discard all interviewer context
    # and re-run the graph as if the next user reply is a brand-new complaint.
    #
    # Instead, probe the checkpoint: if state.next is non-empty, the graph is
    # paused at a node boundary — treat the next inbound message as a resume.
    graph_started = False
    # graph.get_state() is a synchronous SQLite call from LangGraph's
    # SqliteSaver. Calling it directly in this async handler would block the
    # uvicorn event loop for the duration of the I/O — under even moderate
    # concurrency (multiple WS connects in a short window) the loop can starve
    # and other requests start timing out. Two defenses:
    #   1) Offload to a worker thread via asyncio.to_thread, matching the
    #      pattern used elsewhere in this file (see lines 307, 454).
    #   2) Cap the probe with a 3s timeout. If the checkpoint store is slow or
    #      contended we treat the session as fresh rather than stalling the
    #      connection — the WS handler will still work, just without auto-resume.
    try:
        checkpoint = await asyncio.wait_for(
            asyncio.to_thread(graph.get_state, config),
            timeout=3.0,
        )
        if checkpoint is not None:
            has_pending = bool(getattr(checkpoint, "next", None))
            task_interrupts = any(
                getattr(t, "interrupts", None) for t in (getattr(checkpoint, "tasks", None) or [])
            )
            if has_pending or task_interrupts:
                graph_started = True
                logger.info(
                    "WS resume: session=%s pending_nodes=%s task_interrupts=%s",
                    session_id, getattr(checkpoint, "next", None), task_interrupts,
                )
    except asyncio.TimeoutError:
        logger.warning("Checkpoint probe timed out after 3s (session=%s) — treating as fresh", session_id)
    except Exception as e:
        logger.warning("Could not probe checkpoint for resume state: %s", e)

    # Send welcome greeting for new sessions (no existing messages)
    try:
        async with async_session() as db:
            from sqlalchemy import func as sa_func
            count_result = await db.execute(
                select(sa_func.count(Message.id)).where(Message.session_id == session_id)
            )
            msg_count = count_result.scalar() or 0
    except Exception as e:
        logger.warning("Failed to count existing messages for greeting: %s", e)
        msg_count = -1  # skip greeting on DB error

    if msg_count == 0:
        greeting = (
            "Hello! Welcome to MediChain. I'm your clinical interviewer and I'll be helping "
            "to understand your health concerns today.\n\n"
            "Before we begin, could you please tell me your name and briefly describe "
            "what's been troubling you?"
        )
        await ws.send_text(_ws_msg("agent_message", agent="interviewer", content=greeting))
        await _persist_message(session_id, "assistant", greeting, agent="interviewer")

    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg_data = json.loads(raw)
                user_message = msg_data.get("content", msg_data.get("message", raw))
            except json.JSONDecodeError:
                user_message = raw

            # Persist user message to DB
            await _persist_message(session_id, "user", user_message)

            # Auto-generate session title from first user message
            if not graph_started:
                title = user_message.strip()[:80]
                if len(user_message.strip()) > 80:
                    title = title.rsplit(" ", 1)[0] + "..."
                try:
                    async with async_session() as db:
                        from app.db.models import Session as SessionModel
                        result = await db.execute(
                            select(SessionModel).where(SessionModel.id == session_id)
                        )
                        s = result.scalar_one_or_none()
                        if s and s.title in ("Untitled Consultation", "New Consultation"):
                            s.title = title
                            await db.commit()
                except Exception as e:
                    logger.warning("Failed to update session title: %s", e)

            if graph_started:
                # Resuming after an interrupt (interviewer follow-up)
                transition_msg = "Response received, continuing consultation..."
                await ws.send_text(
                    _ws_msg(
                        "agent_transition",
                        agent="interviewer",
                        content=transition_msg,
                    )
                )
                await _persist_log(session_id, "interviewer", "transition", content=transition_msg)
                # Wrap in a task so a replacing connection can cancel it.
                task = asyncio.create_task(
                    _run_graph(
                        ws, graph, user_message, config,
                        is_resume=True, session_id=session_id,
                    )
                )
                manager.register_task(session_id, task)
                try:
                    await task
                except asyncio.CancelledError:
                    logger.info("Resume graph task cancelled: session=%s", session_id)
            else:
                # First message in this WebSocket session: load DB history for context
                graph_started = True
                history_messages = []
                try:
                    async with async_session() as db:
                        hist_result = await db.execute(
                            select(Message)
                            .where(Message.session_id == session_id)
                            .order_by(Message.created_at)
                        )
                        history_messages = _history_messages_from_db_rows(hist_result.scalars().all())
                except Exception as e:
                    logger.warning("Failed to load chat history: %s", e)

                # Look up session.llm_model so per-session provider routing
                # actually reaches the agents (was previously stored in DB but
                # never propagated; agents always read MEDICHAIN_LLM_MODEL).
                session_llm_model = None
                try:
                    async with async_session() as db:
                        from app.db.models import Session as SessionModel
                        result = await db.execute(
                            select(SessionModel).where(SessionModel.id == session_id)
                        )
                        sm = result.scalar_one_or_none()
                        session_llm_model = sm.llm_model if sm else None
                except Exception as e:
                    logger.warning("Could not load session.llm_model: %s", e)

                initial_input = {
                    "messages": history_messages,
                    "patient_history": None,
                    "diagnosis": None,
                    "critic_review": None,
                    "rag_context": None,
                    "iteration_count": 0,
                    "current_agent": "interviewer",
                    "coordinator_response": None,
                    "agent_logs": [],
                    # v2 fields
                    "debate_rounds": None,
                    "debate_outcome": None,
                    "cdss_scores": None,
                    "drug_interactions": None,
                    "llm_model": session_llm_model,
                    "session_id": session_id,
                }
                transition_msg = "Interviewer is starting the consultation..."
                await ws.send_text(
                    _ws_msg(
                        "agent_transition",
                        agent="interviewer",
                        content=transition_msg,
                    )
                )
                await _persist_log(session_id, "interviewer", "transition", content=transition_msg)
                task = asyncio.create_task(
                    _run_graph(
                        ws, graph, initial_input, config,
                        is_resume=False, session_id=session_id,
                    )
                )
                manager.register_task(session_id, task)
                try:
                    await task
                except asyncio.CancelledError:
                    logger.info("Initial graph task cancelled: session=%s", session_id)

    except WebSocketDisconnect:
        manager.disconnect(session_id)
    except Exception as e:
        logger.exception("WebSocket error: session %s", session_id)
        try:
            await ws.send_text(_ws_msg("error", content=str(e)))
        except Exception:
            pass
        manager.disconnect(session_id)
