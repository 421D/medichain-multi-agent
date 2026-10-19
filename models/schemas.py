from pydantic import BaseModel, Field, field_validator
from typing import Optional
from enum import Enum


# --- Enums ---


class AgentName(str, Enum):
    INTERVIEWER = "interviewer"
    DIAGNOSTICIAN = "diagnostician"
    CRITIC = "critic"


class InterviewStatus(str, Enum):
    COMPLETE = "complete"
    NEED_MORE_INFO = "need_more_info"


class SafetyFlag(str, Enum):
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"


class RedirectTarget(str, Enum):
    INTERVIEWER = "interviewer"
    DIAGNOSTICIAN = "diagnostician"


# --- Interviewer schemas ---


class PatientSummary(BaseModel):
    chief_complaint: str = Field(description="Chief complaint")
    history_of_present_illness: str = Field(description="History of present illness")
    past_medical_history: str = Field(default="", description="Past medical history")
    medications: str = Field(default="", description="Current medications")
    allergies: str = Field(default="", description="Allergy history")
    family_history: str = Field(default="", description="Family history")
    review_of_systems: str = Field(default="", description="Review of systems")


class InterviewerOutput(BaseModel):
    status: InterviewStatus = Field(description="Current status: complete or need_more_info")
    question: Optional[str] = Field(default=None, description="Question to ask the patient")
    reasoning: Optional[str] = Field(default=None, description="Internal reasoning for current decision")
    summary: Optional[PatientSummary] = Field(
        default=None, description="Structured patient history summary when complete"
    )


# --- Diagnostician schemas ---


class DiagnosisEntry(BaseModel):
    diagnosis: str = Field(description="Diagnosis name")
    confidence: int = Field(ge=0, le=100, description="Confidence score 0-100")
    supporting_evidence: list[str] = Field(default_factory=list, description="List of supporting evidence")
    against_evidence: list[str] = Field(default_factory=list, description="List of contradicting evidence")
    source: str = Field(default="", description="Knowledge base source reference")


class DiagnosticianOutput(BaseModel):
    differential_diagnosis: list[DiagnosisEntry] = Field(description="Ranked list of differential diagnoses")
    recommended_tests: list[str] = Field(description="Recommended diagnostic tests")
    reasoning_chain: str = Field(description="Full reasoning chain")


# --- Critic schemas ---


class CriticIssue(BaseModel):
    type: str = Field(description="Issue type")
    description: str = Field(description="Issue description")
    suggestion: str = Field(description="Improvement suggestion")


class CriticOutput(BaseModel):
    approval: bool = Field(description="Whether the current diagnosis is approved")
    issues: list[CriticIssue] = Field(default_factory=list, description="List of identified issues")
    final_assessment: str = Field(description="Final assessment summary")
    safety_flag: SafetyFlag = Field(description="Safety flag: green/yellow/red")
    redirect_to: Optional[RedirectTarget] = Field(
        default=None, description="Agent to redirect to if issues found"
    )


# --- Debate schemas ---


class DebateChallenge(BaseModel):
    """A structured challenge from the Critic during debate."""
    challenge_id: str = Field(description="Challenge identifier, e.g. 'c1'")
    type: str = Field(description="Challenge type: missed_diagnosis, evidence_gap, scoring_error, safety_concern")
    claim: str = Field(description="The specific challenge claim")
    evidence: list[str] = Field(default_factory=list, description="Evidence supporting the challenge")
    suggested_action: str = Field(description="Suggested corrective action")
    tool_evidence: Optional[dict] = Field(default=None, description="CDSS tool output supporting this challenge")


class DebateResponse(BaseModel):
    """Diagnostician's response to a specific challenge."""
    challenge_id: str = Field(description="ID of the challenge being responded to")
    action: str = Field(description="Response action: accept, refute, or partially_accept")
    reasoning: str = Field(description="Reasoning for the response")
    evidence: list[str] = Field(default_factory=list, description="Evidence supporting the response")
    tool_evidence: Optional[dict] = Field(default=None, description="CDSS tool output supporting this response")
    updated_diagnosis: Optional[dict] = Field(default=None, description="Updated diagnosis entry if accepted")


class DebateRound(BaseModel):
    """One complete round of Critic-Diagnostician debate."""
    round_number: int = Field(description="Round number (1-indexed)")
    challenges: list[DebateChallenge] = Field(default_factory=list, description="Critic's challenges")
    responses: list[DebateResponse] = Field(default_factory=list, description="Diagnostician's responses")
    resolution: str = Field(description="Round resolution: resolved, escalated, or deadlock")


class DebateOutcome(BaseModel):
    """Final outcome of the debate process."""
    rounds: list[DebateRound] = Field(default_factory=list)
    total_challenges: int = Field(default=0)
    accepted: int = Field(default=0)
    refuted: int = Field(default=0)
    final_verdict: str = Field(description="approved, revised_and_approved, or unresolved")
    consensus_diagnosis: Optional[dict] = Field(default=None, description="Post-debate consensus diagnosis")


class CriticDebateOutput(BaseModel):
    """Structured output from Critic during debate."""
    challenges: list[DebateChallenge] = Field(default_factory=list, description="Structured challenges")
    safety_flag: SafetyFlag = Field(
        default=SafetyFlag.YELLOW,
        description="Safety flag: green | yellow | red",
    )
    overall_assessment: str = Field(description="Overall assessment of the diagnosis")

    @field_validator("safety_flag", mode="before")
    @classmethod
    def _coerce_safety_flag(cls, v):
        """Tolerate off-vocabulary LLM outputs (e.g. 'urgent', 'warn') by mapping
        them to the closest canonical flag, rather than raising a
        ValidationError that would crash the debate node at runtime."""
        if isinstance(v, SafetyFlag):
            return v
        if not isinstance(v, str):
            return SafetyFlag.YELLOW
        s = v.strip().lower()
        if s in ("green", "yellow", "red"):
            return s
        if s in ("urgent", "critical", "emergency", "danger", "severe"):
            return "red"
        if s in ("caution", "warn", "warning", "orange", "moderate"):
            return "yellow"
        if s in ("ok", "safe", "none", "clear", ""):
            return "green"
        return "yellow"  # unknown vocabulary → conservative default


class DiagnosticianDebateOutput(BaseModel):
    """Structured output from Diagnostician during debate."""
    responses: list[DebateResponse] = Field(default_factory=list, description="Responses to each challenge")
    updated_reasoning: str = Field(default="", description="Updated reasoning chain if diagnosis changed")


# --- CDSS Selector schemas (LLM picks which scores to compute + extracts params) ---


class CDSSToolSelection(BaseModel):
    """A single CDSS scoring tool the selector LLM wants to run."""
    tool: str = Field(
        description="Tool name. One of: wells_score, curb65, cha2ds2_vasc, heart_score, qsofa, phq9"
    )
    params: dict = Field(
        default_factory=dict,
        description="Parameters matching the tool's input schema (e.g. Wells expects 7 booleans)",
    )
    rationale: str = Field(
        default="",
        description="One-line clinical reason this score applies to this patient",
    )


class CDSSEvaluation(BaseModel):
    """Structured output from the CDSS selector node."""
    scores_to_run: list[CDSSToolSelection] = Field(
        default_factory=list,
        description="Empty list if no clinical score applies to the current DDx",
    )
    reasoning: str = Field(
        default="",
        description="Brief overall reasoning for the selection",
    )


# --- WebSocket message schema ---


class WSMessage(BaseModel):
    type: str = Field(description="Message type")
    agent: Optional[str] = Field(default=None, description="Agent sending the message")
    content: Optional[str] = Field(default=None, description="Message content")
    data: Optional[dict] = Field(default=None, description="Additional data payload")
