# Prompt Design

Author: Danni Cai (Prompt & LLM Engineer)

MediChain makes six kinds of LLM call. Each has its own system prompt in [`prompts/`](../prompts/),
and every call except the Coordinator returns a Pydantic schema from
[`models/schemas.py`](../models/schemas.py) via structured output. The prompts therefore do two jobs:
they shape clinical behaviour, and they tell the model what each schema field must contain.

This document records what each prompt is for and why it is written the way it is.

## Principles used across all prompts

1. **One job per prompt.** Each agent does one step, so each prompt stays short and can be changed without
   breaking the others. Early in the project the prompts were f-strings inside the agent files; moving
   them into `prompts/` let them be edited and reviewed on their own.
2. **Rules, not personas.** A line like "you are an expert" does little. Concrete, checkable rules
   ("at least 3 differentials", "2+ supporting evidence items") change the output.
3. **Say when to do nothing.** The most useful rules tell the model when to stop: stop asking questions,
   raise no challenge, run no score. Without them, models keep producing output because they were asked to.
4. **Safety overrides everything else.** Emergency handling appears in the Interviewer, Critic and
   Coordinator prompts, and in each one it takes priority over the normal flow.
5. **Name the schema.** Each prompt ends by naming the output schema, so the prose and the structured
   output agree.

## Interviewer: [`interviewer_prompt.py`](../prompts/interviewer_prompt.py)

**Goal:** collect a usable history in as few turns as possible.

- **SOCRATES framework** (Site, Onset, Character, Radiation, Associations, Time course,
  Exacerbating/relieving factors, Severity) gives the model a checklist instead of open-ended chat.
- **Batch questioning.** Asking one question per turn made consultations long. The prompt asks for 3 to 5
  questions at once, as a numbered list, each covering a *different* SOCRATES dimension, and forbids
  questions that depend on each other's answers so the patient can answer them all in one message.
  A worked example is included because the format matters to the patient.
- **Explicit completion rules.** Vague first message: ask, don't complete. Three or more dimensions
  covered: complete. At most two follow-up rounds. These stop the model from interviewing forever.
- **Emergency fast-track.** With red flags (chest pain, breathing difficulty, stroke signs, severe
  bleeding) the model asks at most 1 or 2 questions and completes, so urgent advice is not delayed.
- **Plain, warm language**, because the reader is the patient.

## Diagnostician: [`diagnostician_prompt.py`](../prompts/diagnostician_prompt.py)

**Goal:** a ranked differential that a reviewer (the Critic, or a clinician) can check.

- **At least three differentials, ranked.** A single answer hides uncertainty.
- **Calibrated confidence.** LLMs tend to give high confidence to everything. The prompt reserves 85+ for
  near-classic presentations, so the score carries information.
- **Evidence both ways.** Each diagnosis needs 2+ supporting items quoted from the history or retrieved
  text, and diagnoses ranked 2 and lower also need evidence *against*. This makes the ranking auditable.
- **Sources and grounding.** Each entry cites a guideline or a knowledge-base id, and the model is told to
  prefer retrieved context over its own training knowledge.
- **Must-not-miss conditions.** The reasoning chain has to name any life-threatening differential that
  still needs excluding, which is what the Critic then checks.

## Critic in the debate: [`critic_debate_prompt.py`](../prompts/critic_debate_prompt.py)

**Goal:** find real problems in the differential, and only real problems.

- **Typed challenges.** Every challenge is one of four types: `missed_diagnosis`, `evidence_gap`,
  `scoring_error` (a CDSS score contradicts the differential), `safety_concern`. Each needs evidence and a
  suggested action. The team's final report calls this structured, rather than free-text, criticism
  "the single most useful prompt-engineering choice we made": it made challenges countable and
  machine-readable, simplified the Diagnostician's reply, and removed vague "this seems unsafe" outputs
  seen in earlier versions.
- **Permission to say nothing.** "Issue NO challenges if DDx is clinically adequate. Minor imperfections
  don't warrant challenges." Without this, a critic always finds something.
- **Safety flag separate from challenges.** Green, yellow or red describes the patient's urgency, not the
  quality of the diagnosis, so a correct diagnosis of meningitis is still red.
- **Debate memory.** Resolved issues must not be raised again, and in the final round only genuine safety
  risks may be raised. This keeps the debate converging within `MAX_DEBATE_ROUNDS`.

## Diagnostician in the debate: [`diagnostician_debate_prompt.py`](../prompts/diagnostician_debate_prompt.py)

**Goal:** answer each challenge on its merits.

- One response per challenge, in order: `accept`, `refute` or `partially_accept`, each with reasoning and
  evidence. Accepting or partially accepting must come with an updated diagnosis entry.
- A refutation needs specific clinical counter-evidence, and any CDSS score cited in the challenge must be
  addressed directly.
- "Don't agree just to be agreeable": LLMs tend to concede to any objection.
  **Open question:** in the 2026-04-21 evaluation every challenge was accepted (100%). With only 7 cases it
  is not possible to tell whether the challenges were all valid or the model is still too agreeable. A
  larger case set with deliberately wrong challenges would separate the two.

## Coordinator: [`coordinator_prompt.py`](../prompts/coordinator_prompt.py)

**Goal:** a response the patient can read and act on.

- **Fixed structure:** empathy, possible diagnoses in plain language, recommended tests, reassurance.
- **Emergency rules have highest priority.** If the safety flag is red or the differential contains a
  life-threatening condition, the response must *open* with urgent instructions (go to the emergency
  department, call 000/911), above the empathy line, and soft phrasing such as "see your doctor when
  convenient" is banned.
- **Output hygiene.** Earlier responses ended with a template placeholder ("Warm regards, [Your Name]").
  The prompt now fixes the sign-off and forbids leaving placeholders, and asks for natural language only,
  no JSON.
- States that this is a preliminary assessment that tests must confirm.

## CDSS selector: [`cdss_prompt.py`](../prompts/cdss_prompt.py)

**Goal:** let the LLM decide *which* risk scores apply, while the scores themselves are computed by
deterministic code in [`cdss/scoring.py`](../cdss/scoring.py).

- A table lists each score with when to use it and the exact parameter shape, including band definitions
  for HEART, so extraction is unambiguous.
- **No invented data.** Parameters come strictly from the history. Unknown values default to false or the
  lowest band, and the model should prefer the lower-risk value over a speculative positive.
- PHQ-9 runs only when all nine item scores are documented.
- An empty list is a valid answer: routine cases (a simple UTI, otitis media) need no score.

## What I would do next

- Grow the harness from 7 to 30+ cases and add cases where the correct move is to *reject* a challenge.
- Run the same prompts on the four supported models (Kimi, Llama 3.3 70B on Groq, GPT-4o, Gemini 2.0 Flash)
  and compare accuracy, safety recall, latency and cost.
- Version the prompts alongside harness results, so each prompt change is tied to a measured effect.
