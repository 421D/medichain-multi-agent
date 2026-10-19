"""Test CDSS MCP tools as plain function calls (no MCP transport)."""
import json
import pytest
from cdss.mcp_server import (
    cdss_wells_score, cdss_curb65, cdss_heart_score,
    cdss_qsofa, cdss_phq9, cdss_cha2ds2_vasc,
)


@pytest.mark.asyncio(loop_scope="function")
async def test_wells_mcp_returns_json():
    result = await cdss_wells_score(
        clinical_signs_dvt=True, pe_most_likely=False,
        heart_rate_over_100=True, immobilization_or_surgery=False,
        previous_dvt_pe=False, hemoptysis=False, malignancy=False,
    )
    data = json.loads(result)
    assert "score" in data
    assert "risk_level" in data
    assert "recommendation" in data


@pytest.mark.asyncio(loop_scope="function")
async def test_qsofa_mcp():
    result = await cdss_qsofa(
        respiratory_rate_over_22=True,
        altered_mentation=True,
        systolic_bp_under_100=False,
    )
    data = json.loads(result)
    assert data["score"] == 2
    assert "sepsis" in data["sepsis_risk"].lower()


@pytest.mark.asyncio(loop_scope="function")
async def test_phq9_mcp():
    result = await cdss_phq9(scores=[2, 2, 2, 1, 1, 1, 1, 1, 1])
    data = json.loads(result)
    assert data["total_score"] == 12
    assert data["severity"] == "moderate"
