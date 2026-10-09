"""Specialist critics with structured outputs via instructor + OpenRouter."""

from __future__ import annotations

from pathlib import Path

import instructor
from openai import OpenAI

from src.arbitration.schemas import CritiqueReport
from src.config import DEFAULT_ROUTING_PATH, get_critic_models as _get_critic_models
from src.models.interface import get_openrouter_client
from src.models.registry import get_model


def _load_critic_models(routing_path: Path = DEFAULT_ROUTING_PATH) -> dict[str, str]:
    """Return {dimension: model_name} from cached config."""
    return _get_critic_models(routing_path)


def _instructor_client() -> instructor.Instructor:
    raw: OpenAI = get_openrouter_client()
    return instructor.from_openai(raw, mode=instructor.Mode.TOOLS)


def _run_critic(
    *,
    dimension: str,
    system: str,
    prompt: str,
    candidate_text: str,
    model_name: str,
) -> CritiqueReport:
    config = get_model(model_name)
    client = _instructor_client()
    user_msg = (
        f"ORIGINAL USER PROMPT:\n{prompt}\n\n"
        f"CANDIDATE OUTPUT TO CRITIQUE:\n{candidate_text}\n\n"
        f"Evaluate ONLY the {dimension} dimension. "
        f"Set dimension='{dimension}'. List concrete issues with quotes when possible."
    )
    report = client.chat.completions.create(
        model=config.model_id,
        response_model=CritiqueReport,
        max_retries=2,
        max_tokens=512,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_msg},
        ],
        extra_headers={
            "HTTP-Referer": "https://github.com/local/llm-router-arbitration",
            "X-OpenRouter-Title": "Smart Router Arbitration",
        },
    )
    report.dimension = dimension  # type: ignore[assignment]
    report.model_name = model_name
    return report


def accuracy_critic(prompt: str, candidate_text: str, *, model_name: str | None = None) -> CritiqueReport:
    models = _load_critic_models()
    return _run_critic(
        dimension="accuracy",
        system=(
            "You are an Accuracy Critic. Focus on factual correctness, invented details, "
            "wrong numbers/names/dates, and claims not supported by the prompt. "
            "Ignore style and completeness unless they create a factual error."
        ),
        prompt=prompt,
        candidate_text=candidate_text,
        model_name=model_name or models["accuracy"],
    )


def logic_critic(prompt: str, candidate_text: str, *, model_name: str | None = None) -> CritiqueReport:
    models = _load_critic_models()
    return _run_critic(
        dimension="logic",
        system=(
            "You are a Logic Critic. Focus on contradictions, non sequiturs, broken "
            "reasoning chains, and conclusions that do not follow from the stated premises. "
            "Ignore missing coverage unless it creates a logical hole."
        ),
        prompt=prompt,
        candidate_text=candidate_text,
        model_name=model_name or models["logic"],
    )


def completeness_critic(
    prompt: str,
    candidate_text: str,
    *,
    model_name: str | None = None,
) -> CritiqueReport:
    models = _load_critic_models()
    return _run_critic(
        dimension="completeness",
        system=(
            "You are a Completeness Critic. Focus on whether the candidate addresses every "
            "part of the user prompt, required constraints, and asked formats. "
            "Flag omissions and partial answers even if what is present is accurate."
        ),
        prompt=prompt,
        candidate_text=candidate_text,
        model_name=model_name or models["completeness"],
    )
