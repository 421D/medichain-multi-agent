"""Multi-provider LLM utility module.

⚠️ DEPRECATED for the main agent pipeline. Production agents go through
`agents.base.get_llm()` / `get_structured_llm()` (Kimi via LangChain
ChatOpenAI-compatible client). This module is retained only because
`tests/test_llm.py` imports it as a manual smoke script.

Do NOT add new callers here — extend `agents/base.py` instead, so the
project keeps a single source of truth for LLM provider/model choice.
"""
import os
import json
from dotenv import load_dotenv

load_dotenv()

def get_llm_client():
    """Factory function: returns LLM client based on environment config."""
    model = os.getenv("MEDICHAIN_LLM_MODEL", "groq").lower()

    if model == "groq":
        from groq import Groq
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY not set in .env")
        return Groq(api_key=api_key)

    elif model == "gemini":
        from google import genai
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not set in .env")
        return genai.Client(api_key=api_key)

    elif model == "openai":
        from openai import OpenAI
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not set in .env")
        return OpenAI(api_key=api_key)

    else:
        raise ValueError(f"Unsupported model: {model}. Use 'groq', 'gemini' or 'openai'.")


def chat_completion(client, prompt: str, model_name: str = None) -> str:
    """Unified chat completion function for all providers."""
    model = os.getenv("MEDICHAIN_LLM_MODEL", "groq").lower()

    if model == "groq":
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content.strip()

    elif model == "gemini":
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt
        )
        return response.text.strip()

    elif model == "openai":
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content.strip()


def extract_json(reply: str) -> dict:
    """Robustly extract JSON from LLM response."""
    # Remove markdown code blocks first
    clean = reply.replace("```json", "").replace("```", "").strip()

    # Find the outermost { }
    start = clean.find("{")
    if start == -1:
        return None

    # Walk through to find matching closing brace
    depth = 0
    for i, char in enumerate(clean[start:], start):
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(clean[start:i+1])
                except json.JSONDecodeError:
                    return None
    return None
