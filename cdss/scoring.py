from pydantic import BaseModel, Field


# ── Wells Score (PE) ──

class WellsInput(BaseModel):
    clinical_signs_dvt: bool = Field(description="Clinical signs/symptoms of DVT")
    pe_most_likely: bool = Field(description="PE is most likely diagnosis")
    heart_rate_over_100: bool = Field(description="Heart rate > 100 bpm")
    immobilization_or_surgery: bool = Field(description="Immobilization or surgery in past 4 weeks")
    previous_dvt_pe: bool = Field(description="Previous DVT or PE")
    hemoptysis: bool = Field(description="Hemoptysis present")
    malignancy: bool = Field(description="Active malignancy")


class WellsResult(BaseModel):
    score: float
    risk_level: str  # "low" | "moderate" | "high"
    probability: str
    recommendation: str
    evidence_source: str = "Wells et al. 2000, Thrombosis and Haemostasis"


def calculate_wells_score(inp: WellsInput) -> WellsResult:
    score = 0.0
    if inp.clinical_signs_dvt: score += 3.0
    if inp.pe_most_likely: score += 3.0
    if inp.heart_rate_over_100: score += 1.5
    if inp.immobilization_or_surgery: score += 1.5
    if inp.previous_dvt_pe: score += 1.5
    if inp.hemoptysis: score += 1.0
    if inp.malignancy: score += 1.0

    # Wells 3-tier cutoffs (Wells et al. 2000): <2 low, 2-6 moderate, >6 high.
    # Using <=1 rather than <2 would misclassify score=1.5 as moderate.
    if score < 2:
        risk_level, probability = "low", "PE unlikely"
        recommendation = "Consider D-dimer testing. If negative, PE can be excluded."
    elif score <= 6:
        risk_level, probability = "moderate", "PE possible"
        recommendation = "D-dimer testing recommended. If positive, proceed to CTPA."
    else:
        risk_level, probability = "high", "PE likely"
        recommendation = "Proceed directly to CTPA. Do not delay for D-dimer."

    return WellsResult(score=score, risk_level=risk_level,
                       probability=probability, recommendation=recommendation)


# ── CURB-65 (Pneumonia) ──

class CURB65Input(BaseModel):
    confusion: bool = Field(description="New-onset confusion")
    urea_over_7: bool = Field(description="Blood urea nitrogen > 7 mmol/L")
    respiratory_rate_over_30: bool = Field(description="Respiratory rate >= 30/min")
    low_blood_pressure: bool = Field(description="Systolic BP < 90 or Diastolic BP <= 60 mmHg")
    age_over_65: bool = Field(description="Age >= 65 years")


class CURB65Result(BaseModel):
    score: int
    severity: str  # "low" | "moderate" | "severe"
    mortality_risk: str
    recommendation: str
    evidence_source: str = "Lim et al. 2003, Thorax (BTS Guidelines)"


def calculate_curb65(inp: CURB65Input) -> CURB65Result:
    score = sum([inp.confusion, inp.urea_over_7, inp.respiratory_rate_over_30,
                 inp.low_blood_pressure, inp.age_over_65])

    if score <= 1:
        severity, mortality = "low", "<3% 30-day mortality"
        recommendation = "Consider outpatient treatment. Oral antibiotics appropriate."
    elif score == 2:
        severity, mortality = "moderate", "3-15% 30-day mortality"
        recommendation = "Consider short hospital admission or closely supervised outpatient care."
    else:
        severity, mortality = "severe", ">15% 30-day mortality"
        recommendation = "Urgent hospital admission. Consider ICU if score 4-5."

    return CURB65Result(score=score, severity=severity,
                        mortality_risk=mortality, recommendation=recommendation)


# ── CHA2DS2-VASc (AF Stroke Risk) ──

class CHA2DS2VASCInput(BaseModel):
    congestive_heart_failure: bool = Field(description="CHF or LVEF <= 40%")
    hypertension: bool = Field(description="Hypertension history")
    age: int = Field(description="Patient age in years")
    diabetes: bool = Field(description="Diabetes mellitus")
    stroke_tia_history: bool = Field(description="Prior stroke, TIA, or thromboembolism")
    vascular_disease: bool = Field(description="Prior MI, PAD, or aortic plaque")
    sex_female: bool = Field(description="Female sex")


class CHA2DS2VASCResult(BaseModel):
    score: int
    annual_stroke_risk: str
    recommendation: str
    evidence_source: str = "Lip et al. 2010, Chest (ESC Guidelines)"


def calculate_cha2ds2_vasc(inp: CHA2DS2VASCInput) -> CHA2DS2VASCResult:
    score = 0
    if inp.congestive_heart_failure: score += 1
    if inp.hypertension: score += 1
    if inp.age >= 75: score += 2
    elif inp.age >= 65: score += 1
    if inp.diabetes: score += 1
    if inp.stroke_tia_history: score += 2
    if inp.vascular_disease: score += 1
    if inp.sex_female: score += 1

    risk_map = {0: "0%", 1: "1.3%", 2: "2.2%", 3: "3.2%", 4: "4.0%",
                5: "6.7%", 6: "9.8%", 7: "9.6%", 8: "12.5%", 9: "15.2%"}
    annual_risk = risk_map.get(score, ">15%")

    # ESC 2020 / AHA 2019: female sex alone (no other risk factors) is a
    # risk modifier, not an indication for OAC. Don't recommend OAC for the
    # lone-female score=1 case.
    lone_female = (score == 1 and inp.sex_female and not (
        inp.congestive_heart_failure or inp.hypertension or inp.diabetes
        or inp.stroke_tia_history or inp.vascular_disease or inp.age >= 65
    ))
    if score == 0 or lone_female:
        recommendation = "No antithrombotic therapy recommended."
    elif score == 1:
        recommendation = "Consider oral anticoagulation (OAC) based on individual risk-benefit."
    else:
        recommendation = "Oral anticoagulation recommended (DOAC preferred over warfarin)."

    return CHA2DS2VASCResult(score=score, annual_stroke_risk=annual_risk,
                              recommendation=recommendation)


# ── HEART Score (Chest Pain ACS) ──

class HEARTInput(BaseModel):
    history: int = Field(ge=0, le=2, description="0=slightly suspicious, 1=moderately, 2=highly suspicious")
    ecg: int = Field(ge=0, le=2, description="0=normal, 1=non-specific changes, 2=significant ST deviation")
    age: int = Field(ge=0, le=2, description="0=<45, 1=45-64, 2=>=65")
    risk_factors: int = Field(ge=0, le=2, description="0=no known, 1=1-2 factors, 2=>=3 or atherosclerosis hx")
    troponin: int = Field(ge=0, le=2, description="0=normal, 1=1-3x normal, 2=>3x normal")


class HEARTResult(BaseModel):
    score: int
    risk_level: str  # "low" | "moderate" | "high"
    mace_risk: str
    recommendation: str
    evidence_source: str = "Six et al. 2008, Netherlands Heart Journal"


def calculate_heart_score(inp: HEARTInput) -> HEARTResult:
    score = inp.history + inp.ecg + inp.age + inp.risk_factors + inp.troponin

    if score <= 3:
        risk_level, mace = "low", "1.7% 6-week MACE risk"
        recommendation = "Consider early discharge with outpatient follow-up."
    elif score <= 6:
        risk_level, mace = "moderate", "12-16.6% 6-week MACE risk"
        recommendation = "Admit for observation. Serial troponins and further workup."
    else:
        risk_level, mace = "high", ">50% 6-week MACE risk"
        recommendation = "Urgent cardiology consultation. Consider early invasive strategy."

    return HEARTResult(score=score, risk_level=risk_level,
                       mace_risk=mace, recommendation=recommendation)


# ── qSOFA (Sepsis Screening) ──

class QSOFAInput(BaseModel):
    respiratory_rate_over_22: bool = Field(description="Respiratory rate >= 22/min")
    altered_mentation: bool = Field(description="Altered mental status (GCS < 15)")
    systolic_bp_under_100: bool = Field(description="Systolic BP <= 100 mmHg")


class QSOFAResult(BaseModel):
    score: int
    sepsis_risk: str
    recommendation: str
    evidence_source: str = "Singer et al. 2016, JAMA (Sepsis-3)"


def calculate_qsofa(inp: QSOFAInput) -> QSOFAResult:
    score = sum([inp.respiratory_rate_over_22, inp.altered_mentation,
                 inp.systolic_bp_under_100])

    if score < 2:
        risk, rec = "Low risk", "Continue monitoring. qSOFA < 2 does not exclude sepsis."
    else:
        risk = "High risk — possible sepsis"
        rec = ("qSOFA >= 2: assess for organ dysfunction (full SOFA score). "
               "Consider blood cultures, lactate, and empiric antibiotics.")

    return QSOFAResult(score=score, sepsis_risk=risk, recommendation=rec)


# ── PHQ-9 (Depression Screening) ──

class PHQ9Input(BaseModel):
    scores: list[int] = Field(min_length=9, max_length=9,
                              description="9 PHQ-9 item scores, each 0-3")


class PHQ9Result(BaseModel):
    total_score: int
    severity: str
    recommendation: str
    evidence_source: str = "Kroenke et al. 2001, Journal of General Internal Medicine"


def screen_phq9(inp: PHQ9Input) -> PHQ9Result:
    total = sum(inp.scores)

    if total <= 4:
        sev, rec = "minimal", "No treatment indicated. Monitor if clinically appropriate."
    elif total <= 9:
        sev, rec = "mild", "Watchful waiting. Repeat PHQ-9 at follow-up."
    elif total <= 14:
        sev, rec = "moderate", "Consider counselling or pharmacotherapy."
    elif total <= 19:
        sev, rec = "moderately severe", "Active treatment: pharmacotherapy and/or psychotherapy."
    else:
        sev, rec = "severe", "Immediate pharmacotherapy and psychotherapy. Assess for safety."

    return PHQ9Result(total_score=total, severity=sev, recommendation=rec)
