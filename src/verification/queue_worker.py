"""Async wrappers so verification can run without blocking the user response path."""

from __future__ import annotations

import asyncio
from pathlib import Path

from src.verification.single_judge import VerificationResult, verify_response


async def verify_response_async(
    prompt: str,
    cheap_answer: str,
    *,
    routing_path: Path | None = None,
    max_tokens_strong: int = 512,
    max_tokens_judge: int = 128,
) -> VerificationResult:
    """Run the sync verifier in a worker thread via asyncio.to_thread."""
    kwargs: dict = {
        "max_tokens_strong": max_tokens_strong,
        "max_tokens_judge": max_tokens_judge,
    }
    if routing_path is not None:
        kwargs["routing_path"] = routing_path

    return await asyncio.to_thread(
        verify_response,
        prompt,
        cheap_answer,
        **kwargs,
    )


if __name__ == "__main__":
    async def _demo() -> None:
        result = await verify_response_async(
            "What is 2 + 2?",
            "2 + 2 equals 5.",  # planted wrong
        )
        print(f"verdict: {result.verdict}")
        print(f"reason: {result.reason}")
        print(f"promote_to_arbitration: {result.promote_to_arbitration}")

    asyncio.run(_demo())
