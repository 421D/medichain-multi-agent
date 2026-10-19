"""RAG retriever with in-process LRU cache.

The diagnostician builds its query from `chief_complaint + hpi + ros`. In the
harness and in real sessions, identical or near-identical queries often
recur (repeat test cases, follow-up messages in the same session, common
chief complaints like "chest pain"). Caching the (query, top_k) → results
tuple skips the ChromaDB roundtrip (including embedding) for hits.

We key on the (query, top_k) pair. The cache is per-process and bounded to
512 entries (~a few MB at top_k=5). If the knowledge base is reloaded
mid-process, call `retriever.clear_cache()`.
"""
from __future__ import annotations

import logging
import threading
from collections import OrderedDict

from rag.knowledge_base import KnowledgeBase

logger = logging.getLogger(__name__)


class Retriever:
    # Class-level to keep the cache warm across Retriever rebuilds inside the
    # same process (tests that recreate the retriever won't pay cold-start
    # embedding cost on every run).
    _CACHE_MAX = 512

    def __init__(self, knowledge_base: KnowledgeBase):
        self._kb = knowledge_base
        self._cache: OrderedDict[tuple[str, int], list[dict]] = OrderedDict()
        self._cache_lock = threading.Lock()
        self._hits = 0
        self._misses = 0

    def retrieve(self, query: str, top_k: int = 5) -> list[dict]:
        """Retrieve top_k relevant medical knowledge entries for a given query."""
        key = (query, top_k)
        with self._cache_lock:
            if key in self._cache:
                # LRU touch
                self._cache.move_to_end(key)
                self._hits += 1
                cached = self._cache[key]
                logger.debug("retriever cache hit for %r (top_k=%d)", query[:60], top_k)
                # Return a shallow copy so callers can mutate safely.
                return [dict(e) for e in cached]
            self._misses += 1

        results = self._kb.query(query_text=query, n_results=top_k)
        logger.info("Retrieved %d results for query: %s", len(results), query[:80])

        with self._cache_lock:
            self._cache[key] = results
            self._cache.move_to_end(key)
            while len(self._cache) > self._CACHE_MAX:
                self._cache.popitem(last=False)

        return [dict(e) for e in results]

    def clear_cache(self) -> None:
        """Reset the retrieval cache. Call after reloading the KB."""
        with self._cache_lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0

    def cache_stats(self) -> dict:
        """For observability — surface hit/miss ratio in traces if desired."""
        with self._cache_lock:
            total = self._hits + self._misses
            return {
                "hits": self._hits,
                "misses": self._misses,
                "size": len(self._cache),
                "hit_rate": (self._hits / total) if total else 0.0,
            }
