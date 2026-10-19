import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.agent_bridge import process_message
from app.db.database import get_db
from app.db.models import Message, Session

router = APIRouter(prefix="/api/v1/chat", tags=["Chat"])


# -- Schemas --

class ChatMessageIn(BaseModel):
    session_id: str
    content: str


class ChatMessageOut(BaseModel):
    id: str
    session_id: str
    role: str
    content: str
    agent: str | None = None
    citations: list[dict] = []
    metadata_: dict | None = None
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_message(cls, msg: Message) -> "ChatMessageOut":
        """Build a response model that surfaces `agent` and `citations` from
        the message's metadata JSON (populated by the WebSocket handler), so
        reloaded history renders the same agent badges + citations as live chat.

        `metadata_` is typed as JSON in SQLAlchemy but some drivers return a
        string instead of a parsed dict; guard against that explicitly.
        """
        raw_meta = msg.metadata_
        if isinstance(raw_meta, str):
            try:
                raw_meta = json.loads(raw_meta)
            except (json.JSONDecodeError, TypeError):
                raw_meta = None
        meta = raw_meta if isinstance(raw_meta, dict) else {}
        citations = meta.get("citations") or []
        if not isinstance(citations, list):
            citations = []
        agent = meta.get("agent") if isinstance(meta.get("agent"), str) else None
        return cls(
            id=str(msg.id),
            session_id=str(msg.session_id),
            role=msg.role,
            content=msg.content,
            agent=agent,
            citations=citations,
            metadata_=meta if meta else None,
            created_at=msg.created_at,
        )


class ChatResponseOut(BaseModel):
    user_message: ChatMessageOut
    ai_response: ChatMessageOut
    citations: list[dict] = []
    reasoning_steps: list[dict] = []


# -- Routes --

@router.post("/", response_model=ChatResponseOut)
async def send_message(data: ChatMessageIn, db: AsyncSession = Depends(get_db)):
    # Verify session exists
    result = await db.execute(select(Session).where(Session.id == data.session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Save user message
    user_msg = Message(session_id=data.session_id, role="user", content=data.content)
    db.add(user_msg)
    await db.commit()
    await db.refresh(user_msg)

    # Get chat history for context
    history_result = await db.execute(
        select(Message)
        .where(Message.session_id == data.session_id)
        .order_by(Message.created_at)
    )
    history = [
        {"role": m.role, "content": m.content}
        for m in history_result.scalars().all()
    ]

    # Process through agent pipeline
    agent_response = await process_message(
        session_id=data.session_id,
        user_message=data.content,
        llm_model=session.llm_model,
        chat_history=history,
    )

    # Save AI response
    ai_msg = Message(
        session_id=data.session_id,
        role="assistant",
        content=agent_response.content,
        metadata_={
            "agent": agent_response.agent_name,
            "citations": agent_response.citations,
            "reasoning": agent_response.reasoning_steps,
        },
    )
    db.add(ai_msg)
    await db.commit()
    await db.refresh(ai_msg)

    return ChatResponseOut(
        user_message=ChatMessageOut.from_message(user_msg),
        ai_response=ChatMessageOut.from_message(ai_msg),
        citations=agent_response.citations,
        reasoning_steps=agent_response.reasoning_steps,
    )


@router.get("/{session_id}", response_model=list[ChatMessageOut])
async def get_chat_history(session_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.created_at)
    )
    return [ChatMessageOut.from_message(m) for m in result.scalars().all()]
