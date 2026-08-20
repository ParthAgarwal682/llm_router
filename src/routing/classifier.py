"""Load the trained complexity classifier and classify prompts."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import joblib

from src.routing.features import extract_features

ComplexityTier = Literal["simple", "moderate", "complex"]

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODEL_PATH = ROOT / "data" / "complexity_classifier.joblib"

_bundle: dict | None = None


def _load(model_path: Path = DEFAULT_MODEL_PATH) -> dict:
    global _bundle
    if _bundle is not None and model_path == DEFAULT_MODEL_PATH:
        return _bundle
    if not model_path.exists():
        raise FileNotFoundError(
            f"Classifier not found at {model_path}. "
            "Run: python -m src.routing.train_classifier"
        )
    bundle = joblib.load(model_path)
    if model_path == DEFAULT_MODEL_PATH:
        _bundle = bundle
    return bundle


def classify_complexity(
    prompt: str,
    *,
    model_path: Path = DEFAULT_MODEL_PATH,
) -> ComplexityTier:
    bundle = _load(model_path)
    pipeline = bundle["pipeline"]
    features = extract_features(prompt)
    pred = pipeline.predict([features])[0]
    return str(pred)  # type: ignore[return-value]
