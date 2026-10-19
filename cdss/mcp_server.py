"""
MediChain CDSS MCP Server -- Clinical Decision Support scoring tools.

Each tool implements a published clinical scoring algorithm.
Tools are deterministic (no LLM calls) and return JSON.

Run standalone:  python -m cdss.mcp_server
"""
import json
from mcp.server.fastmcp import FastMCP
from cdss.scoring import (
    calculate_wells_score, WellsInput,
    calculate_curb65, CURB65Input,
    calculate_cha2ds2_vasc, CHA2DS2VASCInput,
    calculate_heart_score, HEARTInput,
    calculate_qsofa, QSOFAInput,
    screen_phq9, PHQ9Input,
)
from cdss.drug_interactions import check_interactions

mcp = FastMCP(
    "MediChain CDSS Tools",
    instructions=(
        "Clinical Decision Support scoring tools for evidence-based risk assessment. "
        "All algorithms follow published clinical guidelines. Use these to quantify "
        "clinical risk and support diagnostic reasoning with evidence."
    ),
)


@mcp.tool()
async def cdss_wells_score(
    clinical_signs_dvt: bool, pe_most_likely: bool,
    heart_rate_over_100: bool, immobilization_or_surgery: bool,
    previous_dvt_pe: bool, hemoptysis: bool, malignancy: bool,
) -> str:
    """Calculate Wells Score for pulmonary embolism (PE) risk.

    Returns risk level (low/moderate/high) and clinical recommendation.
    Based on: Wells et al. 2000, Thrombosis and Haemostasis.
    """
    result = calculate_wells_score(WellsInput(
        clinical_signs_dvt=clinical_signs_dvt, pe_most_likely=pe_most_likely,
        heart_rate_over_100=heart_rate_over_100,
        immobilization_or_surgery=immobilization_or_surgery,
        previous_dvt_pe=previous_dvt_pe, hemoptysis=hemoptysis,
        malignancy=malignancy,
    ))
    return result.model_dump_json()


@mcp.tool()
async def cdss_curb65(
    confusion: bool, urea_over_7: bool,
    respiratory_rate_over_30: bool, low_blood_pressure: bool,
    age_over_65: bool,
) -> str:
    """Calculate CURB-65 score for community-acquired pneumonia severity.

    Returns severity (low/moderate/severe), mortality risk, and disposition recommendation.
    Based on: Lim et al. 2003, Thorax (BTS Guidelines).
    """
    result = calculate_curb65(CURB65Input(
        confusion=confusion, urea_over_7=urea_over_7,
        respiratory_rate_over_30=respiratory_rate_over_30,
        low_blood_pressure=low_blood_pressure, age_over_65=age_over_65,
    ))
    return result.model_dump_json()


@mcp.tool()
async def cdss_cha2ds2_vasc(
    congestive_heart_failure: bool, hypertension: bool,
    age: int, diabetes: bool, stroke_tia_history: bool,
    vascular_disease: bool, sex_female: bool,
) -> str:
    """Calculate CHA2DS2-VASc score for atrial fibrillation stroke risk.

    Returns annual stroke risk percentage and anticoagulation recommendation.
    Based on: Lip et al. 2010, Chest (ESC Guidelines).
    """
    result = calculate_cha2ds2_vasc(CHA2DS2VASCInput(
        congestive_heart_failure=congestive_heart_failure,
        hypertension=hypertension, age=age, diabetes=diabetes,
        stroke_tia_history=stroke_tia_history,
        vascular_disease=vascular_disease, sex_female=sex_female,
    ))
    return result.model_dump_json()


@mcp.tool()
async def cdss_heart_score(
    history: int, ecg: int, age: int,
    risk_factors: int, troponin: int,
) -> str:
    """Calculate HEART score for chest pain ACS (acute coronary syndrome) risk.

    Each parameter scored 0-2. Returns MACE risk and management recommendation.
    Based on: Six et al. 2008, Netherlands Heart Journal.
    """
    result = calculate_heart_score(HEARTInput(
        history=history, ecg=ecg, age=age,
        risk_factors=risk_factors, troponin=troponin,
    ))
    return result.model_dump_json()


@mcp.tool()
async def cdss_qsofa(
    respiratory_rate_over_22: bool,
    altered_mentation: bool,
    systolic_bp_under_100: bool,
) -> str:
    """Calculate qSOFA score for sepsis screening.

    Score >= 2 suggests possible sepsis -- triggers full SOFA assessment.
    Based on: Singer et al. 2016, JAMA (Sepsis-3 Definitions).
    """
    result = calculate_qsofa(QSOFAInput(
        respiratory_rate_over_22=respiratory_rate_over_22,
        altered_mentation=altered_mentation,
        systolic_bp_under_100=systolic_bp_under_100,
    ))
    return result.model_dump_json()


@mcp.tool()
async def cdss_phq9(scores: list[int]) -> str:
    """Screen for depression severity using PHQ-9 questionnaire.

    Provide 9 item scores (each 0-3). Returns total, severity, and recommendation.
    Based on: Kroenke et al. 2001, Journal of General Internal Medicine.
    """
    result = screen_phq9(PHQ9Input(scores=scores))
    return result.model_dump_json()


@mcp.tool()
async def cdss_drug_interactions(
    current_medications: list[str],
    proposed_medications: list[str] | None = None,
) -> str:
    """Check drug-drug interactions for patient's medications.

    Uses NLM RxNorm API with local fallback for common high-risk pairs.
    Returns severity classification and clinical recommendations.
    """
    result = await check_interactions(current_medications, proposed_medications or [])
    return result.model_dump_json()


if __name__ == "__main__":
    mcp.run()
