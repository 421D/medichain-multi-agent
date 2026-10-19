from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tool_registry import tool_registry
from app.db.database import get_db
from app.db.models import AgentLog, Session

router = APIRouter(prefix="/api/v1/agents", tags=["Agents"])

# Note: session.llm_model is recorded for audit only — actual LLM selection
# is governed by the MEDICHAIN_LLM_MODEL env var read in agents/base.py.
# Per-session model switching is not currently honoured at runtime.
AVAILABLE_MODELS = ["kimi", "groq", "openai", "gemini", "gpt-4o", "gpt-4"]


class ModelConfig(BaseModel):
    session_id: str
    model: str


@router.get("/status")
async def agent_status():
    """Health check for the agent system."""
    return {
        "status": "ok",
        "available_models": AVAILABLE_MODELS,
        "available_tools": tool_registry.list_tools(),
    }


@router.post("/config")
async def update_model_config(data: ModelConfig, db: AsyncSession = Depends(get_db)):
    """Switch LLM model for a session at runtime."""
    result = await db.execute(
        select(Session).where(Session.id == str(data.session_id))
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if data.model not in AVAILABLE_MODELS:
        raise HTTPException(
            status_code=400,
            detail=f"Model must be one of: {AVAILABLE_MODELS}",
        )

    session.llm_model = data.model
    await db.commit()
    return {"detail": f"Model switched to {data.model}", "session_id": str(data.session_id)}


_ACTION_TO_EVENT_TYPE = {
    "transition": "transition",
    "reasoning": "reasoning",
    "diagnosis_result": "diagnosis",
    "llm_call": "reasoning",
    "rag_retrieval": "reasoning",
    "diagnosis_complete": "diagnosis",
    "review_complete": "reasoning",
    "response_generated": "message",
    "debate_complete": "reasoning",
    "debate_challenge": "reasoning",
    "debate_response": "reasoning",
}


@router.get("/logs/{session_id}")
async def get_agent_logs(session_id: str, db: AsyncSession = Depends(get_db)):
    """Get agent reasoning logs for a session.

    Response shape is kept in sync with the frontend AgentLog type:
      { id, session_id, agent, event_type, content, timestamp, completed }
    so the same component can render both REST-loaded logs and live
    WebSocket-streamed logs without a transform layer.
    """
    result = await db.execute(
        select(AgentLog)
        .where(AgentLog.session_id == session_id)
        .order_by(AgentLog.created_at)
    )
    logs = result.scalars().all()
    return [
        {
            "id": str(log.id),
            "session_id": str(log.session_id),
            "agent": log.agent_name,
            "event_type": _ACTION_TO_EVENT_TYPE.get(log.action, "reasoning"),
            "content": (log.output_data or {}).get("content", "") or log.action,
            "timestamp": log.created_at.isoformat() if log.created_at else None,
            "completed": True,
            # Legacy fields preserved for any existing consumer
            "agent_name": log.agent_name,
            "action": log.action,
            "output_data": log.output_data,
            "tool_calls": log.tool_calls,
            "duration_ms": log.duration_ms,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }
        for log in logs
    ]
