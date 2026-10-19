# MediChain - Installation Manual

> **Last verified:** 2026-04-28 on macOS 14 / Ubuntu 22.04 / Docker 24.0+

This is the **single-source install manual**. It covers prerequisites, container build, runtime configuration, smoke tests, full test-suite execution, and known issues.

---

## 1. Prerequisites

| Tool | Minimum Version | Purpose |
|------|-----------------|---------|
| Docker | 24.0+ (with Compose v2) | Backend, PostgreSQL, Redis containers |
| Node.js | 20 LTS | Frontend dev/build (Vite + React 18) |
| Python | 3.12 (only if running tests/demo outside Docker) | Local pytest, `demo_orchestration.py` |
| Git | 2.30+ | Source checkout |
| 8 GB RAM | - | ChromaDB + LangGraph + Postgres comfortably |

> **Docker is the primary deployment target.** Items below marked *(local)* are alternatives if Docker is unavailable.

### LLM Provider API Keys

You need **at least one** of the following keys. The default is **Kimi (Moonshot)** because of its 128K context window and free tier; any single working key lets the full pipeline run.

| Provider | Where to get a key |
|----------|--------------------|
| Kimi (default) | https://platform.moonshot.cn/console/api-keys |
| Groq | https://console.groq.com/keys |
| OpenAI | https://platform.openai.com/api-keys |
| Gemini | https://aistudio.google.com/apikey |

PubMed and RxNorm (used by the MCP servers) are **anonymous-access**, no key required.

---

## 2. Quick Start (Docker - recommended for testers)

The repo ships a **production compose stack**: backend + frontend +
Postgres + Redis, all containerised, no local Node/Python required.

```bash
# 1. Clone the repo
git clone https://github.com/421D/medichain-multi-agent.git
cd medichain-multi-agent

# 2. Configure secrets - only one LLM key is needed
cp .env.example .env
# Edit .env: set MEDICHAIN_LLM_MODEL and the matching <provider>_API_KEY

# 3. Build & start the full stack
docker compose up -d --build

# 4. Wait ~60-90s for the LangGraph knowledge base to load into memory.
#    Then verify everything is healthy:
curl http://localhost:8000/health
# {"status":"healthy","langgraph_ready":true}
docker compose ps          # all 4 services should show (healthy)

# 5. Open the app
open http://localhost:8080      # React UI (nginx-served, proxies /api + /ws)
open http://localhost:8000/docs # Swagger API explorer
```

### Local frontend dev (alternative to the dockerised frontend)

If you prefer hot-module
reload during development, keep `docker-compose.override.yml` in place (it
disables the prod
frontend container) and run Vite directly:

```bash
cd frontend-v3-creative
npm install --legacy-peer-deps
npm run dev          # http://localhost:8080 with HMR
```

The Vite dev server proxies `/api` and `/ws` to `localhost:8000`.

---

## 3. Configuration Reference

`.env` (backend, read by Docker Compose):

| Variable | Default | Notes |
|----------|---------|-------|
| `MEDICHAIN_LLM_MODEL` | `kimi` | One of `kimi`, `groq`, `openai`, `gemini` |
| `KIMI_API_KEY` / `GROQ_API_KEY` / `OPENAI_API_KEY` / `GEMINI_API_KEY` | - | Set the one matching `MEDICHAIN_LLM_MODEL` |
| `DATABASE_URL` | `postgresql+asyncpg://medichain:medichain@db:5432/medichain` | Compose-internal hostname `db` |
| `REDIS_URL` | `redis://redis:6379` | Compose-internal hostname `redis` |
| `MAX_DEBATE_ROUNDS` | `2` | Cap on Critic<->Diagnostician turns per case |
| `CORS_ORIGINS` | `http://localhost:8080,http://localhost:5173,http://localhost:3000` | Comma-separated; must include the frontend origin |
| `APP_ENV` | `development` | Set to `production` to suppress debug logs |

`frontend-v3-creative/.env.local` (frontend, optional):

| Variable | Default | Notes |
|----------|---------|-------|
| `VITE_API_BASE_URL` | `http://localhost:8000` | Backend HTTP base |
| `VITE_USE_MOCK` | `false` | If `true`, the UI falls back to bundled mock data on API failure (useful for offline grading) |

---

## 4. Smoke Tests (no API keys required)

These verify the Docker stack and core pipeline without any external LLM calls.

```bash
# (a) Backend health
curl http://localhost:8000/health
# -> {"status":"healthy","langgraph_ready":true}

# (b) MCP tool registry (live PubMed)
curl -X POST http://localhost:8000/api/v1/tools/query \
     -H "Content-Type: application/json" \
     -d '{"tool_name":"pubmed_search","query":"acute meningitis"}'
# -> JSON list of citations

# (c) Offline orchestration demo (no LLM key needed; uses canned transcripts)
docker compose exec backend python demo_orchestration.py
# -> walks the V2 debate pipeline end-to-end with a chest-pain case
```

---

## 5. Full Test Suite

### Backend tests (212 unit/integration, default)

```bash
# Inside the running backend container
docker compose exec backend pytest -q

# Or locally (requires Python 3.12 venv):
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest -q
```

Expected output: **212 passed, 3 deselected** (the 3 deselected are `live`-marked WebSocket integration tests that require a running backend on `:8000` - see below).

### Live integration tests (require backend running)

```bash
# In one terminal: ensure backend is up
docker compose up -d

# In another:
pytest -m live tests/test_ws_concurrent.py        # WebSocket concurrency / reconnect / malformed payload
python tests/test_ws_live.py                      # End-to-end chest pain case via WS
python tests/test_cdss_mcp_live.py                # CDSS MCP server stdio round-trip
```

### Coverage report

```bash
pytest --cov --cov-report=term --cov-report=html
open htmlcov/index.html
```

### Evaluation harness (7 ground-truth clinical cases)

```bash
# Offline mode (no LLM calls - uses cached pipeline output)
python -m harness.run --offline

# Live mode (calls real LLM provider - costs API credits, ~10 min)
python -m harness.run --live

# Per-case
python -m harness.run --case EVAL-003
```

Latest report: `reports/evaluation_2026-04-21.md` - Top-1 100%, Top-3 100%, Safety 85.7% on 7 cases.

### Frontend tests

```bash
cd frontend-v3-creative
npm install
npm test                # vitest + @testing-library/react
```

---

## 6. Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `langgraph_ready: false` after 90s | ChromaDB embedding model still downloading | Wait ~2 min on first start. The knowledge-base corpora are not in the repo (licensed, ~670 MB); see `docs/rag_guide.md` and place the JSONL files in `data/`. Without them the pipeline still runs, but RAG returns no references. |
| `connection refused` on `:5432` | Postgres slow to boot | `docker compose ps` - wait until `db` shows `healthy` |
| `401` from Kimi / OpenAI | Wrong / expired API key | Verify `.env`, then `docker compose restart backend` |
| Frontend shows mock data | Backend unreachable + `VITE_USE_MOCK=true` | Check `curl localhost:8000/health`; either start backend or set `VITE_USE_MOCK=false` |
| `pytest_asyncio` plugin missing | Local venv not synced | `pip install -r requirements.txt` (it's pinned in there) |
| Port 8000 / 5432 / 6379 already in use | Another service occupying the port | Edit `docker-compose.yml` port mapping or stop the conflicting service |

---

## 7. Project Layout (testers' quick map)

```
medichain/
|-- app/                       FastAPI server (REST + WebSocket)
|-- agents/                    LangGraph 4-agent pipeline
|-- orchestrator/              LangGraph topology + state
|-- prompts/                   System prompts for each agent
|-- cdss/                      Clinical Decision Support MCP server (6 scoring tools)
|-- harness/                   Evaluation harness (7 ground-truth cases)
|-- rag/                       ChromaDB knowledge base + retriever
|-- models/                    Pydantic schemas + LLM provider factory
|-- frontend-v3-creative/      React 18 + Vite + Tailwind UI
|-- tests/                     215 pytest cases (212 unit/integration + 3 live)
|-- docker-compose.yml         Backend + Postgres + Redis
|-- Dockerfile                 Multi-stage; non-root runtime; HEALTHCHECK wired
`-- INSTALL.md                 you are here
```

See `README.md` Architecture for the V2 debate-protocol diagram.

---

## 8. Issues / Questions

Please open a GitHub issue.
