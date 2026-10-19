"""Prompt caching helpers (Q5).

MediChain supports multiple providers (Kimi/OpenAI/Gemini/Groq) and each
handles prompt caching differently. This module centralises the decision:

- **OpenAI (gpt-4o family)**: automatic caching on any prompt prefix >=1024
  tokens. No code change needed — just keep the prefix stable (system prompt
  + static RAG wrapper must come before dynamic user content). Cache hit is
  reported back in `response.usage.prompt_tokens_details.cached_tokens` and
  our tracer (app/core/tracer.py) already surfaces that.

- **Anthropic**: explicit `cache_control: {type: "ephemeral"}`
  markers on message content blocks; 5-minute TTL; up to 4 breakpoints per
  request; cached tokens billed at 10% of normal input cost.

- **Kimi/Moonshot**: supports context caching via a separate
  `POST /v1/caching` endpoint. Cache is referenced by `cache_id` in
  subsequent calls. More involved to wire up — not yet implemented here.

- **Groq**: no prompt caching (all-in-memory inference). No-op.

- **Gemini**: `cachedContent` API, separate from the chat call. Not yet wired.

### Design invariant
We keep agent nodes provider-agnostic by always using plain
`SystemMessage`/`HumanMessage` pairs and relying on automatic caching
(OpenAI) plus the ordering discipline (system → static RAG wrapper →
dynamic input). When we later add explicit cache_control for Anthropic, we
use `apply_anthropic_cache_marker` at the site that builds messages.

### Ordering rule (enforced by convention, tested by tracer metrics)
For every agent:
  1. Start with `SystemMessage(content=<fully static system prompt>)`.
  2. Follow with any **static** few-shot or schema description blocks.
  3. Put dynamic content (patient_history, debate_history, rag_results)
     inside the final `HumanMessage`.

If we accidentally inject dynamic content into the SystemMessage, the
OpenAI prefix cache misses every call. The tracer's cache_hit_rate field
is the regression detector for this invariant.
"""
from __future__ import annotations

from typing import Iterable

from langchain_core.messages import BaseMessage, SystemMessage


def apply_anthropic_cache_marker(
    messages: Iterable[BaseMessage],
    *,
    mark_system: bool = True,
) -> list[BaseMessage]:
    """Add Anthropic cache_control markers to the last static block.

    Anthropic caches the prefix up to the cache_control marker. We mark the
    end of the SystemMessage (the last thing we know is static).

    Returns a new list; does not mutate inputs. Only effective when the
    downstream LLM is Anthropic; OpenAI/Kimi/Groq silently ignore the field
    because Anthropic `cache_control` is an Anthropic-specific extension.
    """
    out: list[BaseMessage] = []
    for msg in messages:
        if mark_system and isinstance(msg, SystemMessage):
            # Promote string content to the list-of-blocks form so we can
            # attach cache_control to the final block.
            content = msg.content
            if isinstance(content, str):
                marked = [{
                    "type": "text",
                    "text": content,
                    "cache_control": {"type": "ephemeral"},
                }]
                out.append(SystemMessage(content=marked))
                continue
        out.append(msg)
    return out


def cache_hit_rate(input_tokens: int, cached_tokens: int) -> float:
    """Safe ratio cached / total-input. Returns 0 when denominator is zero."""
    if not input_tokens:
        return 0.0
    return max(0.0, min(1.0, cached_tokens / input_tokens))
