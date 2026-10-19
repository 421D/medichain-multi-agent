"""
MCP Client — connects to the MediChain MCP Server via stdio transport.

Strategy: spawn a fresh subprocess + stdio session for every tool call.
We previously tried to keep a long-lived session for performance, but
`mcp.client.stdio.stdio_client` and `ClientSession` use anyio task groups
bound to the task that entered them; reusing them from a different request
task triggers `RuntimeError: Attempted to exit cancel scope in a different
task`. Spawning per-call costs ~200-500ms but is correct under FastAPI's
concurrent request model.

`init_mcp_session()` and `close_mcp_session()` are kept as no-ops so the
existing FastAPI lifespan in `app/main.py` doesn't need to change.
"""

import json
import logging
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

logger = logging.getLogger(__name__)

# Path to the root MCP server script (PubMed / OpenFDA / ICD-11 tools).
# CDSS tools live in cdss/mcp_server.py and are NOT exposed through this
# client — they are intended for use as a standalone MCP server.
MCP_SERVER_PATH = str(Path(__file__).resolve().parent.parent.parent / "mcp_server.py")


def _server_params() -> StdioServerParameters:
    return StdioServerParameters(command="python3", args=[MCP_SERVER_PATH])


async def init_mcp_session() -> None:
    """No-op. The persistent-session optimisation was removed; see module docstring."""
    return None


async def close_mcp_session() -> None:
    """No-op. The persistent-session optimisation was removed; see module docstring."""
    return None


async def _extract_json(result: Any) -> dict:
    """Extract the first JSON-decodable text chunk from an MCP CallToolResult."""
    for content in result.content:
        if hasattr(content, "text"):
            try:
                return json.loads(content.text)
            except json.JSONDecodeError:
                return {"text": content.text}
    return {"error": "No text content in MCP response"}


async def call_mcp_tool(tool_name: str, arguments: dict) -> dict:
    """Call a tool on the MediChain MCP server (one-shot subprocess)."""
    async with stdio_client(_server_params()) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments=arguments)
            return await _extract_json(result)


async def list_mcp_tools() -> list[dict]:
    """List all tools available on the MCP server (one-shot subprocess)."""
    async with stdio_client(_server_params()) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.list_tools()
            return [{"name": t.name, "description": t.description} for t in result.tools]


async def search_pubmed(query: str) -> dict:
    """Convenience wrapper for PubMed search via MCP."""
    return await call_mcp_tool("pubmed_search", {"query": query})


async def lookup_drug(drug_name: str) -> dict:
    """Convenience wrapper for drug lookup (OpenFDA drug label) via MCP."""
    return await call_mcp_tool("drugbank_lookup", {"drug_name": drug_name})


async def lookup_icd11(condition: str) -> dict:
    """Convenience wrapper for ICD-11 code lookup via MCP."""
    return await call_mcp_tool("icd11_lookup", {"condition": condition})
