"""
MediChain Orchestration Demo (V2 — Debate Protocol)
Demonstrates the 4-agent pipeline using mock agents.
No LLM API or RAG required — pure orchestration logic.

V2 changes vs V1:
  - Critic loopback node replaced with structured debate_round node
  - Diagnostician responds to Critic's challenges with accept/refute/partially_accept
  - CDSS scoring tools available via MCP (6 clinical risk calculators)

Usage: python demo_orchestration.py
"""

import time

# ANSI colors
GREEN = "\033[32m"
BLUE = "\033[34m"
RED = "\033[31m"
MAGENTA = "\033[35m"
PURPLE = "\033[95m"
GREY = "\033[90m"
BOLD = "\033[1m"
RESET = "\033[0m"

DIVIDER = GREY + "-" * 60 + RESET


def print_step(color, agent, message, delay=0.3):
    time.sleep(delay)
    print(f"  {color}[{agent}]{RESET} {message}")


def demo():
    print(f"\n{BOLD}{'=' * 60}")
    print("  MediChain V2: Debate-Driven Multi-Agent Diagnostics")
    print(f"{'=' * 60}{RESET}\n")
    print(f"  Flow: Interviewer -> Diagnostician -> Debate Round -> Coordinator")
    print(f"  Debate Round: Critic <-> Diagnostician, max 2 rounds, structured protocol.\n")

    # --- Simulated state ---
    state = {
        "messages": [],
        "patient_history": None,
        "diagnosis": None,
        "critic_review": None,
        "coordinator_response": None,
        "rag_context": None,
        "iteration_count": 0,
        "current_agent": "interviewer",
        "agent_logs": [],
    }

    # ==================== INTERVIEWER ====================
    print(DIVIDER)
    print(f"\n{BOLD}Stage 1: Interviewer Agent (History-Taking){RESET}\n")

    questions = [
        ("What are your main symptoms and how long have they lasted?",
         "I've had a severe headache for three days, mainly on the right side."),
        ("Is the pain throbbing, stabbing, or a pressure sensation? Any nausea or light sensitivity?",
         "It's throbbing, worse in the morning. I feel nauseous and bright light bothers me."),
        ("Any history of migraines? Are you currently taking any medications?",
         "No migraine history. I take ibuprofen occasionally but it doesn't help much."),
        ("Any family history of migraines or neurological conditions? Any recent head injury?",
         "My mother gets migraines. No recent injuries."),
    ]

    for i, (question, answer) in enumerate(questions, 1):
        print_step(GREEN, "Interviewer", f"Q{i}: {question}")
        print_step(GREY, "Patient", f"A{i}: {answer}", delay=0.2)

        state["messages"].append({"role": "ai", "content": question})
        state["messages"].append({"role": "human", "content": answer})
        state["agent_logs"].append({
            "agent": "interviewer", "action": "asking_question", "turn": i
        })

    # Interviewer completes
    state["patient_history"] = {
        "chief_complaint": "Severe right-sided headache for 3 days",
        "history_of_present_illness": "Throbbing pain, worse in morning, with nausea and photophobia",
        "past_medical_history": "None significant",
        "medications": "Occasional ibuprofen (ineffective)",
        "allergies": "Denied",
        "family_history": "Mother has migraines",
        "review_of_systems": "Nausea, photophobia; no fever, no vision changes",
    }
    state["current_agent"] = "diagnostician"
    state["agent_logs"].append({
        "agent": "interviewer", "action": "history_complete",
        "fields_collected": 7,
    })

    print()
    print_step(GREEN, "Interviewer", f"{BOLD}History collection COMPLETE -> handoff to Diagnostician{RESET}")
    print(f"\n  {GREY}State passed: patient_history (7 fields){RESET}")

    # ==================== DIAGNOSTICIAN ====================
    print(f"\n{DIVIDER}")
    print(f"\n{BOLD}Stage 2: Diagnostician Agent (Differential Diagnosis){RESET}\n")

    print_step(BLUE, "Diagnostician", "Analysing patient history...")
    print_step(BLUE, "Diagnostician", "Retrieving medical knowledge (RAG: 5 results)...")
    print_step(BLUE, "Diagnostician", "Generating differential diagnosis with CoT reasoning...\n")

    diagnoses = [
        ("Migraine without aura", 78, "Throbbing, unilateral, nausea, photophobia, family history"),
        ("Tension-type headache", 45, "Prolonged duration, stress possible; but throbbing argues against"),
        ("Cluster headache", 20, "Unilateral; but no autonomic symptoms, no circadian pattern"),
    ]

    for dx, conf, reasoning in diagnoses:
        bar = "█" * (conf // 5) + "░" * (20 - conf // 5)
        print(f"    {BLUE}{dx}{RESET}")
        print(f"    Confidence: [{bar}] {conf}%")
        print(f"    Reasoning:  {reasoning}\n")

    state["diagnosis"] = {
        "differential_diagnosis": [
            {"diagnosis": d, "confidence": c, "supporting_evidence": [r], "against_evidence": [], "source": "medical_kb"}
            for d, c, r in diagnoses
        ],
        "recommended_tests": ["Neurological examination", "Blood pressure check", "Consider brain MRI if persistent"],
        "reasoning_chain": "Unilateral throbbing + nausea + photophobia + family history strongly suggests migraine.",
    }
    state["current_agent"] = "debate_round"
    state["agent_logs"].append({
        "agent": "diagnostician", "action": "diagnosis_complete",
        "diagnoses_count": 3,
    })

    print_step(BLUE, "Diagnostician", f"Recommended tests: Neuro exam, BP check, consider MRI")
    print_step(BLUE, "Diagnostician", f"{BOLD}Diagnosis COMPLETE -> handoff to Debate Round{RESET}")
    print(f"\n  {GREY}State passed: diagnosis (3 differentials), rag_context{RESET}")

    # ==================== DEBATE ROUND 1 ====================
    print(f"\n{DIVIDER}")
    print(f"\n{BOLD}Stage 3: Debate Round (V2 — Critic <-> Diagnostician){RESET}\n")
    print(f"  {GREY}Debate protocol: Critic issues structured challenges, Diagnostician")
    print(f"  responds with accept / refute / partially_accept. Max 2 rounds.{RESET}\n")

    # ---- Round 1 ----
    print(f"{BOLD}  Round 1 / 2{RESET}\n")

    print_step(PURPLE, "Critic", "Issuing structured challenges against current diagnosis...\n")
    round1_challenges = [
        ("evidence_gap", "Medication dosage and frequency not documented",
         "Ibuprofen 'occasional' is vague; need daily dose for medication overuse headache assessment"),
        ("safety_concern", "Red-flag SAH not explicitly excluded",
         "Sudden onset headache (thunderclap) is a distinguishing feature not yet asked about"),
    ]
    for i, (ctype, claim, evidence) in enumerate(round1_challenges, 1):
        print(f"    {PURPLE}Challenge #{i}{RESET} [{ctype}]: {claim}")
        print(f"      Evidence: {evidence}\n")

    print_step(BLUE, "Diagnostician", "Responding to each challenge...\n")
    round1_responses = [
        ("partially_accept", "Dose info was incomplete — I'll infer '1-2x/day' from 'occasional' but flag uncertainty"),
        ("accept", "Correct — I should have explicitly noted gradual (non-thunderclap) onset. Updating."),
    ]
    for i, (action, reasoning) in enumerate(round1_responses, 1):
        color = GREEN if action == "accept" else (MAGENTA if action == "partially_accept" else RED)
        print(f"    {BLUE}Response #{i}{RESET}: {color}{action}{RESET} — {reasoning}\n")

    state["debate_rounds"] = [
        {
            "round_number": 1,
            "challenges": [
                {"type": t, "claim": c, "evidence": [e]} for t, c, e in round1_challenges
            ],
            "responses": [
                {"action": a, "reasoning": r} for a, r in round1_responses
            ],
            "resolution": "escalated",  # not all accept, so go to round 2
        }
    ]
    state["agent_logs"].append({
        "agent": "debate_round", "action": "round_complete",
        "round": 1, "accepted": 1, "partially": 1, "refuted": 0,
    })

    # Apply accepted updates
    state["patient_history"]["medications"] = "Ibuprofen 400mg, 1-2x daily (inferred, ineffective)"
    state["patient_history"]["history_of_present_illness"] += ". Gradual onset (non-thunderclap) confirmed."
    state["diagnosis"]["differential_diagnosis"][0]["confidence"] = 85

    print(f"  {GREY}Round 1 result: 1 accepted + 1 partially → diagnosis revised, next round{RESET}\n")

    # ---- Round 2 ----
    print(f"{BOLD}  Round 2 / 2{RESET}\n")

    print_step(PURPLE, "Critic", "Re-examining revised diagnosis...\n")
    print(f"    {PURPLE}No remaining challenges{RESET} — revised diagnosis is internally consistent.")
    print(f"    {PURPLE}Safety flag{RESET}: {BOLD}GREEN{RESET} (gradual onset documented, no red flags)\n")

    state["debate_rounds"].append({
        "round_number": 2,
        "challenges": [],
        "responses": [],
        "resolution": "resolved",
    })
    state["debate_outcome"] = {
        "rounds": state["debate_rounds"],
        "total_challenges": 2,
        "accepted": 1,
        "refuted": 0,
        "final_verdict": "revised_and_approved",
    }
    state["critic_review"] = {
        "approval": True,
        "safety_flag": "green",
        "issues": [
            {"type": "evidence_gap", "description": "Medication dosage", "suggestion": "Inferred"},
        ],
        "final_assessment": "Debate consensus reached in 2 rounds. Migraine diagnosis well-supported, no urgent concerns.",
    }
    state["current_agent"] = "complete"
    state["iteration_count"] = 2
    state["agent_logs"].append({
        "agent": "debate_round", "action": "debate_complete",
        "total_rounds": 2, "verdict": "revised_and_approved",
    })

    print_step(PURPLE, "Critic", f"Final verdict: {GREEN}{BOLD}REVISED_AND_APPROVED{RESET}")
    print_step(PURPLE, "Debate", f"{BOLD}Debate COMPLETE (2 rounds) -> handoff to Coordinator{RESET}")

    print(f"\n  {GREY}Routing: debate_round (complete) -> Coordinator (rounds 2/2){RESET}")

    # ==================== COORDINATOR ====================
    print(f"\n{DIVIDER}")
    print(f"\n{BOLD}Stage 4: Coordinator Agent (Patient-Facing Response){RESET}\n")

    print_step(MAGENTA, "Coordinator", "Synthesising outputs from all agents...\n")

    response = """    Thank you for sharing your symptoms with me. I understand that dealing
    with a persistent headache for three days can be very distressing, and
    I want to help you understand what might be going on.

    Based on our assessment, the pattern of your symptoms -- a throbbing
    one-sided headache with nausea and sensitivity to light, especially
    given your mother's history of migraines -- is most consistent with a
    migraine. This is a common and treatable condition.

    To confirm this and rule out other causes, I would recommend:
    1. A neurological examination
    2. A blood pressure check
    3. If the headaches persist or worsen, a brain MRI for reassurance

    Please visit your GP at your earliest convenience. In the meantime,
    if you experience a sudden severe "thunderclap" headache, vision
    changes, or weakness, please seek emergency care immediately.

    Take care, and don't hesitate to reach out if you have any concerns."""

    print(f"{MAGENTA}{response}{RESET}")

    state["coordinator_response"] = response
    state["agent_logs"].append({
        "agent": "coordinator", "action": "response_generated",
    })

    # ==================== SUMMARY ====================
    print(f"\n{DIVIDER}")
    print(f"\n{BOLD}Orchestration Summary (V2){RESET}\n")
    outcome = state.get("debate_outcome", {})
    print(f"  Agents involved:     Interviewer, Diagnostician, Debate Round, Coordinator")
    print(f"  Debate rounds used:  {outcome.get('rounds', [{}])[-1].get('round_number', 0) if outcome else 0} / 2")
    print(f"  Total challenges:    {outcome.get('total_challenges', 0)}")
    print(f"  Challenges accepted: {outcome.get('accepted', 0)}")
    print(f"  Challenges refuted:  {outcome.get('refuted', 0)}")
    print(f"  Final verdict:       {outcome.get('final_verdict', 'n/a')}")
    print(f"  Final safety flag:   GREEN")
    print(f"  Agent log entries:   {len(state['agent_logs'])}")
    print()

    print(f"  {BOLD}State Flow:{RESET}")
    print(f"  START -> Interviewer (4 turns, patient history complete)")
    print(f"       -> Diagnostician (3 differentials, RAG-enhanced)")
    print(f"       -> Debate Round 1 ({PURPLE}2 challenges{RESET} -> {BLUE}1 accept + 1 partially{RESET})")
    print(f"       -> Debate Round 2 ({PURPLE}no new challenges{RESET} -> {GREEN}consensus{RESET})")
    print(f"       -> Coordinator (final patient-facing response)")
    print(f"       -> END")
    print(f"\n{'=' * 60}\n")


if __name__ == "__main__":
    demo()
