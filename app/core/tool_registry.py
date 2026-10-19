"""
MCP Tool Registry.
Manages external medical tool/API connections for agent reasoning.

Supported tools (Sprint 2):
- PubMed API: literature search
- DrugBank: drug interaction checks
- WHO ICD-11: diagnosis code lookup
"""

import hashlib
import json
from datetime import datetime, timezone

import httpx

from app.utils.logger import get_logger

logger = get_logger(__name__)

# In-memory cache (Redis in Sprint 2)
_cache: dict[str, dict] = {}
CACHE_TTL_SECONDS = 3600  # 1 hour


class ToolResult:
    """Standardized result from any external tool call."""

    def __init__(self, tool_name: str, query: str, results: list[dict], raw_response: dict | None = None):
        self.tool_name = tool_name
        self.query = query
        self.results = results
        self.raw_response = raw_response
        self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return {
            "tool_name": self.tool_name,
            "query": self.query,
            "results": self.results,
            "timestamp": self.timestamp,
        }

    def to_citations(self) -> list[dict]:
        """Convert results to citation format for frontend display."""
        return [
            {
                "source": self.tool_name,
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "snippet": r.get("snippet", ""),
            }
            for r in self.results
        ]


def _cache_key(tool_name: str, query: str) -> str:
    return hashlib.md5(f"{tool_name}:{query}".encode()).hexdigest()


class ToolRegistry:
    """Central registry for all external medical tools."""

    def __init__(self):
        self._tools: dict[str, callable] = {}
        self._register_defaults()

    def _register_defaults(self):
        self._tools["pubmed"] = self._search_pubmed
        self._tools["drugbank"] = self._search_drugbank
        self._tools["icd11"] = self._search_icd11

    def list_tools(self) -> list[str]:
        return list(self._tools.keys())

    async def call(self, tool_name: str, query: str) -> ToolResult:
        """Call a registered tool with caching."""
        if tool_name not in self._tools:
            raise ValueError(f"Unknown tool: {tool_name}. Available: {self.list_tools()}")

        # Check cache
        key = _cache_key(tool_name, query)
        if key in _cache:
            logger.info(f"Cache hit: {tool_name} query='{query}'")
            cached = _cache[key]
            return ToolResult(tool_name=tool_name, query=query, results=cached["results"])

        # Call tool
        logger.info(f"Calling tool: {tool_name} query='{query}'")
        result = await self._tools[tool_name](query)

        # Cache result
        _cache[key] = {"results": result.results, "timestamp": result.timestamp}
        return result

    # -- PubMed --

    async def _search_pubmed(self, query: str) -> ToolResult:
        """Search PubMed for medical literature."""
        base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

        async with httpx.AsyncClient(timeout=15.0) as client:
            # Step 1: search for article IDs
            search_resp = await client.get(
                f"{base_url}/esearch.fcgi",
                params={
                    "db": "pubmed",
                    "term": query,
                    "retmax": 5,
                    "retmode": "json",
                },
            )
            search_data = search_resp.json()
            id_list = search_data.get("esearchresult", {}).get("idlist", [])

            if not id_list:
                return ToolResult(tool_name="pubmed", query=query, results=[])

            # Step 2: fetch article summaries
            summary_resp = await client.get(
                f"{base_url}/esummary.fcgi",
                params={
                    "db": "pubmed",
                    "id": ",".join(id_list),
                    "retmode": "json",
                },
            )
            summary_data = summary_resp.json()
            articles = summary_data.get("result", {})

            results = []
            for pmid in id_list:
                article = articles.get(pmid, {})
                if isinstance(article, dict):
                    results.append({
                        "title": article.get("title", ""),
                        "authors": ", ".join(
                            a.get("name", "") for a in article.get("authors", [])[:3]
                        ),
                        "journal": article.get("source", ""),
                        "year": article.get("pubdate", "")[:4],
                        "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                        "snippet": article.get("title", ""),
                        "pmid": pmid,
                    })

            return ToolResult(
                tool_name="pubmed",
                query=query,
                results=results,
                raw_response=summary_data,
            )

    # -- DrugBank (stub) --

    async def _search_drugbank(self, query: str) -> ToolResult:
        """Search DrugBank for drug interactions — Sprint 2 full implementation."""
        logger.warning("DrugBank integration is a stub — returning mock data")
        return ToolResult(
            tool_name="drugbank",
            query=query,
            results=[
                {
                    "title": f"Drug interaction data for: {query}",
                    "url": f"https://go.drugbank.com/unearth/q?query={query}",
                    "snippet": "Full DrugBank integration planned for Sprint 2",
                }
            ],
        )

    # -- WHO ICD-11 (stub) --

    async def _search_icd11(self, query: str) -> ToolResult:
        """Search WHO ICD-11 for diagnosis codes — Sprint 2 full implementation."""
        logger.warning("ICD-11 integration is a stub — returning mock data")
        return ToolResult(
            tool_name="icd11",
            query=query,
            results=[
                {
                    "title": f"ICD-11 lookup for: {query}",
                    "url": f"https://icd.who.int/browse/2024-01/mms/en#search={query}",
                    "snippet": "Full ICD-11 integration planned for Sprint 2",
                }
            ],
        )


# Global singleton
tool_registry = ToolRegistry()
