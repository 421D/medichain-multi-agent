import pytest
from cdss.scoring import (
    calculate_wells_score, WellsInput, WellsResult,
    calculate_curb65, CURB65Input,
    calculate_cha2ds2_vasc, CHA2DS2VASCInput,
    calculate_heart_score, HEARTInput,
    calculate_qsofa, QSOFAInput,
    screen_phq9, PHQ9Input,
)


class TestWellsScore:
    def test_low_risk_all_false(self):
        inp = WellsInput(
            clinical_signs_dvt=False, pe_most_likely=False,
            heart_rate_over_100=False, immobilization_or_surgery=False,
            previous_dvt_pe=False, hemoptysis=False, malignancy=False,
        )
        result = calculate_wells_score(inp)
        assert result.score == 0.0
        assert result.risk_level == "low"

    def test_high_risk(self):
        inp = WellsInput(
            clinical_signs_dvt=True, pe_most_likely=True,
            heart_rate_over_100=True, immobilization_or_surgery=False,
            previous_dvt_pe=True, hemoptysis=False, malignancy=False,
        )
        result = calculate_wells_score(inp)
        assert result.score == 9.0
        assert result.risk_level == "high"

    def test_moderate_risk(self):
        inp = WellsInput(
            clinical_signs_dvt=False, pe_most_likely=False,
            heart_rate_over_100=True, immobilization_or_surgery=True,
            previous_dvt_pe=False, hemoptysis=False, malignancy=True,
        )
        result = calculate_wells_score(inp)
        assert result.score == 4.0
        assert result.risk_level == "moderate"

    def test_result_has_recommendation(self):
        inp = WellsInput(
            clinical_signs_dvt=True, pe_most_likely=True,
            heart_rate_over_100=False, immobilization_or_surgery=False,
            previous_dvt_pe=False, hemoptysis=False, malignancy=False,
        )
        result = calculate_wells_score(inp)
        assert result.recommendation  # non-empty
        assert result.evidence_source  # non-empty


class TestCURB65:
    def test_score_zero(self):
        result = calculate_curb65(CURB65Input(
            confusion=False, urea_over_7=False,
            respiratory_rate_over_30=False, low_blood_pressure=False,
            age_over_65=False))
        assert result.score == 0
        assert result.severity == "low"

    def test_severe(self):
        result = calculate_curb65(CURB65Input(
            confusion=True, urea_over_7=True,
            respiratory_rate_over_30=True, low_blood_pressure=True,
            age_over_65=True))
        assert result.score == 5
        assert result.severity == "severe"


class TestCHA2DS2VASc:
    def test_young_healthy_male(self):
        result = calculate_cha2ds2_vasc(CHA2DS2VASCInput(
            congestive_heart_failure=False, hypertension=False,
            age=40, diabetes=False, stroke_tia_history=False,
            vascular_disease=False, sex_female=False))
        assert result.score == 0

    def test_elderly_with_stroke_history(self):
        result = calculate_cha2ds2_vasc(CHA2DS2VASCInput(
            congestive_heart_failure=True, hypertension=True,
            age=76, diabetes=True, stroke_tia_history=True,
            vascular_disease=False, sex_female=True))
        assert result.score == 8  # CHF(1)+HTN(1)+Age76(2)+DM(1)+Stroke(2)+Female(1)=8


class TestHEARTScore:
    def test_low_risk(self):
        result = calculate_heart_score(HEARTInput(
            history=0, ecg=0, age=0, risk_factors=0, troponin=0))
        assert result.score == 0
        assert result.risk_level == "low"

    def test_high_risk(self):
        result = calculate_heart_score(HEARTInput(
            history=2, ecg=2, age=2, risk_factors=2, troponin=2))
        assert result.score == 10
        assert result.risk_level == "high"


class TestQSOFA:
    def test_no_risk(self):
        result = calculate_qsofa(QSOFAInput(
            respiratory_rate_over_22=False, altered_mentation=False,
            systolic_bp_under_100=False))
        assert result.score == 0

    def test_high_risk(self):
        result = calculate_qsofa(QSOFAInput(
            respiratory_rate_over_22=True, altered_mentation=True,
            systolic_bp_under_100=True))
        assert result.score == 3
        assert "sepsis" in result.sepsis_risk.lower()


class TestPHQ9:
    def test_minimal(self):
        result = screen_phq9(PHQ9Input(scores=[0]*9))
        assert result.total_score == 0
        assert result.severity == "minimal"

    def test_severe(self):
        result = screen_phq9(PHQ9Input(scores=[3]*9))
        assert result.total_score == 27
        assert result.severity == "severe"

    def test_moderate(self):
        result = screen_phq9(PHQ9Input(scores=[1,2,1,2,1,1,1,1,1]))
        assert result.total_score == 11
        assert result.severity == "moderate"
