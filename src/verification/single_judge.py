"""Cheap single-judge verifier: spot-check a cheap answer against a stronger model."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import yaml

from src.models.interface import LLMResponse, send_request
from src.models.registry import get_model

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ROUTING_PATH = ROOT / "config" / "routing.yaml"

Verdict = Literal["AGREE", "DISAGREE"]

# Defaults use registry names. Model IDs verified via OpenRouter /api/v1/models (2026-07-27):
#   gpt4o          → openai/gpt-4o
#   gpt4o_mini     → openai/gpt-4o-mini
DEFAULT_STRONG_MODEL = "gpt4o"
DEFAULT_JUDGE_MODEL = "gpt4o_mini"

JUDGE_SYSTEM = (
    "You are a strict quality checker. Compare a CANDIDATE answer to a REFERENCE "
    "answer for the same user prompt. Decide if they meaningfully disagree on facts, "
    "conclusions, or required content. Ignore minor wording differences. "
    "Reply in exactly this format:\n"
    "VERDICT: AGREE\n"
    "REASON: <one sentence>\n"
    "or\n"
    "VERDICT: DISAGREE\n"
    "REASON: <one sentence>"
)


@dataclass
class VerificationResult:
    verdict: Verdict
    reason: str
    strong_answer: str
    strong_model: str
    judge_model: str
    strong_cost_usd: float
    judge_cost_usd: float
    promote_to_arbitration: bool

    @property
    def total_cost_usd(self) -> float:
        return self.strong_cost_usd + self.judge_cost_usd


def _load_verification_models(
    routing_path: Path = DEFAULT_ROUTING_PATH,
) -> tuple[str, str]:
    strong = DEFAULT_STRONG_MODEL
    judge = DEFAULT_JUDGE_MODEL
    if routing_path.exists():
        with routing_path.open() as f:
            data = yaml.safe_load(f) or {}
        cfg = data.get("verification") or {}
        strong = str(cfg.get("strong_model", strong))
        judge = str(cfg.get("judge_model", judge))
    # Fail fast if names are wrong
    get_model(strong)
    get_model(judge)
    return strong, judge


def _parse_verdict(text: str) -> tuple[Verdict, str]:
    verdict_match = re.search(r"VERDICT:\s*(AGREE|DISAGREE)", text, re.IGNORECASE)
    reason_match = re.search(r"REASON:\s*(.+)", text, re.IGNORECASE | re.DOTALL)

    if not verdict_match:
        # Conservative: unknown parse → treat as disagreement so we escalate
        return "DISAGREE", f"Could not parse judge output: {text.strip()[:200]}"

    verdict: Verdict = verdict_match.group(1).upper()  # type: ignore[assignment]
    reason = reason_match.group(1).strip().splitlines()[0] if reason_match else text.strip()
    return verdict, reason


def verify_response(
    prompt: str,
    cheap_answer: str,
    *,
    routing_path: Path = DEFAULT_ROUTING_PATH,
    max_tokens_strong: int = 512,
    max_tokens_judge: int = 128,
) -> VerificationResult:
    """
    Re-answer `prompt` on a stronger model, then LLM-judge whether `cheap_answer`
    meaningfully diverges from that strong answer.
    """
    strong_model, judge_model = _load_verification_models(routing_path)

    strong_resp: LLMResponse = send_request(
        prompt,
        strong_model,
        max_tokens=max_tokens_strong,
    )

    judge_prompt = (
        f"USER PROMPT:\n{prompt}\n\n"
        f"CANDIDATE ANSWER (from cheaper model):\n{cheap_answer}\n\n"
        f"REFERENCE ANSWER (from stronger model):\n{strong_resp.text}\n"
    )
    judge_resp: LLMResponse = send_request(
        judge_prompt,
        judge_model,
        system=JUDGE_SYSTEM,
        max_tokens=max_tokens_judge,
    )

    verdict, reason = _parse_verdict(judge_resp.text)
    return VerificationResult(
        verdict=verdict,
        reason=reason,
        strong_answer=strong_resp.text,
        strong_model=strong_model,
        judge_model=judge_model,
        strong_cost_usd=strong_resp.cost_usd,
        judge_cost_usd=judge_resp.cost_usd,
        promote_to_arbitration=(verdict == "DISAGREE"),
    )


if __name__ == "__main__":
    # Deliberately wrong cheap answer should yield DISAGREE
    demo_prompt = "What is the capital of France?"
    wrong_cheap = "The capital of France is Berlin."

    print(f"prompt: {demo_prompt}")
    print(f"cheap_answer (planted wrong): {wrong_cheap}\n")
    result = verify_response(demo_prompt, wrong_cheap)
    print(f"verdict: {result.verdict}")
    print(f"reason: {result.reason}")
    print(f"promote_to_arbitration: {result.promote_to_arbitration}")
    print(f"strong_model: {result.strong_model}")
    print(f"judge_model: {result.judge_model}")
    print(f"strong_answer: {result.strong_answer[:200]}...")
    print(
        f"cost_usd: strong={result.strong_cost_usd:.6f} "
        f"judge={result.judge_cost_usd:.6f} total={result.total_cost_usd:.6f}"
    )
