# --- Stage 1: builder ---
FROM python:3.12-slim AS builder

WORKDIR /build

# Build deps for asyncpg / chromadb native extensions
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt

# --- Stage 2: runtime ---
FROM python:3.12-slim

WORKDIR /app

# curl is needed for HEALTHCHECK; rest stays minimal
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /wheels /wheels
COPY requirements.txt .
RUN pip install --no-cache-dir --no-index --find-links=/wheels -r requirements.txt \
    && rm -rf /wheels

COPY . .

# Non-root runtime user
RUN useradd --uid 1000 --create-home --shell /bin/bash medichain \
    && chown -R medichain:medichain /app
USER medichain

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

# Production: 1 uvicorn worker. LangGraph's MemorySaver is in-process so
# multi-worker would split checkpointer state across processes (breaks
# interrupt/resume). docker-compose overrides this command in development
# to enable --reload + alembic migrations.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
