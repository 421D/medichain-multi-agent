from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.models import AgentLog, Message, Session

router = APIRouter(prefix="/api/v1/sessions", tags=["Sessions"])


# -- Schemas --

class SessionCreate(BaseModel):
    title: str = "New Consultation"
    llm_model: str = "gpt-4"


class SessionUpdate(BaseModel):
    title: str | None = None
    status: str | None = None
    llm_model: str | None = None


class SessionResponse(BaseModel):
    id: str
    title: str
    status: str
    llm_model: str
    created_at: datetime | None = None
    message_count: int = 0
    preliminary_diagnosis: str | None = None
    safety_flags: list[str] = []
    agent_participation: list[str] = []

    model_config = ConfigDict(from_attributes=True)


# -- Routes --

@router.post("/", response_model=SessionResponse)
async def create_session(data: SessionCreate, db: AsyncSession = Depends(get_db)):
    session = Session(title=data.title, llm_model=data.llm_model)
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


@router.get("/")
async def list_sessions(db: AsyncSession = Depends(get_db)):
    # Query sessions with message counts
    stmt = (
        select(
            Session,
            func.count(Message.id).label("message_count"),
        )
        .outerjoin(Message, Message.session_id == Session.id)
        .group_by(Session.id)
        .order_by(Session.created_at.desc())
    )
    rows = (await db.execute(stmt)).all()
    session_ids = [s.id for s, _ in rows]

    # Batch-fetch diagnosis results and agent participation
    diag_map: dict[str, dict] = {}
    agents_map: dict[str, list[str]] = {}
    if session_ids:
        diag_result = await db.execute(
            select(AgentLog)
            .where(AgentLog.session_id.in_(session_ids), AgentLog.action == "diagnosis_result")
            .order_by(AgentLog.session_id, AgentLog.created_at.desc())
        )
        for log in diag_result.scalars().all():
            if log.output_data and log.session_id not in diag_map:
                diag_map[log.session_id] = log.output_data

        agent_result = await db.execute(
            select(AgentLog.session_id, AgentLog.agent_name)
            .where(AgentLog.session_id.in_(session_ids))
            .distinct()
        )
        for sid, aname in agent_result.all():
            agents_map.setdefault(sid, []).append(aname)

    results = []
    for s, count in rows:
        diag_data = diag_map.get(s.id, {})
        ddx = diag_data.get("differential_diagnosis", [])
        critic = diag_data.get("critic_review", {})
        preliminary = ddx[0].get("diagnosis", "") if ddx else None
        safety_flags = [critic["safety_flag"]] if critic.get("safety_flag") else []

        results.append(SessionResponse(
            id=s.id,
            title=s.title,
            status=s.status,
            llm_model=s.llm_model,
            created_at=s.created_at,
            message_count=count,
            preliminary_diagnosis=preliminary,
            safety_flags=safety_flags,
            agent_participation=agents_map.get(s.id, []),
        ))
    return results


@router.get("/stats")
async def get_session_stats(db: AsyncSession = Depends(get_db)):
    """Dashboard top-row stats: session counts + message totals + latest activity.

    Defined before /{session_id} so the path doesn't match the variable route.
    """
    total_sessions_stmt = select(func.count(Session.id))
    active_sessions_stmt = select(func.count(Session.id)).where(Session.status == "active")
    total_messages_stmt = select(func.count(Message.id))
    latest_date_stmt = select(func.max(Session.created_at))

    total_sessions = (await db.execute(total_sessions_stmt)).scalar() or 0
    active_sessions = (await db.execute(active_sessions_stmt)).scalar() or 0
    total_messages = (await db.execute(total_messages_stmt)).scalar() or 0
    latest_date = (await db.execute(latest_date_stmt)).scalar()

    return {
        "total_sessions": total_sessions,
        "active_sessions": active_sessions,
        "total_messages": total_messages,
        "latest_session_date": latest_date.isoformat() if latest_date else None,
    }


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    msg_count = (await db.execute(
        select(func.count(Message.id)).where(Message.session_id == session_id)
    )).scalar() or 0

    diag_log = (await db.execute(
        select(AgentLog)
        .where(AgentLog.session_id == session_id, AgentLog.action == "diagnosis_result")
        .order_by(AgentLog.created_at.desc())
        .limit(1)
    )).scalar_one_or_none()
    diag_data = diag_log.output_data if diag_log and diag_log.output_data else {}
    ddx = diag_data.get("differential_diagnosis", [])
    critic = diag_data.get("critic_review", {})
    preliminary = ddx[0].get("diagnosis", "") if ddx else None
    safety_flags = [critic["safety_flag"]] if critic.get("safety_flag") else []

    agent_rows = (await db.execute(
        select(AgentLog.agent_name)
        .where(AgentLog.session_id == session_id)
        .distinct()
    )).all()
    agent_participation = [a[0] for a in agent_rows]

    return SessionResponse(
        id=session.id,
        title=session.title,
        status=session.status,
        llm_model=session.llm_model,
        created_at=session.created_at,
        message_count=msg_count,
        preliminary_diagnosis=preliminary,
        safety_flags=safety_flags,
        agent_participation=agent_participation,
    )


@router.put("/{session_id}", response_model=SessionResponse)
async def update_session(session_id: str, data: SessionUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if data.title is not None:
        session.title = data.title
    if data.status is not None:
        session.status = data.status
    if data.llm_model is not None:
        session.llm_model = data.llm_model
    await db.commit()
    await db.refresh(session)
    return session


@router.get("/{session_id}/diagnosis")
async def get_session_diagnosis(session_id: str, db: AsyncSession = Depends(get_db)):
    """Return the full structured diagnosis result for a session.

    This is persisted by the WebSocket handler when the coordinator completes.
    The frontend calls this on mount to restore DiagnosisPanel / DebateView state
    that was originally delivered via WebSocket events.
    """
    result = await db.execute(
        select(AgentLog)
        .where(AgentLog.session_id == session_id, AgentLog.action == "diagnosis_result")
        .order_by(AgentLog.created_at.desc())
        .limit(1)
    )
    log = result.scalar_one_or_none()
    if not log or not log.output_data:
        return None
    return log.output_data


@router.delete("/{session_id}")
async def delete_session(session_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    await db.delete(session)
    await db.commit()
    return {"detail": "Deleted"}
