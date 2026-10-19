"""add indexes on hot-path columns (session_id, status, action, created_at)

Revision ID: 9f4a2c8d1e7b
Revises: 8671be970ecc
Create Date: 2026-04-29

PostgreSQL does not automatically index foreign keys, so every dashboard
query (`/sessions/stats`, `/sessions/`, `/chat/{session_id}`,
`/agents/logs/{session_id}`) was doing a sequential scan against `sessions`,
`messages`, and `agent_logs`. This migration adds btree indexes on the
columns we actually filter/order by at the API surface, mirroring the
`index=True` flags now declared in `app/db/models.py`.
"""
from alembic import op


revision = "9f4a2c8d1e7b"
down_revision = "8671be970ecc"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # sessions: dashboard sorts by created_at DESC and filters status='active'.
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])
    op.create_index("ix_sessions_status", "sessions", ["status"])
    op.create_index("ix_sessions_created_at", "sessions", ["created_at"])

    # messages: chat history loads with WHERE session_id = ? ORDER BY created_at.
    op.create_index("ix_messages_session_id", "messages", ["session_id"])
    op.create_index("ix_messages_created_at", "messages", ["created_at"])

    # agent_logs: timeline view + diagnosis_result lookup both filter by
    # (session_id, action) and order by created_at DESC.
    op.create_index("ix_agent_logs_session_id", "agent_logs", ["session_id"])
    op.create_index("ix_agent_logs_action", "agent_logs", ["action"])
    op.create_index("ix_agent_logs_created_at", "agent_logs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_agent_logs_created_at", table_name="agent_logs")
    op.drop_index("ix_agent_logs_action", table_name="agent_logs")
    op.drop_index("ix_agent_logs_session_id", table_name="agent_logs")
    op.drop_index("ix_messages_created_at", table_name="messages")
    op.drop_index("ix_messages_session_id", table_name="messages")
    op.drop_index("ix_sessions_created_at", table_name="sessions")
    op.drop_index("ix_sessions_status", table_name="sessions")
    op.drop_index("ix_sessions_user_id", table_name="sessions")
