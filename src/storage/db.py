"""SQLite audit log for routed requests and arbitration verdicts."""

from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = ROOT / "data" / "router.db"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def connect(db_path: Path = DEFAULT_DB_PATH) -> Iterator[sqlite3.Connection]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path: Path = DEFAULT_DB_PATH) -> None:
    with connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS requests (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                prompt TEXT NOT NULL,
                response_text TEXT,
                tier TEXT,
                model_used TEXT,
                model_id TEXT,
                cost_usd REAL NOT NULL DEFAULT 0,
                baseline_cost_usd REAL NOT NULL DEFAULT 0,
                latency_ms REAL,
                promoted_to_arbitration INTEGER NOT NULL DEFAULT 0,
                verify_verdict TEXT,
                verify_reason TEXT,
                verdict_json TEXT,
                status TEXT NOT NULL DEFAULT 'routed'
            )
            """
        )


@dataclass
class RequestRow:
    id: str
    created_at: str
    prompt: str
    response_text: str | None
    tier: str | None
    model_used: str | None
    model_id: str | None
    cost_usd: float
    baseline_cost_usd: float
    latency_ms: float | None
    promoted_to_arbitration: bool
    verify_verdict: str | None
    verify_reason: str | None
    verdict_json: str | None
    status: str

    def to_dict(self) -> dict[str, Any]:
        verdict = None
        if self.verdict_json:
            try:
                verdict = json.loads(self.verdict_json)
            except json.JSONDecodeError:
                verdict = {"raw": self.verdict_json}
        return {
            "id": self.id,
            "created_at": self.created_at,
            "prompt": self.prompt,
            "response_text": self.response_text,
            "tier": self.tier,
            "model_used": self.model_used,
            "model_id": self.model_id,
            "cost_usd": self.cost_usd,
            "baseline_cost_usd": self.baseline_cost_usd,
            "latency_ms": self.latency_ms,
            "promoted_to_arbitration": self.promoted_to_arbitration,
            "verify_verdict": self.verify_verdict,
            "verify_reason": self.verify_reason,
            "verdict": verdict,
            "status": self.status,
        }


def _row_to_request(row: sqlite3.Row) -> RequestRow:
    return RequestRow(
        id=row["id"],
        created_at=row["created_at"],
        prompt=row["prompt"],
        response_text=row["response_text"],
        tier=row["tier"],
        model_used=row["model_used"],
        model_id=row["model_id"],
        cost_usd=float(row["cost_usd"] or 0),
        baseline_cost_usd=float(row["baseline_cost_usd"] or 0),
        latency_ms=row["latency_ms"],
        promoted_to_arbitration=bool(row["promoted_to_arbitration"]),
        verify_verdict=row["verify_verdict"],
        verify_reason=row["verify_reason"],
        verdict_json=row["verdict_json"],
        status=row["status"],
    )


def create_request(
    *,
    prompt: str,
    response_text: str,
    tier: str,
    model_used: str,
    model_id: str,
    cost_usd: float,
    baseline_cost_usd: float,
    latency_ms: float,
    status: str = "routed",
    promoted_to_arbitration: bool = False,
    verify_verdict: str | None = None,
    verify_reason: str | None = None,
    verdict_json: str | None = None,
    db_path: Path = DEFAULT_DB_PATH,
) -> str:
    init_db(db_path)
    request_id = str(uuid.uuid4())
    with connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO requests (
                id, created_at, prompt, response_text, tier, model_used, model_id,
                cost_usd, baseline_cost_usd, latency_ms, promoted_to_arbitration,
                verify_verdict, verify_reason, verdict_json, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                request_id,
                _utc_now(),
                prompt,
                response_text,
                tier,
                model_used,
                model_id,
                cost_usd,
                baseline_cost_usd,
                latency_ms,
                int(promoted_to_arbitration),
                verify_verdict,
                verify_reason,
                verdict_json,
                status,
            ),
        )
    return request_id


def update_request(request_id: str, db_path: Path = DEFAULT_DB_PATH, **fields: Any) -> None:
    if not fields:
        return
    allowed = {
        "response_text",
        "cost_usd",
        "baseline_cost_usd",
        "latency_ms",
        "promoted_to_arbitration",
        "verify_verdict",
        "verify_reason",
        "verdict_json",
        "status",
    }
    unknown = set(fields) - allowed
    if unknown:
        raise ValueError(f"Cannot update fields: {sorted(unknown)}")

    cols = []
    values: list[Any] = []
    for key, value in fields.items():
        if key == "promoted_to_arbitration":
            value = int(bool(value))
        cols.append(f"{key} = ?")
        values.append(value)
    values.append(request_id)

    with connect(db_path) as conn:
        conn.execute(
            f"UPDATE requests SET {', '.join(cols)} WHERE id = ?",
            values,
        )


def get_request(request_id: str, db_path: Path = DEFAULT_DB_PATH) -> RequestRow | None:
    init_db(db_path)
    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM requests WHERE id = ?",
            (request_id,),
        ).fetchone()
    return _row_to_request(row) if row else None


def list_requests(
    *,
    limit: int = 100,
    arbitrations_only: bool = False,
    db_path: Path = DEFAULT_DB_PATH,
) -> list[RequestRow]:
    init_db(db_path)
    query = "SELECT * FROM requests"
    if arbitrations_only:
        query += " WHERE promoted_to_arbitration = 1 OR verdict_json IS NOT NULL"
    query += " ORDER BY created_at DESC LIMIT ?"
    with connect(db_path) as conn:
        rows = conn.execute(query, (limit,)).fetchall()
    return [_row_to_request(r) for r in rows]


def get_stats(db_path: Path = DEFAULT_DB_PATH) -> dict[str, Any]:
    init_db(db_path)
    with connect(db_path) as conn:
        totals = conn.execute(
            """
            SELECT
                COUNT(*) AS total_requests,
                COALESCE(SUM(cost_usd), 0) AS total_cost_usd,
                COALESCE(SUM(baseline_cost_usd), 0) AS total_baseline_cost_usd,
                COALESCE(SUM(promoted_to_arbitration), 0) AS escalations,
                COALESCE(AVG(latency_ms), 0) AS avg_latency_ms
            FROM requests
            """
        ).fetchone()
        by_model = conn.execute(
            """
            SELECT model_used, COUNT(*) AS count, COALESCE(SUM(cost_usd), 0) AS cost_usd
            FROM requests
            WHERE model_used IS NOT NULL
            GROUP BY model_used
            ORDER BY count DESC
            """
        ).fetchall()
        by_tier = conn.execute(
            """
            SELECT tier, COUNT(*) AS count
            FROM requests
            WHERE tier IS NOT NULL
            GROUP BY tier
            ORDER BY count DESC
            """
        ).fetchall()

    total = int(totals["total_requests"] or 0)
    escalations = int(totals["escalations"] or 0)
    total_cost = float(totals["total_cost_usd"] or 0)
    baseline = float(totals["total_baseline_cost_usd"] or 0)
    return {
        "total_requests": total,
        "total_cost_usd": total_cost,
        "total_baseline_cost_usd": baseline,
        "cost_saved_usd": max(0.0, baseline - total_cost),
        "escalations": escalations,
        "escalation_rate": (escalations / total) if total else 0.0,
        "avg_latency_ms": float(totals["avg_latency_ms"] or 0),
        "model_distribution": [
            {"model": r["model_used"], "count": r["count"], "cost_usd": r["cost_usd"]}
            for r in by_model
        ],
        "tier_distribution": [
            {"tier": r["tier"], "count": r["count"]} for r in by_tier
        ],
    }
