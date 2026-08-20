"""Model registry: name → OpenRouter model_id, costs, quality tier."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelConfig:
    name: str
    model_id: str  # OpenRouter provider/model slug
    cost_per_1k_input: float  # USD
    cost_per_1k_output: float  # USD
    quality_tier: int  # 1=cheap, 2=mid, 3=expensive


# Costs derived from OpenRouter /api/v1/models pricing (per-token × 1000)
# Verified 2026-07-27.
MODEL_REGISTRY: dict[str, ModelConfig] = {
    "llama_8b": ModelConfig(
        name="llama_8b",
        model_id="meta-llama/llama-3.1-8b-instruct",
        cost_per_1k_input=0.00005,
        cost_per_1k_output=0.00008,
        quality_tier=1,
    ),
    "gpt4o_mini": ModelConfig(
        name="gpt4o_mini",
        model_id="openai/gpt-4o-mini",
        cost_per_1k_input=0.00015,
        cost_per_1k_output=0.0006,
        quality_tier=1,
    ),
    "claude_haiku": ModelConfig(
        name="claude_haiku",
        model_id="anthropic/claude-3-haiku",
        cost_per_1k_input=0.00025,
        cost_per_1k_output=0.00125,
        quality_tier=1,
    ),
    "claude_sonnet_4": ModelConfig(
        name="claude_sonnet_4",
        model_id="anthropic/claude-sonnet-4",
        cost_per_1k_input=0.003,
        cost_per_1k_output=0.015,
        quality_tier=2,
    ),
    "gpt4o": ModelConfig(
        name="gpt4o",
        model_id="openai/gpt-4o",
        cost_per_1k_input=0.0025,
        cost_per_1k_output=0.01,
        quality_tier=3,
    ),
    "llama_70b": ModelConfig(
        name="llama_70b",
        model_id="meta-llama/llama-3.3-70b-instruct",
        cost_per_1k_input=0.00013,
        cost_per_1k_output=0.0004,
        quality_tier=2,
    ),
}


def get_model(name: str) -> ModelConfig:
    try:
        return MODEL_REGISTRY[name]
    except KeyError as exc:
        known = ", ".join(sorted(MODEL_REGISTRY))
        raise KeyError(f"Unknown model {name!r}. Known: {known}") from exc


def list_models() -> list[ModelConfig]:
    return list(MODEL_REGISTRY.values())
