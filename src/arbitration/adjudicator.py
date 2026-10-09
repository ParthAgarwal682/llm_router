"""Adjudicator: resolve critic disagreements into a final Verdict."""

from __future__ import annotations

from pathlib import Path

import instructor
from openai import OpenAI

from src.arbitration.schemas import CritiqueReport, Verdict
from src.config import DEFAULT_ROUTING_PATH, get_adjudicator_model as _get_adjudicator_model
from src.models.interface import get_openrouter_client
from src.models.registry import get_model


def _load_adjudicator_model(routing_path: Path = DEFAULT_ROUTING_PATH) -> str:
    """Return the adjudicator model name from cached config."""
    return _get_adjudicator_model(routing_path)


def adjudicate(
    prompt: str,
    candidate_text: str,
    reports: list[CritiqueReport],
    disagreements: list[str],
    *,
    model_name: str | None = None,
) -> Verdict:
    model_name = model_name or _load_adjudicator_model()
    config = get_model(model_name)
    client: instructor.Instructor = instructor.from_openai(
        get_openrouter_client(),
        mode=instructor.Mode.TOOLS,
    )

    reports_blob = "\n\n".join(
        f"[{r.dimension} | model={r.model_name} | score={r.score}/5 | "
        f"confidence={r.self_confidence:.2f}]\n"
        f"issues={r.model_dump_json()}"
        for r in reports
    )
    disagreement_blob = (
        "\n".join(f"- {d}" for d in disagreements) if disagreements else "(none)"
    )

    user_msg = (
        f"ORIGINAL USER PROMPT:\n{prompt}\n\n"
        f"CANDIDATE OUTPUT:\n{candidate_text}\n\n"
        f"CRITIC REPORTS:\n{reports_blob}\n\n"
        f"DETECTED DISAGREEMENTS:\n{disagreement_blob}\n\n"
        "Produce a final Verdict. Confirm only real issues. Dismiss weak or "
        "contradicted flags. Set should_escalate=true if overall_score <= 5."
    )

    return client.chat.completions.create(
        model=config.model_id,
        response_model=Verdict,
        max_retries=2,
        max_tokens=650,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are the Adjudicator for a multi-critic panel. Reason carefully "
                    "through disagreements, weigh critic confidence, and output a calibrated "
                    "Verdict with confirmed_issues, dismissed_flags, and a one-paragraph summary."
                ),
            },
            {"role": "user", "content": user_msg},
        ],
        extra_headers={
            "HTTP-Referer": "https://github.com/local/llm-router-arbitration",
            "X-OpenRouter-Title": "Smart Router Arbitration",
        },
    )
