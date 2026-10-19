import sys
import json
sys.path.insert(0, ".")

from models.llm_factory import get_llm_client, chat_completion, extract_json

def pretty(data):
    print(json.dumps(data, indent=2, ensure_ascii=False))


# Test 1: LLM client creation
print("=" * 50)
print("Testing LLM Client Creation...")
print("=" * 50)

try:
    client = get_llm_client()
    print(f"Client created: {type(client).__name__}")
except Exception as e:
    print(f"Client creation failed (expected if no API key): {e}")


# Test 2: Chat completion
print("\n" + "=" * 50)
print("Testing Chat Completion...")
print("=" * 50)

try:
    client = get_llm_client()
    response = chat_completion(client, "What is the most common cause of chest pain? Reply in one sentence.")
    print(f"Response: {response}")
except Exception as e:
    print(f"Chat completion failed (expected if no API key): {e}")


# Test 3: JSON extraction
print("\n" + "=" * 50)
print("Testing JSON Extraction...")
print("=" * 50)

test_cases = [
    '{"status": "complete", "diagnosis": "migraine"}',
    '```json\n{"status": "complete"}\n```',
    'Here is the result: {"status": "ok", "data": {"nested": true}} and more text',
    'No JSON here',
]

for i, case in enumerate(test_cases, 1):
    result = extract_json(case)
    print(f"  Case {i}: {result}")
