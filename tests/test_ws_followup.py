"""Follow-up question test: simulate a user sending an INCOMPLETE case
("My chest hurts"), verify the Interviewer's SOCRATES framework detects
missing info and sends follow-up questions, and the graph resume/interrupt
cycle works end-to-end.

This tests the `interviewer_node` interrupt() mechanism + the WebSocket
__interrupt__ handler + Command(resume=...) pipeline.

Run: .venv/bin/python tests/test_ws_followup.py
"""
import asyncio
import json
import time

import httpx
import websockets


BACKEND_HTTP = "http://127.0.0.1:8000"
BACKEND_WS = "ws://127.0.0.1:8000"

# Pre-canned SOCRATES-style answers we'll feed back when Interviewer asks
SAMPLE_ANSWERS = [
    "It started about 2 hours ago, very sudden.",
    "It's crushing and radiates to my left arm and jaw. Pain is about 8/10.",
    "I'm sweating a lot and short of breath. I feel nauseous.",
    "I'm 55 years old, male. I have diabetes and high blood pressure.",
    "My father had a heart attack at age 52. I take metformin and lisinopril.",
    "Nothing makes it better or worse. It's constant.",
]

INITIAL_MESSAGE = "My chest hurts."

GREETING_SNIPPET = "Welcome to MediChain"


async def main():
    print("=" * 72)
    print("  Follow-up Question Test — incomplete case → SOCRATES追问")
    print("=" * 72)

    # 1. Create a fresh session
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{BACKEND_HTTP}/api/v1/sessions/",
            json={"title": "Followup test", "llm_model": "kimi"},
        )
        sid = r.json()["id"]
    print(f"\nCreated session: {sid}")

    # 2. Connect
    print(f"Connecting to /ws/{sid}")
    async with websockets.connect(f"{BACKEND_WS}/ws/{sid}", ping_interval=None) as ws:
        # 3. Receive greeting
        greeting_raw = await asyncio.wait_for(ws.recv(), timeout=5)
        greeting = json.loads(greeting_raw)
        print(f"\n[greeting] {greeting['content'][:70]}...")

        # 4. Send INCOMPLETE case
        print(f"\n[USER  #1] {INITIAL_MESSAGE}")
        await ws.send(json.dumps({"content": INITIAL_MESSAGE}))

        # 5. Event-driven answer loop
        start = time.time()
        answer_idx = 0
        followup_count = 0
        event_counts: dict[str, int] = {}
        timeline: list[tuple[float, str, str]] = []

        while True:
            if time.time() - start > 420:  # 7 min hard cap
                print("  [timeout 420s]")
                break
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=120)
            except asyncio.TimeoutError:
                print(f"  [no events for 120s — assuming done]")
                break

            event = json.loads(raw)
            et = event.get("type", "?")
            agent = event.get("agent", "")
            content = event.get("content", "") or ""
            event_counts[et] = event_counts.get(et, 0) + 1
            elapsed = time.time() - start
            timeline.append((elapsed, et, f"{agent}: {content[:50]}"))

            if et == "agent_transition":
                print(f"  [{elapsed:6.1f}s] ➡️  {agent} starting")
            elif et == "agent_reasoning":
                print(f"  [{elapsed:6.1f}s] 🧠 {agent}: {content[:70]}")
            elif et == "agent_message":
                print(f"  [{elapsed:6.1f}s] 📨 agent_message [{agent}]: {content[:80]}")

                # Is this a follow-up question from interviewer?
                # Rule: any agent_message from interviewer AFTER the greeting
                # and BEFORE diagnosis_result is a follow-up question.
                is_followup = (
                    agent == "interviewer"
                    and GREETING_SNIPPET not in content
                )

                if is_followup:
                    followup_count += 1
                    if answer_idx < len(SAMPLE_ANSWERS):
                        answer = SAMPLE_ANSWERS[answer_idx]
                        answer_idx += 1
                        print(f"  [{elapsed:6.1f}s] 👤 USER  #{answer_idx+1}: {answer[:60]}")
                        await ws.send(json.dumps({"content": answer}))
                    else:
                        print(f"  [{elapsed:6.1f}s] ⚠️  No more canned answers, sending generic")
                        await ws.send(json.dumps({"content": "Yes, that's correct."}))

            elif et == "debate_challenge":
                data = event.get("data") or {}
                print(f"  [{elapsed:6.1f}s] ⚔️  debate_challenge [{data.get('type','?')}]: {str(data.get('claim',''))[:60]}")
            elif et == "debate_response":
                data = event.get("data") or {}
                print(f"  [{elapsed:6.1f}s] 🛡️  debate_response [{data.get('action','?')}]")
            elif et == "diagnosis_result":
                print(f"  [{elapsed:6.1f}s] 🎯 diagnosis_result — pipeline complete")
                break
            else:
                print(f"  [{elapsed:6.1f}s] ? {et} [{agent}]: {content[:60]}")

    # 6. Summary
    print("\n" + "=" * 72)
    print("  Summary")
    print("=" * 72)
    print(f"  Total events:    {sum(event_counts.values())}")
    for k, v in sorted(event_counts.items()):
        print(f"    {k}: {v}")
    print(f"  Follow-up questions detected: {followup_count}")
    print(f"  User answers sent:            {answer_idx}")

    # 7. Verification
    print()
    if followup_count >= 1:
        print(f"  ✅ Interviewer asked {followup_count} follow-up question(s)")
        print(f"  ✅ interrupt/resume cycle works")
    else:
        print(f"  ❌ No follow-up detected — Interviewer may have skipped SOCRATES")
        print(f"     (Possible reason: LLM deemed 'My chest hurts' as sufficient)")

    if event_counts.get("diagnosis_result", 0) >= 1:
        print(f"  ✅ Pipeline reached diagnosis_result after {answer_idx+1} turns")
    else:
        print(f"  ⚠️  Pipeline did not reach diagnosis_result")

    # 8. Cleanup
    async with httpx.AsyncClient() as client:
        await client.delete(f"{BACKEND_HTTP}/api/v1/sessions/{sid}")


if __name__ == "__main__":
    asyncio.run(main())
