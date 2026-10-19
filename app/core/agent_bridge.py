"""
Agent Bridge — connects Person 6's FastAPI backend to Winston's LangGraph orchestration.

This module connects the REST chat endpoint to the V2 pipeline:
Interviewer -> Diagnostician (with RAG) -> Debate Round (Critic <-> Diagnostician) -> Coordinator

For the REST API chat endpoint, the graph runs synchronously (single turn):
- The interviewer does NOT use interrupt/resume (no WebSocket here).
- Instead, it processes the user message through the full pipeline in one pass.
- For multi-turn interviewing, use the WebSocket endpoint (app/api/websocket.py).
"""

import asyncio
import logging
from datetime import datetime, timezone
from uuid import UUID

from langgraph.errors import GraphInterrupt

from app.core.mcp_client import search_pubmed, lookup_drug
from app.core.tool_registry import tool_registry
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Module-level graph singleton — set by main.py lifespan via set_graph()
_graph = None


def set_graph(graph):
    """Set the shared LangGraph instance (called from main.py lifespan)."""
    global _graph
    _graph = graph


class AgentResponse:
    """Standardized response from the agent pipeline."""

    def __init__(
        self,
        content: str,
        agent_name: str = "coordinator",
        citations: list[dict] | None = None,
        reasoning_steps: list[dict] | None = None,
    ):
        self.content = content
        self.agent_name = agent_name
        self.citations = citations or []
        self.reasoning_steps = reasoning_steps or []
        self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return {
            "content": self.content,
            "agent_name": self.agent_name,
            "citations": self.citations,
            "reasoning_steps": self.reasoning_steps,
            "timestamp": self.timestamp,
        }


def _run_graph_sync(
    user_message: str,
    chat_history: list[dict] | None,
    thread_id: str,
    llm_model: str | None = None,
) -> dict:
    """Run the LangGraph orchestration synchronously.

    Returns a dict with keys: coordinator_response, diagnosis, critic_review, agent_logs.
    """
    global _graph
    if _graph is None:
        from orchestrator.graph import create_graph
        _graph = create_graph()  # fallback if lifespan hasn't set it

    graph = _graph

    # Build messages from chat history. Normalize role names — REST callers
    # commonly send OpenAI-style {"role": "user"|"assistant"} but interviewer_node
    # only recognizes {"role": "human"|"ai"}. Without this mapping, multi-turn
    # REST history gets dropped on the agent side and context shrinks each turn.
    _role_map = {
        "user": "human", "patient": "human", "human": "human",
        "assistant": "ai", "ai": "ai", "bot": "ai",
        "system": "system",
    }
    messages = []
    if chat_history:
        for msg in chat_history[-10:]:
            raw_role = (msg.get("role") or "human").lower()
            role = _role_map.get(raw_role, "human")
            messages.append({"role": role, "content": msg.get("content", "")})
    # Ensure the latest user message is included
    if not messages or messages[-1].get("content") != user_message:
        messages.append({"role": "human", "content": user_message})

    initial_state = {
        "messages": messages,
        "patient_history": None,
        "diagnosis": None,
        "critic_review": None,
        "rag_context": None,
        "iteration_count": 0,
        "current_agent": "interviewer",
        "coordinator_response": None,
        "agent_logs": [],
        "llm_model": llm_model,
        "session_id": thread_id or None,
    }

    # Use the session_id as thread_id so the LangGraph checkpointer shares
    # state with the WebSocket path (which also keys on session_id). Earlier
    # versions used a fresh UUID per REST call, which produced a brand-new
    # graph state each time and never restored the WS-built history.
    config = {"configurable": {"thread_id": thread_id or "rest-anon"}}

    # Run the graph — invoke runs all nodes to completion.
    # REST path does not support multi-turn interrupt/resume (use WebSocket for that).
    # Distinguish expected GraphInterrupt (interviewer pauses for a question) from
    # real errors so LLM failures, schema validation issues, etc. aren't silently swallowed.
    try:
        final_state = graph.invoke(initial_state, config=config)
    except GraphInterrupt as e:
        logger.info("Graph interrupted by interviewer (REST path, expected): %s", e)
        try:
            state_snapshot = graph.get_state(config)
            final_state = state_snapshot.values if state_snapshot else initial_state
        except Exception as snapshot_err:
            logger.warning("Could not read state snapshot after interrupt: %s", snapshot_err)
            final_state = initial_state
    except Exception:
        logger.exception("Graph execution failed (non-interrupt)")
        raise

    return {
        "coordinator_response": final_state.get("coordinator_response", ""),
        "diagnosis": final_state.get("diagnosis", {}),
        "critic_review": final_state.get("critic_review", {}),
        "agent_logs": final_state.get("agent_logs", []),
        "messages": final_state.get("messages", []),
    }


async def process_message(
    session_id: UUID,
    user_message: str,
    llm_model: str | None = "gpt-4",
    chat_history: list[dict] | None = None,
) -> AgentResponse:
    """
    Main entry point for processing a user message through the agent pipeline.

    Connects to the V2 LangGraph orchestration (Interviewer -> Diagnostician -> Debate Round -> Coordinator).
    Also enriches the response with PubMed citations from Person 6's MCP tool registry.

    Args:
        session_id: The diagnostic session ID
        user_message: The patient's message
        llm_model: Which LLM to use
        chat_history: Previous messages in this session

    Returns:
        AgentResponse with the AI's reply, citations, and reasoning steps
    """
    logger.info(f"Processing message for session {session_id}")

    # Step 1: PubMed enrichment.
    # Earlier versions sent the entire raw patient message (including names
    # and personal context) to NCBI's public eUtils API. That's both a
    # privacy issue and a poor query — clinical terms get diluted by
    # narrative. We now skip the bridge-level PubMed call entirely; if the
    # diagnostician needs literature, it can request it through MCP with a
    # focused query of its choice.
    citations: list[dict] = []

    # Step 2: Run the LangGraph orchestration in a thread (it uses sync LangChain calls).
    # Pass the session_id as thread_id so the graph's checkpointer shares state
    # with the WS path (which also keys on session_id).
    try:
        graph_result = await asyncio.to_thread(
            _run_graph_sync, user_message, chat_history, str(session_id), llm_model
        )
    except Exception as e:
        logger.error(f"LangGraph orchestration failed: {e}")
        graph_result = None

    # Step 3: Extract response from graph result
    if graph_result and graph_result.get("coordinator_response"):
        response_text = graph_result["coordinator_response"]
    elif graph_result and graph_result.get("messages"):
        # Fallback: if the interviewer interrupted, use the last AI message
        ai_messages = [
            m for m in graph_result["messages"]
            if isinstance(m, dict) and m.get("role") == "ai"
        ]
        if ai_messages:
            response_text = ai_messages[-1].get("content", "")
        else:
            response_text = (
                "I'd like to learn more about your symptoms. "
                "Could you tell me more about what you're experiencing?"
            )
    else:
        response_text = (
            "I apologize, but I'm having trouble processing your request right now. "
            "Please try again in a moment."
        )

    # Step 4: Build reasoning steps from agent logs
    reasoning_steps = []
    if graph_result and graph_result.get("agent_logs"):
        for log in graph_result["agent_logs"]:
            reasoning_steps.append({
                "agent": log.get("agent", "unknown"),
                "action": log.get("action", ""),
                "detail": log.get("reasoning") or log.get("detail") or log.get("status") or "",
            })
    else:
        # V2 fallback reasoning steps (used only when agent_logs is empty)
        reasoning_steps = [
            {"agent": "interviewer", "action": "history_collection", "detail": user_message},
            {"agent": "diagnostician", "action": "differential_diagnosis", "detail": "RAG-enhanced"},
            {"agent": "debate_round", "action": "structured_debate", "detail": "Critic <-> Diagnostician, MAX_DEBATE_ROUNDS env"},
            {"agent": "coordinator", "action": "compile_response", "detail": "synthesised"},
        ]

    return AgentResponse(
        content=response_text,
        agent_name="coordinator",
        citations=citations,
        reasoning_steps=reasoning_steps,
    )
