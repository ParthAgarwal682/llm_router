"""Generate 500+ diverse prompts and run them through the router for cost savings.

Default mode is route-only (cheap, gives the headline cost-reduction number).
Use --full to also run verify (+ arbitrate on DISAGREE) — expensive on OpenRouter.

Examples:
  python scripts/run_batch_benchmark.py --limit 520
  python scripts/run_batch_benchmark.py --limit 50 --full
  python scripts/run_batch_benchmark.py --limit 520 --prompts-only
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.arbitration.graph import run_arbitration
from src.models.registry import baseline_cost as _baseline_cost
from src.routing.router import route_and_call
from src.storage import db
from src.verification.single_judge import verify_response

PROMPTS_PATH = ROOT / "data" / "batch_prompts.csv"
RESULTS_PATH = ROOT / "data" / "batch_results.json"
SUMMARY_PATH = ROOT / "data" / "batch_summary.json"
PROGRESS_PATH = ROOT / "data" / "batch_progress.jsonl"
BASELINE_MODEL = "gpt4o"

SIMPLE_TEMPLATES = [
    "What is the capital of {place}?",
    "Convert {n} miles to kilometers.",
    "What does {acronym} stand for?",
    "List three {things}.",
    "Translate '{word}' to Spanish.",
    "What is {pct}% of {n}?",
    "Give a one-sentence definition of {term}.",
    "Rewrite in past tense: {sentence}.",
    "Is {n} a prime number? Answer yes or no.",
    "Spell the number {n} in English.",
]

MODERATE_TEMPLATES = [
    "Summarize {topic} in three bullet points for a beginner.",
    "Compare {a} and {b} in a short markdown table.",
    "Explain how {concept} works step by step with a small example.",
    "Draft a polite email about {topic}.",
    "Outline pros and cons of {topic}.",
    "Write a short Python function related to {concept} with one test idea.",
    "Describe the difference between {a} and {b} with one example each.",
    "Create a simple weekly plan for {topic}.",
    "Explain {concept} in under 150 words.",
    "Turn this vague request into clearer acceptance criteria: {topic}.",
]

COMPLEX_TEMPLATES = [
    "Analyze tradeoffs between {a} and {b} for {context}; recommend one option with constraints.",
    "Design a fault-tolerant approach for {topic}: compare failure modes and monitoring metrics.",
    "Critique this claim and rewrite a stronger version: '{claim}'.",
    "Compare three strategies for {topic}; recommend one under cost, complexity, and risk constraints.",
    "Synthesize arguments for and against {topic}, steelman both sides, give a calibrated view.",
    "Given conflicting goals (speed, safety, cost), propose a phased plan for {topic}.",
    "Debug this situation: {topic} is failing under load — rank likely causes and experiments.",
    "Evaluate whether approach A or B is better for {topic}; include a decision matrix.",
    "Analyze ethical and technical constraints of {topic}; propose measurable safeguards.",
    "Construct a multi-step migration plan for {topic}, including cutover risks and success metrics.",
]

PLACES = [
    "France", "Japan", "Brazil", "Kenya", "Canada", "India", "Egypt", "Sweden",
    "Australia", "Mexico", "Italy", "South Korea", "Argentina", "Poland", "Morocco",
]
ACRONYMS = ["HTTP", "SQL", "GPU", "API", "CPU", "DNS", "TLS", "JSON", "HTML", "CSS"]
THINGS = ["primary colors", "noble gases", "programming paradigms", "cloud providers", "data structures"]
WORDS = ["hello", "thank you", "library", "network", "freedom", "tomorrow", "engineer"]
TERMS = ["photosynthesis", "entropy", "latency", "cache", "recursion", "inflation", "bandwidth"]
SENTENCES = [
    "I walk to school every day",
    "They build reliable software",
    "She reads research papers at night",
]
TOPICS = [
    "remote work", "photosynthesis", "OAuth login", "binary search", "caching",
    "unit testing", "carbon pricing", "RAG chatbots", "database sharding",
    "incident response", "CI/CD pipelines", "password hashing", "load balancing",
    "feature flags", "rate limiting", "observability", "data retention",
]
PAIRS = [
    ("TCP", "UDP"), ("SQL", "NoSQL"), ("REST", "GraphQL"), ("monolith", "microservices"),
    ("carbon tax", "cap-and-trade"), ("fine-tuning", "RAG"), ("threads", "async"),
    ("vertical scaling", "horizontal scaling"), ("JWT", "session cookies"),
]
CONCEPTS = [
    "binary search", "hash maps", "consensus", "backpressure", "idempotency",
    "eventual consistency", "circuit breakers", "two-phase commit",
]
CLAIMS = [
    "AI will automate all customer support next year with zero humans.",
    "Bigger models are always better regardless of latency or cost.",
    "Microservices eliminate the need for careful API design.",
    "Caching removes the need for a correct data model.",
]
CONTEXTS = [
    "a developing country with weak institutions",
    "a multi-tenant SaaS with uneven customer size",
    "a bank shipping an LLM feature",
    "an e-commerce checkout path",
    "a public transit agency",
]

# _baseline_cost() is now imported from src.models.registry.baseline_cost as _baseline_cost


def generate_prompts(n: int = 520, seed: int = 42) -> list[dict[str, str]]:
    rng = random.Random(seed)
    rows: list[dict[str, str]] = []

    while len(rows) < n:
        bucket = len(rows) % 3
        if bucket == 0:
            tmpl = rng.choice(SIMPLE_TEMPLATES)
            prompt = tmpl.format(
                place=rng.choice(PLACES),
                n=rng.randint(2, 99),
                acronym=rng.choice(ACRONYMS),
                things=rng.choice(THINGS),
                word=rng.choice(WORDS),
                pct=rng.choice([5, 10, 12, 15, 20, 25]),
                term=rng.choice(TERMS),
                sentence=rng.choice(SENTENCES),
            )
            label = "simple"
        elif bucket == 1:
            tmpl = rng.choice(MODERATE_TEMPLATES)
            a, b = rng.choice(PAIRS)
            prompt = tmpl.format(
                topic=rng.choice(TOPICS),
                a=a,
                b=b,
                concept=rng.choice(CONCEPTS),
            )
            label = "moderate"
        else:
            tmpl = rng.choice(COMPLEX_TEMPLATES)
            a, b = rng.choice(PAIRS)
            prompt = tmpl.format(
                a=a,
                b=b,
                context=rng.choice(CONTEXTS),
                topic=rng.choice(TOPICS),
                claim=rng.choice(CLAIMS),
            )
            label = "complex"
        rows.append({"prompt": prompt, "expected_tier": label})

    return rows[:n]


def write_prompts_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["prompt", "expected_tier"])
        writer.writeheader()
        writer.writerows(rows)


def load_prompts_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _load_progress() -> list[dict]:
    if not PROGRESS_PATH.exists():
        return []
    rows: list[dict] = []
    with PROGRESS_PATH.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def _append_progress(entry: dict) -> None:
    PROGRESS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with PROGRESS_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
        f.flush()


def _seed_progress_from_db(prompt_set: set[str]) -> int:
    """Recover completed prompts from SQLite if progress.jsonl is empty/partial."""
    existing = {r["prompt"] for r in _load_progress() if "prompt" in r and "error" not in r}
    db.init_db()
    seeded = 0
    for row in db.list_requests(limit=10_000):
        if row.prompt not in prompt_set or row.prompt in existing:
            continue
        if row.status and str(row.status).startswith("error"):
            continue
        entry = {
            "id": row.id,
            "prompt": row.prompt,
            "tier": row.tier,
            "model_used": row.model_used,
            "cost_usd": row.cost_usd,
            "baseline_cost_usd": row.baseline_cost_usd,
            "latency_ms": row.latency_ms,
            "promoted_to_arbitration": row.promoted_to_arbitration,
            "verify_verdict": row.verify_verdict,
            "seeded_from_db": True,
        }
        _append_progress(entry)
        existing.add(row.prompt)
        seeded += 1
    return seeded


def _summarize(results: list[dict], *, full: bool, elapsed: float) -> dict:
    ok = [r for r in results if "error" not in r]
    errors = [r for r in results if "error" in r]
    total_cost = sum(float(r.get("cost_usd") or 0) for r in ok)
    total_baseline = sum(float(r.get("baseline_cost_usd") or 0) for r in ok)
    escalations = sum(1 for r in ok if r.get("promoted_to_arbitration"))
    saved = max(0.0, total_baseline - total_cost)
    reduction_pct = (saved / total_baseline * 100.0) if total_baseline else 0.0
    summary = {
        "n_prompts": len(results),
        "n_success": len(ok),
        "n_errors": len(errors),
        "mode": "full" if full else "route_only",
        "total_cost_usd": total_cost,
        "total_baseline_cost_usd": total_baseline,
        "cost_saved_usd": saved,
        "cost_reduction_pct": reduction_pct,
        "escalations": escalations,
        "escalation_rate": (escalations / len(ok)) if ok else 0.0,
        "elapsed_sec": elapsed,
        "baseline_model": BASELINE_MODEL,
        "results_path": str(RESULTS_PATH),
        "progress_path": str(PROGRESS_PATH),
    }
    RESULTS_PATH.write_text(json.dumps(results, indent=2), encoding="utf-8")
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def run_batch(
    rows: list[dict[str, str]],
    *,
    full: bool = False,
    max_tokens: int = 256,
    resume: bool = False,
) -> dict:
    db.init_db()
    started = time.time()

    if resume:
        seeded = _seed_progress_from_db({r["prompt"] for r in rows})
        if seeded:
            print(f"Seeded {seeded} completed prompts from SQLite into {PROGRESS_PATH}")

    results = _load_progress()
    done = {r["prompt"] for r in results if "prompt" in r}
    if resume and done:
        print(f"Resuming: {len(done)} already done, {len(rows) - len(done)} remaining")

    for i, row in enumerate(rows, start=1):
        prompt = row["prompt"]
        if prompt in done:
            continue

        print(f"[{i}/{len(rows)}] routing… ({row.get('expected_tier', '?')})", flush=True)
        try:
            routed = route_and_call(prompt, max_tokens=max_tokens)
            r = routed.response
            baseline = _baseline_cost(r.input_tokens, r.output_tokens)
            cost = r.cost_usd
            promoted = False
            verify_verdict = None
            verify_reason = None
            verdict_json = None
            status = "routed"

            request_id = db.create_request(
                prompt=prompt,
                response_text=r.text,
                tier=str(routed.tier),
                model_used=routed.model_name,
                model_id=routed.model_id,
                cost_usd=cost,
                baseline_cost_usd=baseline,
                latency_ms=r.latency_ms,
                status=status,
            )

            if full:
                verification = verify_response(prompt, r.text)
                cost += verification.total_cost_usd
                verify_verdict = verification.verdict
                verify_reason = verification.reason
                if verification.promote_to_arbitration:
                    promoted = True
                    arb = run_arbitration(prompt, r.text)
                    if arb.get("verdict"):
                        verdict_json = arb["verdict"].model_dump_json()
                    status = "complete"
                else:
                    status = "complete"
                db.update_request(
                    request_id,
                    cost_usd=cost,
                    promoted_to_arbitration=promoted,
                    verify_verdict=verify_verdict,
                    verify_reason=verify_reason,
                    verdict_json=verdict_json,
                    status=status,
                )

            entry = {
                "id": request_id,
                "prompt": prompt,
                "expected_tier": row.get("expected_tier"),
                "tier": str(routed.tier),
                "model_used": routed.model_name,
                "cost_usd": cost,
                "baseline_cost_usd": baseline,
                "latency_ms": r.latency_ms,
                "promoted_to_arbitration": promoted,
                "verify_verdict": verify_verdict,
            }
            results.append(entry)
            _append_progress(entry)
            done.add(prompt)
            print(
                f"  ok model={routed.model_name} cost=${cost:.6f} "
                f"latency={r.latency_ms:.0f}ms",
                flush=True,
            )
        except Exception as exc:  # noqa: BLE001
            entry = {"prompt": prompt, "error": str(exc)}
            results.append(entry)
            _append_progress(entry)
            print(f"  ERROR: {exc}", flush=True)

    return _summarize(results, full=full, elapsed=time.time() - started)


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch cost-savings benchmark")
    parser.add_argument("--limit", type=int, default=520, help="Number of prompts (default 520)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--prompts-only", action="store_true", help="Only write batch_prompts.csv")
    parser.add_argument(
        "--full",
        action="store_true",
        help="Also run verify (+ arbitrate on DISAGREE). Much more expensive.",
    )
    parser.add_argument("--max-tokens", type=int, default=256)
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip prompts already in batch_progress.jsonl / SQLite and continue",
    )
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="Delete progress checkpoint and start clean",
    )
    args = parser.parse_args()

    if args.fresh and PROGRESS_PATH.exists():
        PROGRESS_PATH.unlink()
        print(f"Cleared {PROGRESS_PATH}")

    rows = generate_prompts(args.limit, seed=args.seed)
    write_prompts_csv(PROMPTS_PATH, rows)
    print(f"Wrote {len(rows)} prompts → {PROMPTS_PATH}")
    if args.prompts_only:
        return

    summary = run_batch(
        rows,
        full=args.full,
        max_tokens=args.max_tokens,
        resume=args.resume,
    )
    print("\n===== BATCH SUMMARY =====")
    print(json.dumps(summary, indent=2))
    print(f"\nHeadline: {summary['cost_reduction_pct']:.1f}% cost reduction vs always-{BASELINE_MODEL}")
    print(f"Details: {SUMMARY_PATH}")


if __name__ == "__main__":
    main()
