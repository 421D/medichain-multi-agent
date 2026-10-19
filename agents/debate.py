"""Debate round node: orchestrates structured Critic-Diagnostician debate."""
import json
import logging

from langchain_core.messages import HumanMessage, SystemMessage

from agents.base import get_structured_llm
from models.schemas import (
    CriticDebateOutput, DiagnosticianDebateOutput,
    DebateRound, DebateOutcome,
)
from prompts.critic_debate_prompt import CRITIC_DEBATE_SYSTEM_PROMPT
from prompts.diagnostician_debate_prompt import DIAGNOSTICIAN_DEBATE_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

import os

MAX_DEBATE_ROUNDS = int(os.getenv("MAX_DEBATE_ROUNDS", "2"))


def _build_critic_context(patient_history, diagnosis, debate_history, cdss_scores) -> list:
    """Build LLM messages for the Critic's debate turn."""
    history_str = json.dumps(patient_history, ensure_ascii=False, indent=2)
    diagnosis_str = json.dumps(diagnosis, ensure_ascii=False, indent=2)
    cdss_str = json.dumps(cdss_scores, ensure_ascii=False, indent=2) if cdss_scores else "No CDSS scores available"

    debate_str = ""
    if debate_history:
        debate_str = f"\n## Previous Debate Rounds\n{json.dumps(debate_history, ensure_ascii=False, indent=2)}"

    user_msg = (
        f"## Patient History\n{history_str}\n\n"
        f"## Current Diagnosis\n{diagnosis_str}\n\n"
        f"## CDSS Scores\n{cdss_str}\n"
        f"{debate_str}\n\n"
        f"Current debate round: {len(debate_history) + 1}/{MAX_DEBATE_ROUNDS}\n"
        f"Review the diagnosis and issue structured challenges if warranted."
    )
    return [SystemMessage(content=CRITIC_DEBATE_SYSTEM_PROMPT), HumanMessage(content=user_msg)]


def _build_diagnostician_context(patient_history, diagnosis, challenges, cdss_scores) -> list:
    """Build LLM messages for the Diagnostician's debate response."""
    history_str = json.dumps(patient_history, ensure_ascii=False, indent=2)
    diagnosis_str = json.dumps(diagnosis, ensure_ascii=False, indent=2)
    challenges_str = json.dumps([c.model_dump() for c in challenges], ensure_ascii=False, indent=2)
    cdss_str = json.dumps(cdss_scores, ensure_ascii=False, indent=2) if cdss_scores else "No CDSS scores"

    user_msg = (
        f"## Patient History\n{history_str}\n\n"
        f"## Your Current Diagnosis\n{diagnosis_str}\n\n"
        f"## CDSS Scores\n{cdss_str}\n\n"
        f"## Challenges from Critic\n{challenges_str}\n\n"
        f"Respond to each challenge with accept, refute, or partially_accept."
    )
    return [SystemMessage(content=DIAGNOSTICIAN_DEBATE_SYSTEM_PROMPT), HumanMessage(content=user_msg)]


def _apply_debate_updates(diagnosis: dict, responses) -> dict:
    """Apply accepted debate responses to update the diagnosis.

    After applying updates, the differential is re-sorted by confidence so
    that downstream consumers (`ddx[0]` as primary, evaluation harness, UI)
    see the highest-confidence diagnosis first, even if the debate added a
    new high-confidence entry like "Subarachnoid hemorrhage" that wasn't in
    the original list.
    """
    updated = dict(diagnosis)
    ddx = list(updated.get("differential_diagnosis", []))

    for resp in responses:
        if resp.action in ("accept", "partially_accept") and resp.updated_diagnosis:
            new_dx = resp.updated_diagnosis
            new_name = new_dx.get("diagnosis", "").lower()

            if new_name:
                replaced = False
                for idx, d in enumerate(ddx):
                    if d.get("diagnosis", "").lower() == new_name:
                        ddx[idx] = new_dx
                        replaced = True
                        break
                if not replaced:
                    ddx.append(new_dx)

    # Re-rank by confidence (descending). Missing/invalid confidence sorts last.
    def _conf(d: dict) -> int:
        try:
            return int(d.get("confidence", 0) or 0)
        except (TypeError, ValueError):
            return 0
    ddx.sort(key=_conf, reverse=True)

    updated["differential_diagnosis"] = ddx
    return updated


def debate_round_node(state: dict) -> dict:
    """Execute one round of Critic-Diagnostician structured debate."""
    diagnosis = state.get("diagnosis", {})
    patient_history = state.get("patient_history", {})
    debate_history = state.get("debate_rounds") or []
    cdss_scores = state.get("cdss_scores") or {}
    round_num = len(debate_history) + 1
    agent_logs = []

    # Step 1: Critic generates structured challenges
    critic_llm = get_structured_llm(
        CriticDebateOutput,
        model_override=state.get("llm_model"),
        node=f"critic_r{round_num}",
        session_id=state.get("session_id"),
    )
    critic_messages = _build_critic_context(patient_history, diagnosis, debate_history, cdss_scores)
    critic_result: CriticDebateOutput = critic_llm.invoke(critic_messages)

    agent_logs.append({
        "agent": "critic", "action": "debate_challenge",
        "round": round_num,
        "challenges_count": len(critic_result.challenges),
        "safety_flag": critic_result.safety_flag,
        "assessment": critic_result.overall_assessment[:200],
    })

    if not critic_result.challenges:
        # No challenges -> approved, go to coordinator
        resolved_round = DebateRound(
            round_number=round_num, challenges=[], responses=[],
            resolution="resolved",
        )
        outcome = DebateOutcome(
            rounds=debate_history + [resolved_round.model_dump()],
            total_challenges=0, accepted=0, refuted=0,
            final_verdict="approved",
            consensus_diagnosis=diagnosis,
        )
        return {
            "debate_rounds": debate_history + [resolved_round.model_dump()],
            "debate_outcome": outcome.model_dump(),
            "critic_review": {
                "approval": True,
                "safety_flag": critic_result.safety_flag,
                "issues": [],
                "final_assessment": critic_result.overall_assessment,
            },
            "current_agent": "complete",
            "agent_logs": agent_logs,
        }

    # Step 2: Diagnostician responds to challenges
    diag_llm = get_structured_llm(
        DiagnosticianDebateOutput,
        model_override=state.get("llm_model"),
        node=f"diag_debate_r{round_num}",
        session_id=state.get("session_id"),
    )
    diag_messages = _build_diagnostician_context(
        patient_history, diagnosis, critic_result.challenges, cdss_scores,
    )
    diag_result: DiagnosticianDebateOutput = diag_llm.invoke(diag_messages)

    # Step 3: Resolve round (per-round counts for the agent_log entry)
    round_accepted = sum(1 for r in diag_result.responses if r.action in ("accept", "partially_accept"))
    round_refuted = sum(1 for r in diag_result.responses if r.action == "refute")

    # A round is resolved iff every challenge has a terminal response.
    # Terminal actions: accept, refute, partially_accept. Missing responses (count
    # mismatch) or unknown actions force another round up to MAX_DEBATE_ROUNDS.
    challenge_ids = {c.challenge_id for c in critic_result.challenges}
    responded_ids = {r.challenge_id for r in diag_result.responses
                     if r.action in ("accept", "refute", "partially_accept")}
    all_resolved = challenge_ids.issubset(responded_ids) and len(challenge_ids) > 0

    updated_diagnosis = _apply_debate_updates(diagnosis, diag_result.responses)

    this_round = DebateRound(
        round_number=round_num,
        challenges=[c.model_dump() for c in critic_result.challenges],
        responses=[r.model_dump() for r in diag_result.responses],
        resolution="resolved" if all_resolved else "escalated",
    )

    agent_logs.append({
        "agent": "diagnostician", "action": "debate_response",
        "round": round_num, "accepted": round_accepted, "refuted": round_refuted,
    })

    new_history = debate_history + [this_round.model_dump()]

    if all_resolved or round_num >= MAX_DEBATE_ROUNDS:
        # Aggregate accepted/refuted across ALL rounds, not just the last,
        # so DebateOutcome reports cumulative counts that match the harness's
        # `challenges_accepted / challenge_acceptance_rate` semantics.
        total_accepted = 0
        total_refuted = 0
        for past_round in new_history:
            for r in past_round.get("responses", []) or []:
                action = r.get("action") if isinstance(r, dict) else None
                if action in ("accept", "partially_accept"):
                    total_accepted += 1
                elif action == "refute":
                    total_refuted += 1
        verdict = "revised_and_approved" if total_accepted > 0 else "approved"
        outcome = DebateOutcome(
            rounds=new_history,
            total_challenges=sum(len(r.get("challenges", [])) for r in new_history),
            accepted=total_accepted, refuted=total_refuted,
            final_verdict=verdict,
            consensus_diagnosis=updated_diagnosis,
        )
        return {
            "diagnosis": updated_diagnosis,
            "debate_rounds": new_history,
            "debate_outcome": outcome.model_dump(),
            "critic_review": {
                "approval": True,
                "safety_flag": critic_result.safety_flag,
                "issues": [{"type": c.type, "description": c.claim, "suggestion": c.suggested_action}
                           for c in critic_result.challenges],
                "final_assessment": critic_result.overall_assessment,
            },
            "current_agent": "complete",
            "agent_logs": agent_logs,
        }
    else:
        return {
            "diagnosis": updated_diagnosis,
            "debate_rounds": new_history,
            "current_agent": "debate",
            "agent_logs": agent_logs,
        }
