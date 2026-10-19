import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import agents, chat, evaluation, session, tools
from app.api.websocket import router as ws_router
from app.db.database import engine
from app.db.models import Base
from app.utils.logger import get_logger

logger = get_logger(__name__)


def _init_langgraph():
    """Synchronous initialisation of LangGraph components.

    Runs in a thread so the async lifespan can await it without blocking
    the event loop (ChromaDB and embedding model loading are CPU-bound).
    """
    from orchestrator.graph import create_graph
    from rag.knowledge_base import KnowledgeBase
    from rag.retriever import Retriever
    from agents.diagnostician import set_retriever

    logger.info("Loading medical knowledge base...")
    kb = KnowledgeBase()
    count = kb.load()
    logger.info("Knowledge base loaded with %d entries.", count)

    retriever = Retriever(kb)
    set_retriever(retriever)

    graph = create_graph()
    logger.info("LangGraph compiled and ready.")

    return graph, kb


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create DB tables — this is a fallback for environments that don't run
    # alembic (e.g. local SQLite dev). In production the alembic migrations
    # already created everything via the docker-compose command, so we
    # tolerate "duplicate table" errors here rather than failing startup.
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables ensured.")
    except Exception as e:
        if "already exists" in str(e).lower():
            logger.info("Schema already present (alembic), skipping create_all.")
        else:
            raise

    # Initialise LangGraph + knowledge base in a thread (CPU-bound work)
    try:
        graph, kb = await asyncio.to_thread(_init_langgraph)
        app.state.graph = graph
        app.state.knowledge_base = kb

        from app.core.agent_bridge import set_graph
        set_graph(graph)

        logger.info("LangGraph and knowledge base stored in app.state.")
    except Exception as e:
        logger.error("Failed to initialise LangGraph: %s", e)
        logger.warning("WebSocket endpoint will return errors until LangGraph is available.")
        app.state.graph = None
        app.state.knowledge_base = None

    # MCP lifecycle hook. The current client intentionally uses one-shot
    # subprocess sessions per tool call; these no-ops keep startup/shutdown
    # wiring stable without holding a cross-request stdio session.
    from app.core.mcp_client import init_mcp_session, close_mcp_session
    await init_mcp_session()

    yield

    try:
        await close_mcp_session()
    except Exception as e:
        logger.warning("Error closing MCP session: %s", e)
    logger.info("Shutting down.")


app = FastAPI(
    title="MediChain API",
    description="Multi-Agent Clinical Diagnostic System",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS — allow frontend dev servers by default, override via CORS_ORIGINS env var
# (comma-separated). Keeps the same 3 localhost defaults so local dev is unchanged.
_default_cors = "http://localhost:8080,http://localhost:5173,http://localhost:3000"
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", _default_cors).split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(session.router)
app.include_router(chat.router)
app.include_router(agents.router)
app.include_router(tools.router)
app.include_router(evaluation.router)
app.include_router(ws_router)


@app.get("/", tags=["Health"])
async def root():
    return {
        "status": "ok",
        "service": "MediChain Backend",
        "version": "0.1.0",
    }


@app.get("/health", tags=["Health"])
async def health():
    graph_ready = getattr(app.state, "graph", None) is not None
    return {"status": "healthy", "langgraph_ready": graph_ready}
