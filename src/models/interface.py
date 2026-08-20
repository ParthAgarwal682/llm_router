"""Single entry point for all LLM calls via OpenRouter."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass

from dotenv import load_dotenv
from openai import OpenAI

from src.models.registry import ModelConfig, get_model

load_dotenv()

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is not None:
        return _client

    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key or "your-key-here" in api_key:
        raise RuntimeError(
            "Set OPENROUTER_API_KEY in .env (copy from .env.example)."
        )

    _client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
        # Prevent indefinite hangs on a single OpenRouter call (batch/API)
        timeout=60.0,
        max_retries=2,
    )
    return _client


@dataclass
class LLMResponse:
    text: str
    model_name: str
    model_id: str
    latency_ms: float
    input_tokens: int
    output_tokens: int
    cost_usd: float


def get_openrouter_client() -> OpenAI:
    """Shared OpenAI-compatible OpenRouter client. Prefer send_request() for plain text calls."""
    return _get_client()


def send_request(
    prompt: str,
    model_name: str,
    *,
    system: str | None = None,
    max_tokens: int = 512,
) -> LLMResponse:
    """Call OpenRouter for `model_name` from the registry. Nothing else should hit the client."""
    config: ModelConfig = get_model(model_name)
    client = _get_client()

    messages: list[dict[str, str]] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    started = time.perf_counter()
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
        model=config.model_id,
        messages=messages,
        max_tokens=max_tokens,
    )
    latency_ms = (time.perf_counter() - started) * 1000

    usage = completion.usage
    input_tokens = int(usage.prompt_tokens) if usage else 0
    output_tokens = int(usage.completion_tokens) if usage else 0
    cost_usd = (input_tokens / 1000.0) * config.cost_per_1k_input + (
        output_tokens / 1000.0
    ) * config.cost_per_1k_output

    text = completion.choices[0].message.content or ""
    return LLMResponse(
        text=text,
        model_name=config.name,
        model_id=config.model_id,
        latency_ms=latency_ms,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost_usd,
    )
