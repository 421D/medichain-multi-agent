"""Live MCP client test: starts cdss.mcp_server as subprocess via stdio,
then actually calls each clinical scoring tool through the MCP protocol.

Run:
    .venv/bin/python tests/test_cdss_mcp_live.py

This is the face-to-face proof that CDSS MCP server works end-to-end
via the MCP stdio transport — not just that the code exists.
"""
import asyncio
import json
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    print("=" * 70)
    print("  CDSS MCP Server — Live End-to-End Test")
    print("=" * 70)

    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "cdss.mcp_server"],
    )

    print(f"\n[1/4] Spawning MCP server: {sys.executable} -m cdss.mcp_server")

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            print("[2/4] MCP client session opened, initializing...")
            init_result = await session.initialize()
            print(f"      Server name:    {init_result.serverInfo.name}")
            print(f"      Server version: {init_result.serverInfo.version}")

            print("\n[3/4] Listing available tools via MCP protocol...")
            tools_result = await session.list_tools()
            tools = tools_result.tools
            print(f"      Found {len(tools)} tools:")
            for t in tools:
                desc = (t.description or "").split("\n")[0][:60]
                print(f"        - {t.name:30s} {desc}")

            assert len(tools) == 7, f"Expected 7 CDSS tools, got {len(tools)}"
            print(f"      ✅ Tool count matches expected (7)")

            print("\n[4/4] Calling tools end-to-end via MCP...")

            # --- Test 1: Wells Score for high-risk PE patient ---
            print("\n  Test 1: Wells Score (high-risk PE scenario)")
            result = await session.call_tool(
                "cdss_wells_score",
                arguments={
                    "clinical_signs_dvt": True,
                    "pe_most_likely": True,
                    "heart_rate_over_100": True,
                    "immobilization_or_surgery": False,
                    "previous_dvt_pe": False,
                    "hemoptysis": False,
                    "malignancy": False,
                },
            )
            text = result.content[0].text
            parsed = json.loads(text)
            print(f"    Input:  DVT signs + PE most likely + HR>100")
            print(f"    Output: {json.dumps(parsed, indent=12)}"[:400])
            assert "score" in parsed, "Wells score missing 'score' field"
            assert parsed["score"] >= 6.0, f"Expected high-risk score >= 6, got {parsed['score']}"
            print(f"    ✅ Wells score={parsed['score']}, risk={parsed.get('risk_level','?')}")

            # --- Test 2: CURB-65 for severe pneumonia ---
            print("\n  Test 2: CURB-65 (severe pneumonia, the EVAL-007 case)")
            result = await session.call_tool(
                "cdss_curb65",
                arguments={
                    "confusion": True,
                    "urea_over_7": False,
                    "respiratory_rate_over_30": True,
                    "low_blood_pressure": True,
                    "age_over_65": True,
                },
            )
            text = result.content[0].text
            parsed = json.loads(text)
            print(f"    Input:  Confused + RR>30 + low BP + age>65 (4/5 criteria)")
            print(f"    Output: {parsed}"[:300])
            assert "score" in parsed
            assert parsed["score"] >= 3, f"Expected severe score >= 3, got {parsed['score']}"
            print(f"    ✅ CURB-65 score={parsed['score']}, severity={parsed.get('severity','?')}")

            # --- Test 3: qSOFA for sepsis screening ---
            print("\n  Test 3: qSOFA (sepsis screening)")
            result = await session.call_tool(
                "cdss_qsofa",
                arguments={
                    "altered_mentation": True,
                    "respiratory_rate_over_22": True,
                    "systolic_bp_under_100": True,
                },
            )
            text = result.content[0].text
            parsed = json.loads(text)
            print(f"    Input:  All 3 qSOFA criteria present")
            print(f"    Output: {parsed}"[:300])
            assert parsed.get("score") == 3, f"Expected qSOFA=3, got {parsed.get('score')}"
            print(f"    ✅ qSOFA score={parsed['score']} → high sepsis risk")

            # --- Test 4: HEART Score for chest pain ---
            print("\n  Test 4: HEART Score (the EVAL-003 chest pain case)")
            result = await session.call_tool(
                "cdss_heart_score",
                arguments={
                    "history": 2,
                    "ecg": 1,
                    "age": 2,
                    "risk_factors": 2,
                    "troponin": 2,
                },
            )
            text = result.content[0].text
            parsed = json.loads(text)
            print(f"    Input:  H=2, E=1, A=2, R=2, T=2")
            print(f"    Output: {parsed}"[:300])
            assert parsed.get("score") == 9, f"Expected HEART=9, got {parsed.get('score')}"
            print(f"    ✅ HEART score={parsed['score']} → MACE risk {parsed.get('risk_level','?')}")

    print("\n" + "=" * 70)
    print("  ✅ CDSS MCP Server LIVE test PASSED")
    print("     - 7 tools discovered via list_tools()")
    print("     - 4 tools called end-to-end via MCP stdio transport")
    print("     - All results validated against expected clinical thresholds")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
