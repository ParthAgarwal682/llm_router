"""Classify prompt complexity, pick a model from routing.yaml, call send_request().

Adds retry/fallback: if the chosen model errors or times out, retry once on the
same model, then fall back to the next tier up. Records whether a fallback occurred.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from src.config import DEFAULT_ROUTING_PATH, get_tier_model_map
from src.models.interface import LLMResponse, send_request
from src.models.registry import get_model
from src.routing.classifier import ComplexityTier, classify_complexity

logger = logging.getLogger(__name__)

# Ordered tiers from cheapest to most capable — used for fallback escalation
_TIER_ORDER: list[str] = ["simple", "moderate", "complex"]


def load_tier_model_map(path: Path = DEFAULT_ROUTING_PATH) -> dict[str, str]:
    """Thin wrapper kept for backward compatibility; uses the cached config loader."""
    return get_tier_model_map(path)


@dataclass
class RoutedResponse:
    tier: ComplexityTier
    model_name: str
    model_id: str
    response: LLMResponse
    fallback_used: bool = False
    fallback_from_model: str | None = None

    def summary(self) -> str:
        r = self.response
        fallback_note = ""
        if self.fallback_used:
            fallback_note = f" [FALLBACK from {self.fallback_from_model}]"
        return (
            f"tier={self.tier} model={self.model_name} ({self.model_id}){fallback_note}\n"
            f"latency_ms={r.latency_ms:.0f} "
            f"tokens_in={r.input_tokens} tokens_out={r.output_tokens} "
            f"cost_usd={r.cost_usd:.6f}\n"
            f"---\n{r.text}"
        )


def _try_send(
    prompt: str,
    model_name: str,
    max_tokens: int,
    attempts: int = 2,
) -> LLMResponse:
    """Attempt send_request up to `attempts` times on the same model before raising."""
    last_exc: Exception | None = None
    for attempt in range(attempts):
        try:
            return send_request(prompt, model_name, max_tokens=max_tokens)
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            logger.warning(
                "send_request attempt %d/%d failed for model %s: %s",
                attempt + 1, attempts, model_name, exc,
            )
    raise last_exc  # type: ignore[misc]


def route_and_call(
    prompt: str,
    *,
    routing_path: Path = DEFAULT_ROUTING_PATH,
    max_tokens: int = 512,
) -> RoutedResponse:
    tier = classify_complexity(prompt)
    tier_map = load_tier_model_map(routing_path)

    model_name = tier_map[tier]
    config = get_model(model_name)
    fallback_used = False
    fallback_from_model: str | None = None

    try:
        response = _try_send(prompt, model_name, max_tokens, attempts=2)
    except Exception as primary_exc:  # noqa: BLE001
        # Find next tier up for fallback
        try:
            tier_idx = _TIER_ORDER.index(tier)
        except ValueError:
            tier_idx = -1

        fallback_response = None
        for fallback_tier in _TIER_ORDER[tier_idx + 1:]:
            fallback_model = tier_map.get(fallback_tier)
            if fallback_model and fallback_model != model_name:
                logger.warning(
                    "Primary model %s failed (%s), falling back to %s (%s)",
                    model_name, primary_exc, fallback_model, fallback_tier,
                )
                try:
                    fallback_response = _try_send(
                        prompt, fallback_model, max_tokens, attempts=1
                    )
                    fallback_from_model = model_name
                    model_name = fallback_model
                    config = get_model(model_name)
                    fallback_used = True
                    break
                except Exception as fb_exc:  # noqa: BLE001
                    logger.warning(
                        "Fallback to %s also failed: %s", fallback_model, fb_exc
                    )

        if fallback_response is None:
            raise  # re-raise original if all fallbacks exhausted

        response = fallback_response

    return RoutedResponse(
        tier=tier,
        model_name=model_name,
        model_id=config.model_id,
        response=response,
        fallback_used=fallback_used,
        fallback_from_model=fallback_from_model,
    )


if __name__ == "__main__":
    import sys

    samples = sys.argv[1:] or [
        "What is the capital of France?",
        "Compare TCP and UDP in a short markdown table with 4 rows.",
        "Analyze the economic tradeoffs of carbon taxes versus cap-and-trade; "
        "recommend a policy for a developing country with weak institutions.",
    ]
    for i, prompt in enumerate(samples, start=1):
        print(f"\n===== sample {i} =====")
        print(f"prompt: {prompt}")
        result = route_and_call(prompt)
        print(result.summary())
        meta = {
            "tier": result.tier,
            "model_name": result.model_name,
            "cost_usd": result.response.cost_usd,
            "fallback_used": result.fallback_used,
        }
        print("meta:", meta)
