"""FastAPI: routed completions + forced arbitration + stats."""

from __future__ import annotations

import json
import traceback
from contextlib import asynccontextmanager
from typing import Any

from fastapi import BackgroundTasks, FastAPI, HTTPException
from pydantic import BaseModel, Field

from src.arbitration.graph import run_arbitration
from src.models.registry import get_model
from src.routing.router import route_and_call
from src.storage import db
from src.verification.single_judge import verify_response

BASELINE_MODEL = "gpt4o"  # "always use the top model" counterfactual


def _baseline_cost(input_tokens: int, output_tokens: int) -> float:
    cfg = get_model(BASELINE_MODEL)
    return (input_tokens / 1000.0) * cfg.cost_per_1k_input + (
        output_tokens / 1000.0
    ) * cfg.cost_per_1k_output


def _verify_and_maybe_arbitrate(request_id: str, prompt: str, cheap_answer: str) -> None:
    try:
        db.update_request(request_id, status="verifying")
        verification = verify_response(prompt, cheap_answer)
        extra_cost = verification.total_cost_usd
        row = db.get_request(request_id)
        routed_cost = row.cost_usd if row else 0.0

        if not verification.promote_to_arbitration:
            db.update_request(
                request_id,
                cost_usd=routed_cost + extra_cost,
                promoted_to_arbitration=False,
                verify_verdict=verification.verdict,
                verify_reason=verification.reason,
                status="complete",
            )
            return

        db.update_request(
            request_id,
            status="arbitrating",
            promoted_to_arbitration=True,
            verify_verdict=verification.verdict,
            verify_reason=verification.reason,
            cost_usd=routed_cost + extra_cost,
        )
        result = run_arbitration(prompt, cheap_answer)
        verdict = result["verdict"]
        db.update_request(
            request_id,
            promoted_to_arbitration=True,
            verify_verdict=verification.verdict,
            verify_reason=verification.reason,
            verdict_json=verdict.model_dump_json() if verdict else None,
            status="complete",
        )
    except Exception as exc:  # noqa: BLE001 — background task must not crash the worker silently
        db.update_request(
            request_id,
            status=f"error: {type(exc).__name__}: {exc}",
        )
        traceback.print_exc()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    db.init_db()
    # Docker bind-mounts ./data and may hide the image-trained classifier
    from pathlib import Path

    from src.routing.classifier import DEFAULT_MODEL_PATH
    from src.routing.train_classifier import train_and_save

    if not Path(DEFAULT_MODEL_PATH).exists():
        train_and_save()
    yield


app = FastAPI(
    title="Smart Router + Multi-Critic Arbitration",
    version="0.5.0",
    lifespan=lifespan,
)


class CompletionRequest(BaseModel):
    prompt: str = Field(min_length=1)
    max_tokens: int = Field(default=512, ge=16, le=4096)


class CompletionResponse(BaseModel):
    id: str
    prompt: str
    text: str
    tier: str
    model_used: str
    model_id: str
    cost_usd: float
    baseline_cost_usd: float
    latency_ms: float
    status: str
    note: str = "Verification/arbitration runs in the background; poll GET /v1/arbitrations/{id}"


class ArbitrateRequest(BaseModel):
    prompt: str = Field(min_length=1)
    text: str = Field(min_length=1, description="Candidate output to arbitrate")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/completions", response_model=CompletionResponse)
def completions(
    body: CompletionRequest,
    background_tasks: BackgroundTasks,
) -> CompletionResponse:
    routed = route_and_call(body.prompt, max_tokens=body.max_tokens)
    r = routed.response
    baseline = _baseline_cost(r.input_tokens, r.output_tokens)
    request_id = db.create_request(
        prompt=body.prompt,
        response_text=r.text,
        tier=str(routed.tier),
        model_used=routed.model_name,
        model_id=routed.model_id,
        cost_usd=r.cost_usd,
        baseline_cost_usd=baseline,
        latency_ms=r.latency_ms,
        status="routed",
    )
    background_tasks.add_task(
        _verify_and_maybe_arbitrate,
        request_id,
        body.prompt,
        r.text,
    )
    return CompletionResponse(
        id=request_id,
        prompt=body.prompt,
        text=r.text,
        tier=str(routed.tier),
        model_used=routed.model_name,
        model_id=routed.model_id,
        cost_usd=r.cost_usd,
        baseline_cost_usd=baseline,
        latency_ms=r.latency_ms,
        status="routed",
    )


@app.post("/v1/arbitrate")
def arbitrate(body: ArbitrateRequest) -> dict[str, Any]:
    result = run_arbitration(body.prompt, body.text)
    verdict = result["verdict"]
    request_id = db.create_request(
        prompt=body.prompt,
        response_text=body.text,
        tier="forced",
        model_used="n/a",
        model_id="n/a",
        cost_usd=0.0,
        baseline_cost_usd=0.0,
        latency_ms=0.0,
        promoted_to_arbitration=True,
        verify_verdict="FORCED",
        verify_reason="Caller forced full arbitration via POST /v1/arbitrate",
        verdict_json=verdict.model_dump_json() if verdict else None,
        status="complete",
    )
    return {
        "id": request_id,
        "disagreements": result.get("disagreements") or [],
        "accuracy_report": result["accuracy_report"].model_dump()
        if result.get("accuracy_report")
        else None,
        "logic_report": result["logic_report"].model_dump()
        if result.get("logic_report")
        else None,
        "completeness_report": result["completeness_report"].model_dump()
        if result.get("completeness_report")
        else None,
        "verdict": verdict.model_dump() if verdict else None,
    }


@app.get("/v1/stats")
def stats() -> dict[str, Any]:
    return db.get_stats()


@app.get("/v1/arbitrations/{request_id}")
def get_arbitration(request_id: str) -> dict[str, Any]:
    row = db.get_request(request_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Request not found")
    return row.to_dict()
