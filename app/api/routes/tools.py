from fastapi import APIRouter
from pydantic import BaseModel

from app.core.mcp_client import call_mcp_tool, list_mcp_tools
from app.core.tool_registry import tool_registry

router = APIRouter(prefix="/api/v1/tools", tags=["MCP Tools"])


class ToolQuery(BaseModel):
    tool_name: str
    query: str


@router.get("/")
async def list_tools():
    """List all available MCP tools."""
    try:
        mcp_tools = await list_mcp_tools()
        return {"tools": mcp_tools, "protocol": "MCP"}
    except Exception:
        # Fallback to legacy registry
        return {"tools": tool_registry.list_tools(), "protocol": "legacy"}


@router.post("/query")
async def query_tool(data: ToolQuery):
    """Query an external medical tool via MCP (with legacy fallback).

    Returns 200 for recognized tools + error in body for unknown tools.
    Never raises 500 — unknown or broken tools degrade gracefully.
    """
    # Map legacy tool names to MCP tool names
    mcp_name_map = {
        "pubmed": "pubmed_search",
        "drugbank": "drugbank_lookup",
        "icd11": "icd11_lookup",
    }
    mcp_arg_map = {
        "pubmed_search": {"query": data.query},
        "drugbank_lookup": {"drug_name": data.query},
        "icd11_lookup": {"condition": data.query},
    }

    mcp_tool = mcp_name_map.get(data.tool_name, data.tool_name)
    args = mcp_arg_map.get(mcp_tool, {"query": data.query})

    # Try MCP first
    try:
        result = await call_mcp_tool(mcp_tool, args)
        return {"tool": mcp_tool, "protocol": "MCP", "result": result}
    except Exception as mcp_err:
        # Don't silently swallow — surface to logs so failures are diagnosable.
        import logging
        logging.getLogger(__name__).warning(
            "MCP call '%s' failed (%s); falling back to legacy registry.",
            mcp_tool, mcp_err,
        )

    # Fall back to legacy tool registry
    try:
        result = await tool_registry.call(data.tool_name, data.query)
        return {
            "tool": data.tool_name,
            "protocol": "legacy",
            "result": result.to_dict(),
            "mcp_error": "unavailable",
        }
    except Exception as legacy_err:
        # Both MCP and legacy failed — unknown or broken tool
        return {
            "tool": data.tool_name,
            "protocol": "none",
            "result": None,
            "error": f"Tool '{data.tool_name}' is not available: {legacy_err}",
            "available_tools": ["pubmed", "drugbank", "icd11"],
        }
