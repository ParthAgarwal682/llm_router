"""Central cached configuration loader for routing.yaml.

Replaces per-file YAML parsing in router.py, single_judge.py, critics.py,
and adjudicator.py. The file is parsed once at first access and cached for
the lifetime of the process.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

from src.models.registry import MODEL_REGISTRY

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ROUTING_PATH = ROOT / "config" / "routing.yaml"

REQUIRED_TIERS = {"simple", "moderate", "complex"}


@lru_cache(maxsize=1)
def load_routing_config(routing_path: Path = DEFAULT_ROUTING_PATH) -> dict:
    """Parse and cache routing.yaml. Validates model names against the registry."""
    with routing_path.open() as f:
        data: dict = yaml.safe_load(f) or {}

    # Validate tier models
    tiers = data.get("tiers") or {}
    missing = REQUIRED_TIERS - set(tiers)
    if missing:
        raise ValueError(f"routing.yaml missing tiers: {sorted(missing)}")
    for model_name in tiers.values():
        if model_name not in MODEL_REGISTRY:
            raise KeyError(f"Unknown model {model_name!r} in routing.yaml tiers")

    # Validate verification models
    ver = data.get("verification") or {}
    for key in ("strong_model", "judge_model"):
        name = ver.get(key)
        if name and name not in MODEL_REGISTRY:
            raise KeyError(f"Unknown model {name!r} in routing.yaml verification.{key}")

    # Validate arbitration models
    arb = data.get("arbitration") or {}
    for dim, model_name in (arb.get("critics") or {}).items():
        if model_name not in MODEL_REGISTRY:
            raise KeyError(f"Unknown model {model_name!r} in routing.yaml arbitration.critics.{dim}")
    adj = arb.get("adjudicator_model")
    if adj and adj not in MODEL_REGISTRY:
        raise KeyError(f"Unknown model {adj!r} in routing.yaml arbitration.adjudicator_model")

    return data


def get_tier_model_map(routing_path: Path = DEFAULT_ROUTING_PATH) -> dict[str, str]:
    """Return tier → registry model name mapping."""
    data = load_routing_config(routing_path)
    return {str(k): str(v) for k, v in (data.get("tiers") or {}).items()}


def get_verification_models(routing_path: Path = DEFAULT_ROUTING_PATH) -> tuple[str, str]:
    """Return (strong_model_name, judge_model_name)."""
    data = load_routing_config(routing_path)
    cfg = data.get("verification") or {}
    strong = str(cfg.get("strong_model") or "gpt4o")
    judge = str(cfg.get("judge_model") or "gpt4o_mini")
    return strong, judge


def get_critic_models(routing_path: Path = DEFAULT_ROUTING_PATH) -> dict[str, str]:
    """Return {dimension: registry_model_name} for each critic."""
    _defaults = {
        "accuracy": "gpt4o_mini",
        "logic": "claude_haiku",
        "completeness": "llama_70b",
    }
    data = load_routing_config(routing_path)
    cfg = (data.get("arbitration") or {}).get("critics") or {}
    return {dim: str(cfg.get(dim) or default) for dim, default in _defaults.items()}


def get_adjudicator_model(routing_path: Path = DEFAULT_ROUTING_PATH) -> str:
    """Return the registry model name for the adjudicator."""
    data = load_routing_config(routing_path)
    cfg = data.get("arbitration") or {}
    return str(cfg.get("adjudicator_model") or "gpt4o_mini")
