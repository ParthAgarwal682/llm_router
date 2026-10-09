"""SQLite audit log for routed requests, arbitration verdicts, users, and conversations.

Schema design goals:
- All queries are Postgres-compatible (no SQLite-specific syntax).
- Migrations are idempotent (_add_column_if_missing / CREATE TABLE IF NOT EXISTS).
- Legacy rows (pre-auth) have user_id = NULL and are never returned by user-scoped queries.
- Three cost fields per request:
    answer_cost         — the routed LLM call only
    verification_cost   — strong model + judge + critics + adjudicator (updated in background)
    cost_usd            — answer_cost + verification_cost (backward-compat total)
    baseline_cost_usd   — what GPT-4o would have cost
    net_saved           — baseline_cost_usd - cost_usd (can be negative, never clamped)
    saved_percent       — net_saved / baseline_cost_usd * 100
    savings_final       — 0 while background task running, 1 when costs are final
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
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
    # WAL mode for better concurrent read performance
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _add_column_if_missing(conn: sqlite3.Connection, table: str, column: str, col_type: str) -> None:
    """Idempotent column addition — safe to call on an existing database."""
    existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")


def init_db(db_path: Path = DEFAULT_DB_PATH) -> None:
    with connect(db_path) as conn:
        # ---------------------------------------------------------------
        # Users
        # ---------------------------------------------------------------
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id                   TEXT PRIMARY KEY,
                email                TEXT UNIQUE NOT NULL,
                password_hash        TEXT NOT NULL,
                created_at           TEXT NOT NULL,
                updated_at           TEXT NOT NULL,
                is_active            INTEGER NOT NULL DEFAULT 1,
                is_superuser         INTEGER NOT NULL DEFAULT 0,
                daily_request_limit  INTEGER NOT NULL DEFAULT 100
            )
            """
        )

        # ---------------------------------------------------------------
        # Refresh tokens (for revocation)
        # ---------------------------------------------------------------
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS refresh_tokens (
                id          TEXT PRIMARY KEY,
                user_id     TEXT NOT NULL,
                expires_at  TEXT NOT NULL,
                revoked     INTEGER NOT NULL DEFAULT 0,
                created_at  TEXT NOT NULL
            )
            """
        )

        # ---------------------------------------------------------------
        # Core requests table (unchanged schema for backward compatibility)
        # ---------------------------------------------------------------
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS requests (
                id                      TEXT PRIMARY KEY,
                created_at              TEXT NOT NULL,
                prompt                  TEXT NOT NULL,
                response_text           TEXT,
                tier                    TEXT,
                model_used              TEXT,
                model_id                TEXT,
                cost_usd                REAL NOT NULL DEFAULT 0,
                baseline_cost_usd       REAL NOT NULL DEFAULT 0,
                latency_ms              REAL,
                promoted_to_arbitration INTEGER NOT NULL DEFAULT 0,
                verify_verdict          TEXT,
                verify_reason           TEXT,
                verdict_json            TEXT,
                status                  TEXT NOT NULL DEFAULT 'routed'
            )
            """
        )

        # ---------------------------------------------------------------
        # Conversations
        # ---------------------------------------------------------------
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                id          TEXT PRIMARY KEY,
                session_id  TEXT NOT NULL,
                title       TEXT NOT NULL,
                created_at  TEXT NOT NULL,
                updated_at  TEXT NOT NULL
            )
            """
        )

        # ---------------------------------------------------------------
        # Additive migrations — safe on existing databases
        # ---------------------------------------------------------------
        # Phase 1: auth columns
        _add_column_if_missing(conn, "requests", "conversation_id", "TEXT")
        _add_column_if_missing(conn, "requests", "session_id", "TEXT")
        _add_column_if_missing(conn, "requests", "user_id", "TEXT")          # NULL = legacy

        # Phase 2: accurate cost columns
        _add_column_if_missing(conn, "requests", "answer_cost", "REAL DEFAULT 0")
        _add_column_if_missing(conn, "requests", "verification_cost", "REAL DEFAULT 0")
        _add_column_if_missing(conn, "requests", "net_saved", "REAL")        # NULL = provisional
        _add_column_if_missing(conn, "requests", "saved_percent", "REAL")
        _add_column_if_missing(conn, "requests", "savings_final", "INTEGER DEFAULT 0")
        _add_column_if_missing(conn, "requests", "fallback_used", "INTEGER DEFAULT 0")
        _add_column_if_missing(conn, "requests", "fallback_from_model", "TEXT")

        # Phase 1: conversation user_id
        _add_column_if_missing(conn, "conversations", "user_id", "TEXT")     # NULL = legacy
        _add_column_if_missing(conn, "conversations", "deleted", "INTEGER DEFAULT 0")


# ---------------------------------------------------------------------------
# User CRUD
# ---------------------------------------------------------------------------

@dataclass
class UserRow:
    id: str
    email: str
    password_hash: str
    created_at: str
    updated_at: str
    is_active: bool
    is_superuser: bool
    daily_request_limit: int

    def to_public_dict(self) -> dict[str, Any]:
        """Safe public representation — never includes password_hash."""
        return {
            "id": self.id,
            "email": self.email,
            "created_at": self.created_at,
            "is_active": self.is_active,
            "daily_request_limit": self.daily_request_limit,
        }


def _row_to_user(row: sqlite3.Row) -> UserRow:
    return UserRow(
        id=row["id"],
        email=row["email"],
        password_hash=row["password_hash"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        is_active=bool(row["is_active"]),
        is_superuser=bool(row["is_superuser"]),
        daily_request_limit=int(row["daily_request_limit"]),
    )


def create_user(
    *,
    email: str,
    password_hash: str,
    daily_request_limit: int = 100,
    db_path: Path = DEFAULT_DB_PATH,
) -> UserRow:
    """Create a user. Raises sqlite3.IntegrityError if email already exists."""
    init_db(db_path)
    user_id = str(uuid.uuid4())
    now = _utc_now()
    with connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO users (id, email, password_hash, created_at, updated_at, daily_request_limit)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, email.lower().strip(), password_hash, now, now, daily_request_limit),
        )
    return UserRow(
        id=user_id,
        email=email.lower().strip(),
        password_hash=password_hash,
        created_at=now,
        updated_at=now,
        is_active=True,
        is_superuser=False,
        daily_request_limit=daily_request_limit,
    )


def get_user_by_email(email: str, db_path: Path = DEFAULT_DB_PATH) -> UserRow | None:
    init_db(db_path)
    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE email = ?", (email.lower().strip(),)
        ).fetchone()
    return _row_to_user(row) if row else None


def get_user_by_id(user_id: str, db_path: Path = DEFAULT_DB_PATH) -> UserRow | None:
    init_db(db_path)
    with connect(db_path) as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return _row_to_user(row) if row else None


def count_user_requests_today(user_id: str, db_path: Path = DEFAULT_DB_PATH) -> int:
    """Count requests made by this user since UTC midnight today."""
    today = datetime.now(timezone.utc).date().isoformat()  # YYYY-MM-DD
    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS cnt FROM requests WHERE user_id = ? AND created_at >= ?",
            (user_id, today),
        ).fetchone()
    return int(row["cnt"]) if row else 0


# ---------------------------------------------------------------------------
# Refresh token CRUD
# ---------------------------------------------------------------------------

def store_refresh_token(
    *,
    jti: str,
    user_id: str,
    expires_at: str,
    db_path: Path = DEFAULT_DB_PATH,
) -> None:
    init_db(db_path)
    with connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO refresh_tokens (id, user_id, expires_at, revoked, created_at)
            VALUES (?, ?, ?, 0, ?)
            """,
            (jti, user_id, expires_at, _utc_now()),
        )


def get_refresh_token(jti: str, db_path: Path = DEFAULT_DB_PATH) -> dict | None:
    init_db(db_path)
    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM refresh_tokens WHERE id = ?", (jti,)
        ).fetchone()
    return dict(row) if row else None


def revoke_refresh_token(jti: str, db_path: Path = DEFAULT_DB_PATH) -> None:
    with connect(db_path) as conn:
        conn.execute("UPDATE refresh_tokens SET revoked = 1 WHERE id = ?", (jti,))


def revoke_all_user_refresh_tokens(user_id: str, db_path: Path = DEFAULT_DB_PATH) -> None:
    with connect(db_path) as conn:
        conn.execute(
            "UPDATE refresh_tokens SET revoked = 1 WHERE user_id = ?", (user_id,)
        )


# ---------------------------------------------------------------------------
# Request CRUD
# ---------------------------------------------------------------------------

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
    conversation_id: str | None = None
    session_id: str | None = None
    user_id: str | None = None
    # New cost fields (Phase 2)
    answer_cost: float = 0.0
    verification_cost: float = 0.0
    net_saved: float | None = None       # None = provisional
    saved_percent: float | None = None
    savings_final: bool = False
    fallback_used: bool = False
    fallback_from_model: str | None = None

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
            "answer_cost": self.answer_cost,
            "verification_cost": self.verification_cost,
            "net_saved": self.net_saved,
            "saved_percent": self.saved_percent,
            "savings_final": self.savings_final,
            "latency_ms": self.latency_ms,
            "promoted_to_arbitration": self.promoted_to_arbitration,
            "verify_verdict": self.verify_verdict,
            "verify_reason": self.verify_reason,
            "verdict": verdict,
            "status": self.status,
            "conversation_id": self.conversation_id,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "fallback_used": self.fallback_used,
            "fallback_from_model": self.fallback_from_model,
        }


def _row_to_request(row: sqlite3.Row) -> RequestRow:
    keys = set(row.keys())

    def _get(k: str, default: Any = None) -> Any:
        return row[k] if k in keys else default

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
        conversation_id=_get("conversation_id"),
        session_id=_get("session_id"),
        user_id=_get("user_id"),
        answer_cost=float(_get("answer_cost") or 0),
        verification_cost=float(_get("verification_cost") or 0),
        net_saved=_get("net_saved"),          # may be None (provisional)
        saved_percent=_get("saved_percent"),
        savings_final=bool(_get("savings_final", 0)),
        fallback_used=bool(_get("fallback_used", 0)),
        fallback_from_model=_get("fallback_from_model"),
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
    conversation_id: str | None = None,
    session_id: str | None = None,
    user_id: str | None = None,
    answer_cost: float = 0.0,
    verification_cost: float = 0.0,
    net_saved: float | None = None,
    saved_percent: float | None = None,
    savings_final: bool = False,
    fallback_used: bool = False,
    fallback_from_model: str | None = None,
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
                verify_verdict, verify_reason, verdict_json, status,
                conversation_id, session_id, user_id,
                answer_cost, verification_cost, net_saved, saved_percent, savings_final,
                fallback_used, fallback_from_model
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                conversation_id,
                session_id,
                user_id,
                answer_cost,
                verification_cost,
                net_saved,
                saved_percent,
                savings_final,
                int(fallback_used),
                fallback_from_model,
            ),
        )
    return request_id


_UPDATABLE_FIELDS = {
    "response_text",
    "cost_usd",
    "baseline_cost_usd",
    "latency_ms",
    "promoted_to_arbitration",
    "verify_verdict",
    "verify_reason",
    "verdict_json",
    "status",
    "answer_cost",
    "verification_cost",
    "net_saved",
    "saved_percent",
    "savings_final",
    "fallback_used",
    "fallback_from_model",
}


def update_request(request_id: str, db_path: Path = DEFAULT_DB_PATH, **fields: Any) -> None:
    if not fields:
        return
    unknown = set(fields) - _UPDATABLE_FIELDS
    if unknown:
        raise ValueError(f"Cannot update fields: {sorted(unknown)}")

    cols = []
    values: list[Any] = []
    for key, value in fields.items():
        if key in ("promoted_to_arbitration", "savings_final", "fallback_used"):
            value = int(bool(value))
        cols.append(f"{key} = ?")
        values.append(value)
    values.append(request_id)

    with connect(db_path) as conn:
        conn.execute(
            f"UPDATE requests SET {', '.join(cols)} WHERE id = ?",
            values,
        )


def get_request(
    request_id: str,
    *,
    user_id: str | None = None,
    db_path: Path = DEFAULT_DB_PATH,
) -> RequestRow | None:
    """Return the request row.

    If user_id is provided, enforces user ownership — returns None (not 403)
    if the row belongs to a different user. Legacy rows (user_id=NULL) are only
    visible when user_id is None (admin use).
    """
    init_db(db_path)
    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM requests WHERE id = ?",
            (request_id,),
        ).fetchone()
    if row is None:
        return None
    result = _row_to_request(row)
    if user_id is not None and result.user_id != user_id:
        return None  # return 404, not 403 — don't reveal existence
    return result


def list_requests(
    *,
    limit: int = 100,
    arbitrations_only: bool = False,
    user_id: str | None = None,
    db_path: Path = DEFAULT_DB_PATH,
) -> list[RequestRow]:
    init_db(db_path)
    where_clauses = []
    params: list[Any] = []

    if user_id is not None:
        where_clauses.append("user_id = ?")
        params.append(user_id)

    if arbitrations_only:
        where_clauses.append("(promoted_to_arbitration = 1 OR verdict_json IS NOT NULL)")

    query = "SELECT * FROM requests"
    if where_clauses:
        query += " WHERE " + " AND ".join(where_clauses)
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)

    with connect(db_path) as conn:
        rows = conn.execute(query, params).fetchall()
    return [_row_to_request(r) for r in rows]


# ---------------------------------------------------------------------------
# Cost & savings helpers (pure — testable without DB)
# ---------------------------------------------------------------------------

def compute_savings(
    *,
    baseline_cost_usd: float,
    answer_cost: float,
    verification_cost: float,
) -> dict[str, float | None]:
    """Compute net_saved and saved_percent.

    net_saved CAN be negative (when verification/arbitration costs more than
    the baseline model would have). Never clamped.

    Returns dict with keys: cost_usd, net_saved, saved_percent.
    """
    cost_usd = answer_cost + verification_cost
    net_saved = baseline_cost_usd - cost_usd
    saved_percent: float | None = None
    if baseline_cost_usd > 0:
        saved_percent = (net_saved / baseline_cost_usd) * 100.0
    return {
        "cost_usd": cost_usd,
        "net_saved": net_saved,
        "saved_percent": saved_percent,
    }


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

def get_stats(db_path: Path = DEFAULT_DB_PATH) -> dict[str, Any]:
    """System-wide aggregate statistics across all sessions (admin view)."""
    init_db(db_path)
    with connect(db_path) as conn:
        totals = conn.execute(
            """
            SELECT
                COUNT(*) AS total_requests,
                COALESCE(SUM(cost_usd), 0) AS total_cost_usd,
                COALESCE(SUM(baseline_cost_usd), 0) AS total_baseline_cost_usd,
                COALESCE(SUM(promoted_to_arbitration), 0) AS escalations,
                COALESCE(AVG(latency_ms), 0) AS avg_latency_ms,
                COALESCE(SUM(net_saved), 0) AS total_net_saved
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
    net_saved = float(totals["total_net_saved"] or 0)
    return {
        "total_requests": total,
        "total_cost_usd": total_cost,
        "total_baseline_cost_usd": baseline,
        # Legacy field kept for backward compat; now uses net_saved when available
        "cost_saved_usd": max(0.0, baseline - total_cost),
        "total_net_saved": net_saved,
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


def get_user_stats(
    user_id: str,
    *,
    days: int | None = None,
    db_path: Path = DEFAULT_DB_PATH,
) -> dict[str, Any]:
    """Per-user usage and cost savings.

    days=None means all time, days=7 means last 7 days, etc.
    """
    init_db(db_path)
    params: list[Any] = [user_id]
    date_filter = ""
    if days is not None:
        from datetime import timedelta
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        date_filter = " AND created_at >= ?"
        params.append(cutoff)

    with connect(db_path) as conn:
        totals = conn.execute(
            f"""
            SELECT
                COUNT(*) AS total_requests,
                COALESCE(SUM(cost_usd), 0) AS total_cost_usd,
                COALESCE(SUM(baseline_cost_usd), 0) AS total_baseline_cost_usd,
                COALESCE(SUM(answer_cost), 0) AS total_answer_cost,
                COALESCE(SUM(verification_cost), 0) AS total_verification_cost,
                COALESCE(SUM(net_saved), 0) AS total_net_saved,
                COALESCE(SUM(promoted_to_arbitration), 0) AS escalations,
                COALESCE(AVG(latency_ms), 0) AS avg_latency_ms
            FROM requests
            WHERE user_id = ?{date_filter}
            """,
            params,
        ).fetchone()

        by_model = conn.execute(
            f"""
            SELECT model_used, COUNT(*) AS count, COALESCE(SUM(cost_usd), 0) AS cost_usd,
                   COALESCE(SUM(net_saved), 0) AS net_saved
            FROM requests
            WHERE user_id = ?{date_filter} AND model_used IS NOT NULL
            GROUP BY model_used
            ORDER BY count DESC
            """,
            params,
        ).fetchall()

        by_tier = conn.execute(
            f"""
            SELECT tier, COUNT(*) AS count
            FROM requests
            WHERE user_id = ?{date_filter} AND tier IS NOT NULL
            GROUP BY tier
            ORDER BY count DESC
            """,
            params,
        ).fetchall()

        # Daily time series — group by date prefix of created_at (ISO format)
        daily = conn.execute(
            f"""
            SELECT
                substr(created_at, 1, 10) AS date,
                COALESCE(SUM(net_saved), 0) AS net_saved,
                COALESCE(SUM(cost_usd), 0) AS actual_cost,
                COALESCE(SUM(baseline_cost_usd), 0) AS baseline_cost
            FROM requests
            WHERE user_id = ?{date_filter}
            GROUP BY substr(created_at, 1, 10)
            ORDER BY date ASC
            """,
            params,
        ).fetchall()

    total = int(totals["total_requests"] or 0)
    escalations = int(totals["escalations"] or 0)
    total_cost = float(totals["total_cost_usd"] or 0)
    baseline = float(totals["total_baseline_cost_usd"] or 0)
    net_saved = float(totals["total_net_saved"] or 0)
    saved_pct = (net_saved / baseline * 100.0) if baseline > 0 else 0.0

    return {
        "user_id": user_id,
        "total_requests": total,
        "total_actual_cost": total_cost,
        "total_baseline_cost": baseline,
        "total_net_saved": net_saved,
        "saved_percent": saved_pct,
        "escalations": escalations,
        "escalation_rate": (escalations / total) if total else 0.0,
        "avg_latency_ms": float(totals["avg_latency_ms"] or 0),
        "daily_series": [
            {
                "date": r["date"],
                "net_saved": float(r["net_saved"]),
                "actual_cost": float(r["actual_cost"]),
                "baseline_cost": float(r["baseline_cost"]),
            }
            for r in daily
        ],
        "by_model": [
            {
                "model": r["model_used"],
                "count": r["count"],
                "cost_usd": float(r["cost_usd"]),
                "net_saved": float(r["net_saved"]),
            }
            for r in by_model
        ],
        "by_tier": [
            {"tier": r["tier"], "count": r["count"]} for r in by_tier
        ],
    }


def get_session_stats(session_id: str, db_path: Path = DEFAULT_DB_PATH) -> dict[str, Any]:
    """Return cost and usage metrics scoped to a single browser session."""
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
            WHERE session_id = ?
            """,
            (session_id,),
        ).fetchone()
        by_model = conn.execute(
            """
            SELECT model_used, COUNT(*) AS count, COALESCE(SUM(cost_usd), 0) AS cost_usd
            FROM requests
            WHERE session_id = ? AND model_used IS NOT NULL
            GROUP BY model_used
            ORDER BY count DESC
            """,
            (session_id,),
        ).fetchall()
        by_tier = conn.execute(
            """
            SELECT tier, COUNT(*) AS count
            FROM requests
            WHERE session_id = ? AND tier IS NOT NULL
            GROUP BY tier
            ORDER BY count DESC
            """,
            (session_id,),
        ).fetchall()

    total = int(totals["total_requests"] or 0)
    escalations = int(totals["escalations"] or 0)
    total_cost = float(totals["total_cost_usd"] or 0)
    baseline = float(totals["total_baseline_cost_usd"] or 0)
    saved = baseline - total_cost
    return {
        "session_id": session_id,
        "total_requests": total,
        "total_cost_usd": total_cost,
        "total_baseline_cost_usd": baseline,
        "cost_saved_usd": max(0.0, saved),
        "cost_reduction_pct": (saved / baseline * 100.0) if baseline else 0.0,
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


# ---------------------------------------------------------------------------
# Conversations
# ---------------------------------------------------------------------------

def create_conversation(
    session_id: str,
    title: str,
    *,
    user_id: str | None = None,
    db_path: Path = DEFAULT_DB_PATH,
) -> str:
    """Create a new conversation; returns its UUID."""
    init_db(db_path)
    conv_id = str(uuid.uuid4())
    now = _utc_now()
    with connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO conversations (id, session_id, title, created_at, updated_at, user_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (conv_id, session_id, title, now, now, user_id),
        )
    return conv_id


def list_conversations(
    session_id: str,
    limit: int = 50,
    *,
    user_id: str | None = None,
    db_path: Path = DEFAULT_DB_PATH,
) -> list[dict]:
    """Return recent conversations for a session, newest first."""
    init_db(db_path)
    where = "session_id = ? AND (deleted IS NULL OR deleted = 0)"
    params: list[Any] = [session_id]
    if user_id is not None:
        where += " AND user_id = ?"
        params.append(user_id)
    with connect(db_path) as conn:
        rows = conn.execute(
            f"SELECT * FROM conversations WHERE {where} ORDER BY updated_at DESC LIMIT ?",
            params + [limit],
        ).fetchall()
    return [dict(r) for r in rows]


def get_conversation(
    conversation_id: str,
    *,
    user_id: str | None = None,
    db_path: Path = DEFAULT_DB_PATH,
) -> dict | None:
    """Fetch a single conversation. Returns None if not found or wrong user."""
    init_db(db_path)
    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM conversations WHERE id = ?", (conversation_id,)
        ).fetchone()
    if row is None:
        return None
    d = dict(row)
    if user_id is not None and d.get("user_id") != user_id:
        return None  # 404, not 403
    return d


def update_conversation_title(
    conversation_id: str,
    title: str,
    *,
    user_id: str | None = None,
    db_path: Path = DEFAULT_DB_PATH,
) -> bool:
    """Rename a conversation. Returns False if not found / wrong user."""
    conv = get_conversation(conversation_id, user_id=user_id, db_path=db_path)
    if conv is None:
        return False
    with connect(db_path) as conn:
        conn.execute(
            "UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?",
            (title, _utc_now(), conversation_id),
        )
    return True


def delete_conversation(
    conversation_id: str,
    *,
    user_id: str | None = None,
    db_path: Path = DEFAULT_DB_PATH,
) -> bool:
    """Soft-delete a conversation. Returns False if not found / wrong user."""
    conv = get_conversation(conversation_id, user_id=user_id, db_path=db_path)
    if conv is None:
        return False
    with connect(db_path) as conn:
        conn.execute(
            "UPDATE conversations SET deleted = 1, updated_at = ? WHERE id = ?",
            (_utc_now(), conversation_id),
        )
    return True


def touch_conversation(conversation_id: str, db_path: Path = DEFAULT_DB_PATH) -> None:
    """Update the updated_at timestamp on a conversation."""
    with connect(db_path) as conn:
        conn.execute(
            "UPDATE conversations SET updated_at = ? WHERE id = ?",
            (_utc_now(), conversation_id),
        )


def get_conversation_messages(
    conversation_id: str,
    *,
    user_id: str | None = None,
    db_path: Path = DEFAULT_DB_PATH,
) -> list[dict]:
    """Return all request rows belonging to a conversation, oldest first.

    If user_id is provided, checks ownership of the conversation first.
    """
    init_db(db_path)
    # Verify ownership
    if user_id is not None:
        conv = get_conversation(conversation_id, user_id=user_id, db_path=db_path)
        if conv is None:
            return []  # 404 at router level
    with connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM requests WHERE conversation_id = ? ORDER BY created_at ASC",
            (conversation_id,),
        ).fetchall()
    return [_row_to_request(r).to_dict() for r in rows]
