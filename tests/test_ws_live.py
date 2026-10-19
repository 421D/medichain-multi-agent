"""Live WebSocket test: connect to /ws/{session_id}, send a chest pain case,
print every event received. Proves whether backend sends agent_message +
debate_challenge events correctly, independent of the frontend.
"""
import asyncio
import json
import sys
import time

import httpx
import websockets


BACKEND_HTTP = "http://127.0.0.1:8000"
BACKEND_WS = "ws://127.0.0.1:8000"

CASE = (
    "I am a 55 year old male with diabetes and hypertension. "
    "Crushing chest pain for 2 hours radiating to left arm and jaw. "
    "Pain 8/10, short of breath, sweating heavily. "
    "Taking metformin and lisinopril. Father had MI at 52."
)


async def main():
    print("=" * 70)
    print("  WebSocket A2A Live Test")
    print("=" * 70)

    # 1. Create session
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{BACKEND_HTTP}/api/v1/sessions/",
            json={"title": "WS live test", "llm_model": "kimi"},
        )
        session = r.json()
        sid = session["id"]
        print(f"\n[1/3] Created session: {sid}")

    # 2. Connect WebSocket
    ws_url = f"{BACKEND_WS}/ws/{sid}"
    print(f"[2/3] Connecting to {ws_url}")

    event_counts: dict[str, int] = {}
    events_received: list[dict] = []

    # ping_interval=None disables client-side keepalive — the long LLM calls
    # in debate rounds can exceed the default 20s ping_timeout, causing the
    # websockets library to close the connection mid-pipeline.
    async with websockets.connect(ws_url, ping_interval=None) as ws:
        print(f"[3/3] Connected. Sending case...")
        await ws.send(json.dumps({"content": CASE}))
        start = time.time()

        print(f"\n--- Event stream ---")
        try:
            while True:
                # Break after 5 minutes max
                if time.time() - start > 300:
                    print("    [timeout 300s]")
                    break
                try:
                    # Debate rounds can take 60-120s per LLM call
                    raw = await asyncio.wait_for(ws.recv(), timeout=150)
                except asyncio.TimeoutError:
                    print(f"    [no events for 150s — assuming done]")
                    break

                try:
                    event = json.loads(raw)
                except Exception:
                    continue

                et = event.get("type", "?")
                event_counts[et] = event_counts.get(et, 0) + 1
                events_received.append(event)

                agent = event.get("agent", "")
                content = (event.get("content") or "")[:80]
                data = event.get("data")
                elapsed = time.time() - start

                if et == "agent_message":
                    print(f"  [{elapsed:5.1f}s] 📨 agent_message [{agent}]: {content}")
                elif et == "debate_challenge":
                    challenge_type = data.get("type", "?") if data else "?"
                    claim = (data.get("claim") or "")[:60] if data else ""
                    print(f"  [{elapsed:5.1f}s] ⚔️  debate_challenge [{challenge_type}]: {claim}")
                elif et == "debate_response":
                    action = data.get("action", "?") if data else "?"
                    print(f"  [{elapsed:5.1f}s] 🛡️  debate_response [{action}]")
                elif et == "diagnosis_result":
                    print(f"  [{elapsed:5.1f}s] 🎯 diagnosis_result")
                    break  # End of pipeline
                elif et == "agent_transition":
                    print(f"  [{elapsed:5.1f}s] ➡️  {agent} starting")
                elif et == "agent_reasoning":
                    print(f"  [{elapsed:5.1f}s] 🧠 {agent}: {content}")
                else:
                    print(f"  [{elapsed:5.1f}s] ? {et} [{agent}]: {content}")

        except websockets.ConnectionClosed:
            print("  [ws closed]")

    print(f"\n--- Summary ---")
    print(f"  Total events: {len(events_received)}")
    for et, count in sorted(event_counts.items()):
        print(f"    {et}: {count}")

    # Assertions
    assert event_counts.get("agent_transition", 0) >= 3, "expected >= 3 agent transitions"
    assert event_counts.get("agent_reasoning", 0) >= 3, "expected >= 3 reasoning events"

    has_message = event_counts.get("agent_message", 0) >= 1
    has_diagnosis = event_counts.get("diagnosis_result", 0) >= 1
    has_debate = event_counts.get("debate_challenge", 0) >= 1

    print(f"\n  agent_message received: {'✅' if has_message else '❌'}")
    print(f"  diagnosis_result received: {'✅' if has_diagnosis else '❌'}")
    print(f"  debate_challenge received: {'✅ (debate produced challenges)' if has_debate else '⚠️  (critic 1-round approval, no challenges)'}")

    if not has_message:
        print("\n❌ BUG: backend did not send agent_message — frontend UI won't update")
        sys.exit(1)
    if not has_diagnosis:
        print("\n❌ BUG: backend did not send diagnosis_result — DiagnosisPanel won't populate")
        sys.exit(1)

    print("\n✅ WebSocket event stream working end-to-end")


if __name__ == "__main__":
    asyncio.run(main())
