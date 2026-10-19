"""Bridge CDSS scoring functions into LangChain tools for agent use."""
from langchain_core.tools import tool
from cdss.scoring import (
    calculate_wells_score, WellsInput,
    calculate_curb65, CURB65Input,
    calculate_cha2ds2_vasc, CHA2DS2VASCInput,
    calculate_heart_score, HEARTInput,
    calculate_qsofa, QSOFAInput,
    screen_phq9, PHQ9Input,
)


@tool
def wells_score(
    clinical_signs_dvt: bool, pe_most_likely: bool,
    heart_rate_over_100: bool, immobilization_or_surgery: bool,
    previous_dvt_pe: bool, hemoptysis: bool, malignancy: bool,
) -> str:
    """Calculate Wells Score for PE risk. Returns score, risk level, and recommendation."""
    result = calculate_wells_score(WellsInput(
        clinical_signs_dvt=clinical_signs_dvt, pe_most_likely=pe_most_likely,
        heart_rate_over_100=heart_rate_over_100,
        immobilization_or_surgery=immobilization_or_surgery,
        previous_dvt_pe=previous_dvt_pe, hemoptysis=hemoptysis,
        malignancy=malignancy))
    return result.model_dump_json()


@tool
def curb65(
    confusion: bool, urea_over_7: bool,
    respiratory_rate_over_30: bool, low_blood_pressure: bool,
    age_over_65: bool,
) -> str:
    """Calculate CURB-65 for pneumonia severity. Returns score, severity, and disposition."""
    result = calculate_curb65(CURB65Input(
        confusion=confusion, urea_over_7=urea_over_7,
        respiratory_rate_over_30=respiratory_rate_over_30,
        low_blood_pressure=low_blood_pressure, age_over_65=age_over_65))
    return result.model_dump_json()


@tool
def cha2ds2_vasc(
    congestive_heart_failure: bool, hypertension: bool,
    age: int, diabetes: bool, stroke_tia_history: bool,
    vascular_disease: bool, sex_female: bool,
) -> str:
    """Calculate CHA2DS2-VASc for AF stroke risk. Returns score and anticoagulation recommendation."""
    result = calculate_cha2ds2_vasc(CHA2DS2VASCInput(
        congestive_heart_failure=congestive_heart_failure,
        hypertension=hypertension, age=age, diabetes=diabetes,
        stroke_tia_history=stroke_tia_history,
        vascular_disease=vascular_disease, sex_female=sex_female))
    return result.model_dump_json()


@tool
def heart_score(
    history: int, ecg: int, age: int,
    risk_factors: int, troponin: int,
) -> str:
    """Calculate HEART score for chest pain ACS risk. Each param 0-2. Returns risk and recommendation."""
    result = calculate_heart_score(HEARTInput(
        history=history, ecg=ecg, age=age,
        risk_factors=risk_factors, troponin=troponin))
    return result.model_dump_json()


@tool
def qsofa(
    respiratory_rate_over_22: bool,
    altered_mentation: bool,
    systolic_bp_under_100: bool,
) -> str:
    """Calculate qSOFA for sepsis screening. Score >= 2 suggests possible sepsis."""
    result = calculate_qsofa(QSOFAInput(
        respiratory_rate_over_22=respiratory_rate_over_22,
        altered_mentation=altered_mentation,
        systolic_bp_under_100=systolic_bp_under_100))
    return result.model_dump_json()


@tool
def phq9(scores: list[int]) -> str:
    """Screen depression with PHQ-9. Provide 9 scores (0-3 each). Returns severity."""
    result = screen_phq9(PHQ9Input(scores=scores))
    return result.model_dump_json()


def get_cdss_tools() -> list:
    """Return all CDSS tools for binding to an LLM agent."""
    return [wells_score, curb65, cha2ds2_vasc, heart_score, qsofa, phq9]
