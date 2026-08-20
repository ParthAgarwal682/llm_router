"""Classify prompt complexity, pick a model from routing.yaml, call send_request()."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from src.models.interface import LLMResponse, send_request
from src.models.registry import get_model
from src.routing.classifier import ComplexityTier, classify_complexity

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ROUTING_PATH = ROOT / "config" / "routing.yaml"


def load_tier_model_map(path: Path = DEFAULT_ROUTING_PATH) -> dict[str, str]:
    with path.open() as f:
        data = yaml.safe_load(f)
    tiers = data.get("tiers") or {}
    required = {"simple", "moderate", "complex"}
    missing = required - set(tiers)
    if missing:
        raise ValueError(f"routing.yaml missing tiers: {sorted(missing)}")
    # Validate registry names early
    for model_name in tiers.values():
        get_model(model_name)
    return {str(k): str(v) for k, v in tiers.items()}


@dataclass
class RoutedResponse:
    tier: ComplexityTier
    model_name: str
    model_id: str
    response: LLMResponse

    def summary(self) -> str:
        r = self.response
        return (
            f"tier={self.tier} model={self.model_name} ({self.model_id})\n"
            f"latency_ms={r.latency_ms:.0f} "
            f"tokens_in={r.input_tokens} tokens_out={r.output_tokens} "
            f"cost_usd={r.cost_usd:.6f}\n"
            f"---\n{r.text}"
        )


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
    response = send_request(prompt, model_name, max_tokens=max_tokens)
    return RoutedResponse(
        tier=tier,
        model_name=model_name,
        model_id=config.model_id,
        response=response,
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
        # Keep a tiny structured dump useful for eyeballing
        meta = {
            "tier": result.tier,
            "model_name": result.model_name,
            "cost_usd": result.response.cost_usd,
        }
        print("meta:", meta)
