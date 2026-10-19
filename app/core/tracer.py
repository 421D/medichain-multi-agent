"""MediChain LLM tracer — zero-dependency local observability.

Records every LLM call as one JSONL line in reports/traces/{YYYY-MM-DD}.jsonl:
  {ts, run_id, parent_run_id, node, model, latency_ms, input_tokens,
   output_tokens, cached_tokens, session_id, error}

Why local JSONL instead of Langfuse/Phoenix:
  - Zero external dependency, runs anywhere the codebase runs.
  - Boss can grep/jq/duckdb the file directly for ad-hoc analysis.
  - Langfuse integration can be layered on top later by redirecting the
    sink; the callback shape is already compatible.

Usage:
    from app.core.tracer import MediChainTracer
    handler = MediChainTracer(node="diagnostician", session_id=sid)
    llm = ChatOpenAI(..., callbacks=[handler])
    llm.invoke(messages)

The tracer is opt-in per-call via `callbacks=[handler]` rather than
globally registered so that unit tests / pure-Python regression tests
don't write trace files on disk.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import BaseMessage
from langchain_core.outputs import LLMResult

logger = logging.getLogger(__name__)

# Singleton trace directory; created lazily on first write.
TRACE_DIR = Path(__file__).resolve().parent.parent.parent / "reports" / "traces"

# Serialize JSONL writes — many async LLM calls can finish concurrently and
# partial-line interleaving would corrupt the file for downstream parsers.
_WRITE_LOCK = threading.Lock()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _today_file() -> Path:
    TRACE_DIR.mkdir(parents=True, exist_ok=True)
    return TRACE_DIR / f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.jsonl"


def _extract_usage(response: LLMResult) -> dict[str, int]:
    """Extract token usage from an LLMResult across OpenAI/Anthropic/Kimi shapes.

    Different providers put token counts in different places; this walks the
    common fields. Missing counts default to 0 so downstream aggregations
    (sum(input_tokens)) don't need None-guards.
    """
    usage = {"input_tokens": 0, "output_tokens": 0, "cached_tokens": 0}

    def _apply(tu: dict) -> None:
        """Merge a token_usage-shaped dict into usage, preferring non-zero values."""
        if not isinstance(tu, dict) or not tu:
            return
        inp = int(tu.get("prompt_tokens") or tu.get("input_tokens") or 0)
        out = int(tu.get("completion_tokens") or tu.get("output_tokens") or 0)
        if inp and not usage["input_tokens"]:
            usage["input_tokens"] = inp
        if out and not usage["output_tokens"]:
            usage["output_tokens"] = out
        if not usage["cached_tokens"]:
            details = tu.get("prompt_tokens_details") or tu.get("input_token_details") or {}
            usage["cached_tokens"] = int(
                details.get("cached_tokens")
                or details.get("cache_read")
                or tu.get("cache_read_input_tokens")
                or 0
            )

    try:
        # 1. langchain_openai style: llm_output.token_usage
        if response.llm_output and isinstance(response.llm_output, dict):
            _apply(response.llm_output.get("token_usage") or response.llm_output.get("usage") or {})

        # 2. First generation: usage_metadata / generation_info / response_metadata
        #    Kimi and other OpenAI-compatible providers often only populate these.
        if response.generations:
            first_gen = response.generations[0][0] if response.generations[0] else None
            if first_gen:
                # 2a. AIMessage.usage_metadata (LangChain 0.3+)
                msg = getattr(first_gen, "message", None)
                if msg is not None:
                    _apply(getattr(msg, "usage_metadata", None) or {})
                    # 2b. AIMessage.response_metadata.token_usage (OpenAI-compatible)
                    rm = getattr(msg, "response_metadata", None) or {}
                    if isinstance(rm, dict):
                        _apply(rm.get("token_usage") or rm.get("usage") or {})
                # 2c. Generation.generation_info (ChatOpenAI returns it here)
                gi = getattr(first_gen, "generation_info", None) or {}
                if isinstance(gi, dict):
                    _apply(gi.get("token_usage") or gi.get("usage") or {})
    except Exception as e:  # never let telemetry break the LLM call
        logger.debug("tracer: usage extract failed: %s", e)
    return usage


class MediChainTracer(BaseCallbackHandler):
    """Callback handler that writes one JSONL record per LLM call.

    Construct per-call (cheap) and pass via `callbacks=[...]` so each line
    carries the right `node` and `session_id` tags.
    """

    # Don't run sync callbacks on the async event loop thread — LangChain
    # will dispatch sync handlers automatically when on_llm_end is async.
    # We implement both to be safe regardless of the LLM client.
    raise_error = False  # swallow handler exceptions, never crash the LLM call

    def __init__(
        self,
        node: str = "unknown",
        session_id: str | None = None,
        model_hint: str | None = None,
    ):
        self.node = node
        self.session_id = session_id
        self.model_hint = model_hint  # fallback when the provider doesn't echo the model name
        self._start_times: dict[str, float] = {}
        self._models: dict[str, str] = {}

    # ─── Chat model lifecycle ────────────────────────────────────────────

    def on_chat_model_start(
        self,
        serialized: dict[str, Any],
        messages: list[list[BaseMessage]],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        self._start_times[str(run_id)] = time.perf_counter()
        # Model name lives in different keys depending on provider wrapper.
        model = (
            (serialized or {}).get("kwargs", {}).get("model")
            or (serialized or {}).get("kwargs", {}).get("model_name")
            or (serialized or {}).get("name")
            or self.model_hint
            or "unknown"
        )
        self._models[str(run_id)] = model

    def on_llm_start(
        self,
        serialized: dict[str, Any],
        prompts: list[str],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        # Non-chat LLMs go through this path; store start time the same way.
        self._start_times[str(run_id)] = time.perf_counter()
        model = (
            (serialized or {}).get("kwargs", {}).get("model")
            or (serialized or {}).get("name")
            or self.model_hint
            or "unknown"
        )
        self._models[str(run_id)] = model

    def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        rid = str(run_id)
        start = self._start_times.pop(rid, None)
        latency_ms = int((time.perf_counter() - start) * 1000) if start else -1
        model = self._models.pop(rid, self.model_hint or "unknown")
        usage = _extract_usage(response)

        self._emit({
            "ts": _now_iso(),
            "run_id": rid,
            "parent_run_id": str(parent_run_id) if parent_run_id else None,
            "node": self.node,
            "model": model,
            "latency_ms": latency_ms,
            "input_tokens": usage["input_tokens"],
            "output_tokens": usage["output_tokens"],
            "cached_tokens": usage["cached_tokens"],
            "session_id": self.session_id,
            "error": None,
        })

    def on_llm_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        rid = str(run_id)
        start = self._start_times.pop(rid, None)
        latency_ms = int((time.perf_counter() - start) * 1000) if start else -1
        model = self._models.pop(rid, self.model_hint or "unknown")
        self._emit({
            "ts": _now_iso(),
            "run_id": rid,
            "parent_run_id": str(parent_run_id) if parent_run_id else None,
            "node": self.node,
            "model": model,
            "latency_ms": latency_ms,
            "input_tokens": 0,
            "output_tokens": 0,
            "cached_tokens": 0,
            "session_id": self.session_id,
            "error": f"{type(error).__name__}: {str(error)[:200]}",
        })

    # ─── Sink ────────────────────────────────────────────────────────────

    def _emit(self, record: dict) -> None:
        if os.getenv("MEDICHAIN_TRACE", "1").lower() in ("0", "false", "off"):
            return
        try:
            line = json.dumps(record, ensure_ascii=False) + "\n"
            with _WRITE_LOCK:
                with _today_file().open("a", encoding="utf-8") as f:
                    f.write(line)
        except Exception as e:
            logger.debug("tracer: emit failed: %s", e)


def summarize_today() -> dict:
    """Aggregate today's trace file into per-node stats. CLI-friendly."""
    path = _today_file()
    if not path.exists():
        return {"date": datetime.now(timezone.utc).strftime('%Y-%m-%d'), "calls": 0}

    per_node: dict[str, dict] = {}
    total_calls = 0
    with path.open(encoding="utf-8") as f:
        for line in f:
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            node = rec.get("node", "unknown")
            stats = per_node.setdefault(node, {
                "calls": 0, "total_latency_ms": 0, "total_in": 0,
                "total_out": 0, "total_cached": 0, "errors": 0,
            })
            stats["calls"] += 1
            stats["total_latency_ms"] += max(rec.get("latency_ms") or 0, 0)
            stats["total_in"] += rec.get("input_tokens") or 0
            stats["total_out"] += rec.get("output_tokens") or 0
            stats["total_cached"] += rec.get("cached_tokens") or 0
            if rec.get("error"):
                stats["errors"] += 1
            total_calls += 1

    # Derived fields
    for node, s in per_node.items():
        s["avg_latency_ms"] = s["total_latency_ms"] // s["calls"] if s["calls"] else 0
        s["cache_hit_rate"] = (
            s["total_cached"] / s["total_in"] if s["total_in"] else 0.0
        )

    return {
        "date": datetime.now(timezone.utc).strftime('%Y-%m-%d'),
        "calls": total_calls,
        "per_node": per_node,
    }


if __name__ == "__main__":
    # Quick CLI: python -m app.core.tracer
    import pprint
    pprint.pp(summarize_today())
