import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from app.core.tracer import MediChainTracer

load_dotenv()

# --- Provider configuration ---
# Kimi/Moonshot (Winston's default)
KIMI_BASE_URL = "https://api.moonshot.cn/v1"
KIMI_MODEL = "kimi-latest"

# Groq (DC's default)
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
GROQ_MODEL = "llama-3.3-70b-versatile"

# Gemini (via OpenAI-compatible endpoint)
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
GEMINI_MODEL = "gemini-2.0-flash"


def _get_provider(model_override: str | None = None) -> str:
    """Get the configured LLM provider.

    Resolution order:
      1. `model_override` (per-call, e.g. session.llm_model from REST/WS state)
      2. `MEDICHAIN_LLM_MODEL` environment variable
      3. "kimi" default
    `model_override` is normalised — concrete model names like "gpt-4o" are
    mapped to their provider key ("openai") so that downstream switch works.
    """
    raw = (model_override or os.getenv("MEDICHAIN_LLM_MODEL", "kimi")).lower().strip()
    # Map concrete model names back to provider keys (the API exposes both
    # via /agents/config; downstream get_llm only understands provider keys).
    aliases = {
        "gpt-4": "openai",
        "gpt-4o": "openai",
        "gpt-4o-mini": "openai",
        "kimi-latest": "kimi",
        "moonshot-v1-32k": "kimi",
        "moonshot-v1-8k": "kimi",
        "gemini-2.0-flash": "gemini",
        "llama-3.3-70b-versatile": "groq",
    }
    return aliases.get(raw, raw)


def get_llm(
    temperature: float = 0.3,
    model_override: str | None = None,
    node: str = "unknown",
    session_id: str | None = None,
) -> ChatOpenAI:
    """Get a ChatOpenAI instance based on the configured provider.

    Supports: kimi (default), groq, openai, gemini.
    Set MEDICHAIN_LLM_MODEL environment variable for the global default,
    or pass `model_override` (e.g. session.llm_model) for per-call routing.

    When `node` is provided, every call through this LLM writes a JSONL
    trace record to reports/traces/{today}.jsonl. Disable by setting
    MEDICHAIN_TRACE=0. `session_id` threads the session through the trace
    so we can join traces per-session.
    """
    provider = _get_provider(model_override)
    tracer = MediChainTracer(node=node, session_id=session_id)

    if provider == "groq":
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY environment variable is not set.")
        return ChatOpenAI(
            model=GROQ_MODEL,
            api_key=api_key,
            base_url=GROQ_BASE_URL,
            temperature=temperature,
            max_tokens=8192,
            streaming=True,  # S2/S6: per-token callbacks feed LangGraph stream_mode="messages"
            callbacks=[tracer],
        )

    elif provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set.")
        # gpt-4o: 128K context + 16K output, safer than gpt-4 (8K total)
        return ChatOpenAI(
            model="gpt-4o",
            api_key=api_key,
            temperature=temperature,
            max_tokens=8192,
            streaming=True,  # S2/S6: per-token callbacks feed LangGraph stream_mode="messages"
            callbacks=[tracer],
        )

    elif provider == "gemini":
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable is not set.")
        return ChatOpenAI(
            model=GEMINI_MODEL,
            api_key=api_key,
            base_url=GEMINI_BASE_URL,
            temperature=temperature,
            max_tokens=8192,
            streaming=True,  # S2/S6: per-token callbacks feed LangGraph stream_mode="messages"
            callbacks=[tracer],
        )

    else:
        # Default: kimi/moonshot
        api_key = os.getenv("KIMI_API_KEY")
        if not api_key:
            raise ValueError("KIMI_API_KEY environment variable is not set.")
        return ChatOpenAI(
            model=KIMI_MODEL,
            api_key=api_key,
            base_url=KIMI_BASE_URL,
            temperature=temperature,
            max_tokens=8192,
            streaming=True,  # S2/S6: per-token callbacks feed LangGraph stream_mode="messages"
            callbacks=[tracer],
        )


def get_structured_llm(
    output_schema: type[BaseModel],
    temperature: float = 0.3,
    model_override: str | None = None,
    node: str = "unknown",
    session_id: str | None = None,
):
    llm = get_llm(
        temperature=temperature,
        model_override=model_override,
        node=node,
        session_id=session_id,
    )
    return llm.with_structured_output(output_schema)
