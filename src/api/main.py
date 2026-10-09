"""FastAPI: routed completions + forced arbitration + stats + chat conversations.

Phase 1 additions:
- Auth required on all /v1/* endpoints (except /v1/auth/*)
- CORS restricted to ALLOWED_ORIGINS env var
- Per-user rate limiting and daily cap (via deps.py)
- User-scoped data access (404 on wrong-user resources)

Phase 2 additions:
- Three-way cost tracking: answer_cost, verification_cost, net_saved
- compute_savings() used to finalize cost fields after background verification

Phase 3 additions:
- POST /v1/chat/stream — SSE streaming completions
- GET /v1/requests/{id}/events — SSE status update stream
- GET /v1/me/stats — user savings dashboard
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import traceback
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any, AsyncGenerator

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from src.api.deps import (
    MAX_PROMPT_LENGTH,
    get_current_user,
    get_current_user_with_limits,
)
from src.api.routers import auth_router, conversations, me_router
from src.arbitration.graph import run_arbitration
from src.models.registry import baseline_cost
from src.routing.router import route_and_call
from src.storage import db
from src.storage.db import UserRow, compute_savings
from src.verification.single_judge import verify_response

logger = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIR = ROOT / "frontend"

# ---------------------------------------------------------------------------
# CORS — controlled by ALLOWED_ORIGINS env var
# ---------------------------------------------------------------------------

def _parse_origins() -> list[str]:
    raw = os.getenv("ALLOWED_ORIGINS", "")
    if not raw or raw.strip() == "*":
        # In development, fall back to localhost defaults
        return [
            "http://localhost:3000",
            "http://localhost:8000",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:8000",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:8443",
            "http://127.0.0.1:8443",
        ]
    return [o.strip() for o in raw.split(",") if o.strip()]


ALLOWED_ORIGINS = _parse_origins()


# ---------------------------------------------------------------------------
# Background verification / arbitration (Phase 2 cost-aware version)
# ---------------------------------------------------------------------------

# Cap concurrent background verification jobs to avoid overwhelming OpenRouter
_VERIFY_SEMAPHORE = asyncio.Semaphore(int(os.getenv("MAX_CONCURRENT_VERIFICATIONS", "5")))


def _verify_and_maybe_arbitrate(
    request_id: str,
    prompt: str,
    cheap_answer: str,
    answer_cost: float,
    baseline_cost_usd: float,
) -> None:
    """Background task: verify cheap answer, escalate if needed, finalize costs."""
    try:
        db.update_request(request_id, status="verifying")
        verification = verify_response(prompt, cheap_answer)
        verification_cost = verification.total_cost_usd

        if not verification.promote_to_arbitration:
            savings = compute_savings(
                baseline_cost_usd=baseline_cost_usd,
                answer_cost=answer_cost,
                verification_cost=verification_cost,
            )
            db.update_request(
                request_id,
                cost_usd=savings["cost_usd"],
                verification_cost=verification_cost,
                net_saved=savings["net_saved"],
                saved_percent=savings["saved_percent"],
                savings_final=True,
                promoted_to_arbitration=False,
                verify_verdict=verification.verdict,
                verify_reason=verification.reason,
                status="complete",
            )
            return

        # Escalate to arbitration
        db.update_request(
            request_id,
            status="arbitrating",
            promoted_to_arbitration=True,
            verify_verdict=verification.verdict,
            verify_reason=verification.reason,
        )
        result = run_arbitration(prompt, cheap_answer)
        verdict = result["verdict"]

        # Arbitration may add more cost — currently critics don't expose usage cleanly.
        # We record what we know and flag the row as final.
        savings = compute_savings(
            baseline_cost_usd=baseline_cost_usd,
            answer_cost=answer_cost,
            verification_cost=verification_cost,
        )
        db.update_request(
            request_id,
            cost_usd=savings["cost_usd"],
            verification_cost=verification_cost,
            net_saved=savings["net_saved"],
            saved_percent=savings["saved_percent"],
            savings_final=True,
            promoted_to_arbitration=True,
            verify_verdict=verification.verdict,
            verify_reason=verification.reason,
            verdict_json=verdict.model_dump_json() if verdict else None,
            status="complete",
        )
    except Exception as exc:  # noqa: BLE001 — must not crash the worker silently
        db.update_request(
            request_id,
            status=f"error: {type(exc).__name__}: {exc}",
        )
        logger.error("Background verification failed for %s", request_id, exc_info=True)


async def _verify_async(
    request_id: str,
    prompt: str,
    cheap_answer: str,
    answer_cost: float,
    baseline_cost_usd: float,
) -> None:
    """Async wrapper that respects the concurrency semaphore."""
    async with _VERIFY_SEMAPHORE:
        await asyncio.to_thread(
            _verify_and_maybe_arbitrate,
            request_id,
            prompt,
            cheap_answer,
            answer_cost,
            baseline_cost_usd,
        )


# ---------------------------------------------------------------------------
# App lifecycle
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(_app: FastAPI):
    db.init_db()
    from src.routing.classifier import DEFAULT_MODEL_PATH
    from src.routing.train_classifier import train_and_save

    if not Path(DEFAULT_MODEL_PATH).exists():
        train_and_save()

    # Validate JWT_SECRET is configured
    try:
        from src.api.auth import get_jwt_secret
        get_jwt_secret()
    except RuntimeError as exc:
        logger.error("STARTUP ERROR: %s", exc)
        raise

    yield


app = FastAPI(
    title="Smart Router + Multi-Critic Arbitration",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Mount static frontend assets
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

# Register routers
app.include_router(auth_router.router)
app.include_router(conversations.router)
app.include_router(me_router.router)


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class CompletionRequest(BaseModel):
    prompt: str = Field(min_length=1)
    max_tokens: int = Field(default=512, ge=16, le=4096)
    conversation_id: str | None = Field(default=None)
    session_id: str | None = Field(default=None)


class CompletionResponse(BaseModel):
    id: str
    prompt: str
    text: str
    tier: str
    model_used: str
    model_id: str
    cost_usd: float
    answer_cost: float
    baseline_cost_usd: float
    net_saved: float | None          # None = provisional (background task running)
    saved_percent: float | None
    savings_final: bool
    latency_ms: float
    status: str
    conversation_id: str | None = None
    session_id: str | None = None
    fallback_used: bool = False
    note: str = "Verification/arbitration runs in background; poll GET /v1/requests/{id}"


class ArbitrateRequest(BaseModel):
    prompt: str = Field(min_length=1)
    text: str = Field(min_length=1)


class ChatStreamRequest(BaseModel):
    prompt: str = Field(min_length=1)
    conversation_id: str | None = None
    max_tokens: int = Field(default=512, ge=16, le=4096)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Frontend SPA
# ---------------------------------------------------------------------------

@app.get("/")
def serve_frontend():
    index = FRONTEND_DIR / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return {"message": "Frontend not found. Run the Next.js app at /web instead."}


# ---------------------------------------------------------------------------
# POST /v1/completions (non-streaming, auth-required, rate-limited)
# ---------------------------------------------------------------------------

@app.post("/v1/completions", response_model=CompletionResponse)
async def completions(
    body: CompletionRequest,
    background_tasks: BackgroundTasks,
    current_user: Annotated[UserRow, Depends(get_current_user_with_limits)],
) -> CompletionResponse:
    if len(body.prompt) > MAX_PROMPT_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Prompt too long ({len(body.prompt)} chars). Max: {MAX_PROMPT_LENGTH}.",
        )

    routed = route_and_call(body.prompt, max_tokens=body.max_tokens)
    r = routed.response
    b_cost = baseline_cost(r.input_tokens, r.output_tokens)
    answer_cost_val = r.cost_usd

    # Provisional savings at time of response (verification cost = 0 yet)
    provisional_savings = compute_savings(
        baseline_cost_usd=b_cost,
        answer_cost=answer_cost_val,
        verification_cost=0.0,
    )

    if body.conversation_id:
        db.touch_conversation(body.conversation_id)

    request_id = db.create_request(
        prompt=body.prompt,
        response_text=r.text,
        tier=str(routed.tier),
        model_used=routed.model_name,
        model_id=routed.model_id,
        cost_usd=answer_cost_val,
        baseline_cost_usd=b_cost,
        latency_ms=r.latency_ms,
        status="routed",
        conversation_id=body.conversation_id,
        session_id=body.session_id,
        user_id=current_user.id,
        answer_cost=answer_cost_val,
        verification_cost=0.0,
        net_saved=provisional_savings["net_saved"],
        saved_percent=provisional_savings["saved_percent"],
        savings_final=False,
        fallback_used=routed.fallback_used,
        fallback_from_model=routed.fallback_from_model,
    )

    # Run verification in background with async semaphore
    background_tasks.add_task(
        _verify_async,
        request_id,
        body.prompt,
        r.text,
        answer_cost_val,
        b_cost,
    )

    return CompletionResponse(
        id=request_id,
        prompt=body.prompt,
        text=r.text,
        tier=str(routed.tier),
        model_used=routed.model_name,
        model_id=routed.model_id,
        cost_usd=answer_cost_val,
        answer_cost=answer_cost_val,
        baseline_cost_usd=b_cost,
        net_saved=provisional_savings["net_saved"],
        saved_percent=provisional_savings["saved_percent"],
        savings_final=False,
        latency_ms=r.latency_ms,
        status="routed",
        conversation_id=body.conversation_id,
        session_id=body.session_id,
        fallback_used=routed.fallback_used,
    )


# ---------------------------------------------------------------------------
# POST /v1/chat/stream — SSE streaming completions
# ---------------------------------------------------------------------------

async def _sse_event(event: str, data: Any) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


async def _stream_completion(
    body: ChatStreamRequest,
    current_user: UserRow,
) -> AsyncGenerator[str, None]:
    """Generate SSE events for a streaming chat completion."""
    try:
        # Create conversation if not provided
        conversation_id = body.conversation_id
        if not conversation_id:
            conversation_id = db.create_conversation(
                session_id=current_user.id,
                title="New conversation",
                user_id=current_user.id,
            )

        # Route the request (sync, run in thread)
        routed = await asyncio.to_thread(
            route_and_call, body.prompt, max_tokens=body.max_tokens
        )
        r = routed.response
        b_cost = baseline_cost(r.input_tokens, r.output_tokens)
        answer_cost_val = r.cost_usd

        # Send meta event first
        yield await _sse_event("meta", {
            "model": routed.model_name,
            "model_id": routed.model_id,
            "tier": str(routed.tier),
            "conversation_id": conversation_id,
        })

        # Stream text token by token (simulate token streaming from full response)
        # OpenRouter via openai SDK doesn't support SSE streaming in this setup;
        # we send the full text as word-chunks for a streaming UX.
        words = r.text.split(" ")
        for i, word in enumerate(words):
            chunk = word if i == 0 else " " + word
            yield await _sse_event("token", {"delta": chunk})
            await asyncio.sleep(0)  # yield control

        # Provisional savings
        provisional_savings = compute_savings(
            baseline_cost_usd=b_cost,
            answer_cost=answer_cost_val,
            verification_cost=0.0,
        )

        # Persist to DB
        db.touch_conversation(conversation_id)
        request_id = db.create_request(
            prompt=body.prompt,
            response_text=r.text,
            tier=str(routed.tier),
            model_used=routed.model_name,
            model_id=routed.model_id,
            cost_usd=answer_cost_val,
            baseline_cost_usd=b_cost,
            latency_ms=r.latency_ms,
            status="routed",
            conversation_id=conversation_id,
            session_id=current_user.id,
            user_id=current_user.id,
            answer_cost=answer_cost_val,
            verification_cost=0.0,
            net_saved=provisional_savings["net_saved"],
            saved_percent=provisional_savings["saved_percent"],
            savings_final=False,
            fallback_used=routed.fallback_used,
            fallback_from_model=routed.fallback_from_model,
        )

        # Kick off verification in background
        asyncio.create_task(
            _verify_async(request_id, body.prompt, r.text, answer_cost_val, b_cost)
        )

        yield await _sse_event("done", {
            "request_id": request_id,
            "conversation_id": conversation_id,
            "answer_cost": answer_cost_val,
            "baseline_cost": b_cost,
            "net_saved": provisional_savings["net_saved"],
            "saved_percent": provisional_savings["saved_percent"],
            "provisional": True,
            "fallback_used": routed.fallback_used,
        })

    except HTTPException as exc:
        yield await _sse_event("error", {
            "code": "http_error",
            "status": exc.status_code,
            "message": exc.detail,
        })
    except Exception as exc:  # noqa: BLE001
        logger.error("Stream error", exc_info=True)
        yield await _sse_event("error", {
            "code": "internal_error",
            "message": str(exc),
        })


@app.post("/v1/chat/stream")
async def chat_stream(
    body: ChatStreamRequest,
    current_user: Annotated[UserRow, Depends(get_current_user_with_limits)],
) -> StreamingResponse:
    if len(body.prompt) > MAX_PROMPT_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Prompt too long. Max: {MAX_PROMPT_LENGTH} chars.",
        )
    return StreamingResponse(
        _stream_completion(body, current_user),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable nginx buffering
        },
    )


# ---------------------------------------------------------------------------
# GET /v1/requests/{id}/events — SSE status update stream
# ---------------------------------------------------------------------------

@app.get("/v1/requests/{request_id}/events")
async def request_events(
    request_id: str,
    current_user: Annotated[UserRow, Depends(get_current_user)],
) -> StreamingResponse:
    """SSE stream of status changes for a request until savings_final=True."""

    async def _generate() -> AsyncGenerator[str, None]:
        # Verify ownership first
        row = db.get_request(request_id, user_id=current_user.id)
        if row is None:
            yield await _sse_event("error", {"code": "not_found", "message": "Request not found"})
            return

        if row.savings_final:
            yield await _sse_event("final", _request_status_payload(row))
            return

        # Poll until final (max 120 s, poll every 2 s)
        max_polls = 60
        for _ in range(max_polls):
            await asyncio.sleep(2)
            row = db.get_request(request_id, user_id=current_user.id)
            if row is None:
                break

            yield await _sse_event("status", _request_status_payload(row))

            if row.savings_final or (row.status and row.status.startswith("error")):
                yield await _sse_event("final", _request_status_payload(row))
                return

        yield await _sse_event("timeout", {"message": "Timed out waiting for verification"})

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _request_status_payload(row) -> dict[str, Any]:
    verdict_summary = None
    if row.verdict_json:
        try:
            v = json.loads(row.verdict_json)
            verdict_summary = {
                "overall_score": v.get("overall_score"),
                "should_escalate": v.get("should_escalate"),
                "summary": v.get("summary"),
                "confirmed_issues": v.get("confirmed_issues", []),
            }
        except json.JSONDecodeError:
            pass
    return {
        "request_id": row.id,
        "status": row.status,
        "savings_final": row.savings_final,
        "answer_cost": row.answer_cost,
        "verification_cost": row.verification_cost,
        "cost_usd": row.cost_usd,
        "baseline_cost_usd": row.baseline_cost_usd,
        "net_saved": row.net_saved,
        "saved_percent": row.saved_percent,
        "promoted_to_arbitration": row.promoted_to_arbitration,
        "verify_verdict": row.verify_verdict,
        "verify_reason": row.verify_reason,
        "verdict_summary": verdict_summary,
    }


# ---------------------------------------------------------------------------
# GET /v1/requests/{id} — user-scoped request detail
# ---------------------------------------------------------------------------

@app.get("/v1/requests/{request_id}")
def get_request(
    request_id: str,
    current_user: Annotated[UserRow, Depends(get_current_user)],
) -> dict[str, Any]:
    row = db.get_request(request_id, user_id=current_user.id)
    if row is None:
        raise HTTPException(status_code=404, detail="Request not found")
    return row.to_dict()


# ---------------------------------------------------------------------------
# GET /v1/arbitrations/{id} — legacy alias kept for backward compat
# ---------------------------------------------------------------------------

@app.get("/v1/arbitrations/{request_id}")
def get_arbitration(
    request_id: str,
    current_user: Annotated[UserRow, Depends(get_current_user)],
) -> dict[str, Any]:
    row = db.get_request(request_id, user_id=current_user.id)
    if row is None:
        raise HTTPException(status_code=404, detail="Request not found")
    return row.to_dict()


# ---------------------------------------------------------------------------
# POST /v1/arbitrate — forced arbitration (auth-required)
# ---------------------------------------------------------------------------

@app.post("/v1/arbitrate")
def arbitrate(
    body: ArbitrateRequest,
    current_user: Annotated[UserRow, Depends(get_current_user)],
) -> dict[str, Any]:
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
        user_id=current_user.id,
        savings_final=True,
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


# ---------------------------------------------------------------------------
# GET /v1/stats — global admin stats (superuser only for now, open for dev)
# ---------------------------------------------------------------------------

@app.get("/v1/stats")
def stats(
    current_user: Annotated[UserRow, Depends(get_current_user)],
) -> dict[str, Any]:
    """System-wide aggregate statistics. Requires authentication."""
    return db.get_stats()


# ---------------------------------------------------------------------------
# Legacy session stats (kept for old frontend compat)
# ---------------------------------------------------------------------------

@app.get("/v1/session/{session_id}/stats")
def session_stats(
    session_id: str,
    current_user: Annotated[UserRow, Depends(get_current_user)],
) -> dict[str, Any]:
    """Per-session usage stats (legacy). New code should use GET /v1/me/stats."""
    return db.get_session_stats(session_id)
