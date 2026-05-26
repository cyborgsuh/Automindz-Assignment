"""One-off API connectivity debug (not part of pipeline)."""
from __future__ import annotations

import os

import httpx
from dotenv import load_dotenv

load_dotenv()


def main() -> None:
    key = os.getenv("OPENROUTER_API_KEY", "")
    r = httpx.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json={
            "model": "meta-llama/llama-3.1-8b-instruct",
            "messages": [{"role": "user", "content": 'Return JSON: {"decision":"yes","reason":"test"}'}],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        },
        timeout=60,
    )
    print("OpenRouter HM:", r.status_code, r.text[:400])

    token = os.getenv("AI_ARK_TOKEN", "")
    headers = {"X-TOKEN": token, "Content-Type": "application/json", "Accept": "application/json"}
    body = {
        "page": 0,
        "size": 1,
        "account": {"domain": {"any": {"include": ["idorsia.com"]}}},
        "contact": {
            "experience": {
                "current": {"title": {"any": {"include": {"mode": "SMART", "content": ["Regulatory Affairs"]}}}},
            },
        },
    }
    r2 = httpx.post(
        "https://api.ai-ark.com/api/developer-portal/v1/people",
        headers=headers,
        json=body,
        timeout=30,
    )
    print("AI Ark people:", r2.status_code, r2.text[:400])


if __name__ == "__main__":
    main()
