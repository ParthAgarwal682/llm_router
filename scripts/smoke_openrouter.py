"""Phase 0 throwaway: prove OpenRouter + openai package plumbing works.

Uses the OpenAI SDK pointed at OpenRouter's OpenAI-compatible base URL.
Delete this file once Phase 0 is confirmed.
"""

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

API_KEY = os.getenv("OPENROUTER_API_KEY")
if not API_KEY or "your-key-here" in API_KEY:
    print("ERROR: Set OPENROUTER_API_KEY in .env (copy from .env.example).")
    sys.exit(1)

# Verified against OpenRouter GET /api/v1/models (cheap smoke-test model)
MODEL = "openai/gpt-4o-mini"

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=API_KEY,
)

print(f"Calling {MODEL} via OpenRouter...\n")

completion = client.chat.completions.create(
    extra_headers={
        "HTTP-Referer": os.getenv(
            "OPENROUTER_HTTP_REFERER",
            "https://github.com/local/llm-router-arbitration",
        ),
        "X-OpenRouter-Title": os.getenv(
            "OPENROUTER_APP_TITLE",
            "Smart Router Arbitration",
        ),
    },
    model=MODEL,
    messages=[
        {
            "role": "user",
            "content": "Reply in one short sentence: what is 2+2?",
        }
    ],
)

print(completion.choices[0].message.content)
print(f"\n[ok] model={completion.model!r}")
