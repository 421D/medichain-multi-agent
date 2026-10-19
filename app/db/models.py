import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, JSON
from sqlalchemy.orm import DeclarativeBase, relationship

# Use String(36) for UUID compatibility with SQLite
UUID_TYPE = String(36)


def _uuid_str():
    return str(uuid.uuid4())


def _utcnow():
    """Timezone-aware UTC default. Naive datetimes (datetime.utcnow) drift
    in the frontend because `new Date(iso)` interprets timestamps without a
    TZ marker as local time."""
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id = Column(UUID_TYPE, primary_key=True, default=_uuid_str)
    username = Column(String(100), unique=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    sessions = relationship("Session", back_populates="user")


class Session(Base):
    __tablename__ = "sessions"

    id = Column(UUID_TYPE, primary_key=True, default=_uuid_str)
    # PostgreSQL does NOT auto-index foreign keys (unlike MySQL/InnoDB), so
    # every column we filter or order on at the API surface gets an explicit
    # index. The dashboard's /sessions/stats and /sessions/ both
    # ORDER BY created_at DESC and filter by status — without indexes those
    # become full-table scans once we exceed a few hundred sessions.
    user_id = Column(UUID_TYPE, ForeignKey("users.id"), nullable=True, index=True)
    title = Column(String(255), default="New Consultation")
    status = Column(String(20), default="active", index=True)
    llm_model = Column(String(50), default="gpt-4")
    created_at = Column(DateTime(timezone=True), default=_utcnow, index=True)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    user = relationship("User", back_populates="sessions")
    messages = relationship("Message", back_populates="session", cascade="all, delete-orphan")
    agent_logs = relationship("AgentLog", back_populates="session", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"

    id = Column(UUID_TYPE, primary_key=True, default=_uuid_str)
    # session_id is the dominant filter for /chat/{session_id}; created_at is
    # used for chronological replay. Both belong on a btree index.
    session_id = Column(UUID_TYPE, ForeignKey("sessions.id", ondelete="CASCADE"), index=True)
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    metadata_ = Column("metadata", JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow, index=True)

    session = relationship("Session", back_populates="messages")


class AgentLog(Base):
    __tablename__ = "agent_logs"

    id = Column(UUID_TYPE, primary_key=True, default=_uuid_str)
    # /agents/logs/{session_id} filters by session_id + action ("diagnosis_result")
    # and orders by created_at DESC. session_id is the dominant filter.
    session_id = Column(UUID_TYPE, ForeignKey("sessions.id", ondelete="CASCADE"), index=True)
    agent_name = Column(String(50), nullable=False)
    action = Column(String(50), nullable=False, index=True)
    input_data = Column(JSON, nullable=True)
    output_data = Column(JSON, nullable=True)
    tool_calls = Column(JSON, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow, index=True)

    session = relationship("Session", back_populates="agent_logs")
