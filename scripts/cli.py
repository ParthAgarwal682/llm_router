"""Unified CLI for testing prompts and retraining the complexity classifier.

Usage:
  # 1. Test a single prompt:
  python scripts/cli.py test "What is database sharding?"

  # 2. Test an interactive prompt loop:
  python scripts/cli.py interactive

  # 3. Test a quick batch of diverse prompts:
  python scripts/cli.py batch --limit 5

  # 4. Add a new labeled training sample:
  python scripts/cli.py add-sample --prompt "Design a zero-downtime database migration" --label complex

  # 5. Retrain the classifier:
  python scripts/cli.py train
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.models.registry import baseline_cost as calc_baseline_cost
from src.routing.classifier import classify_complexity
from src.routing.features import extract_features
from src.routing.router import route_and_call
from src.routing.train_classifier import train_and_save
from src.storage import db

DATA_CSV = ROOT / "data" / "labeled_prompts.csv"
DB_PATH = ROOT / "data" / "router.db"


def run_test_prompt(prompt: str, user_id: str = "cli-tester") -> None:
    print("\n" + "=" * 65)
    print(f"📝 PROMPT: {prompt}")
    print("=" * 65)

    # 1. Complexity Classification
    tier = classify_complexity(prompt)
    print(f"🎯 CLASSIFICATION: Tier = [{tier.upper()}]")

    # 2. Route & Call Model
    print("🚀 Routing to model via OpenRouter...")
    try:
        routed = route_and_call(prompt)
    except Exception as exc:
        print(f"❌ Error invoking model: {exc}")
        return

    resp = routed.response
    actual_cost = resp.cost_usd
    baseline = calc_baseline_cost(resp.input_tokens, resp.output_tokens)
    saved = baseline - actual_cost
    saved_pct = (saved / baseline * 100) if baseline > 0 else 0.0

    print(f"🤖 MODEL CHOSEN : {routed.model_name} ({routed.model_id})")
    print(f"⏱️ LATENCY      : {resp.latency_ms:.0f} ms")
    print(f"📊 TOKENS       : {resp.input_tokens} in / {resp.output_tokens} out")
    print(f"💵 ACTUAL COST  : ${actual_cost:.6f}")
    print(f"📈 GPT-4o BASE  : ${baseline:.6f}")
    print(f"💰 NET SAVED    : ${saved:.6f} ({saved_pct:.1f}% savings)")

    # 3. Save to Database so it appears in Streamlit & Web App
    try:
        req_id = db.create_request(
            prompt=prompt,
            response_text=resp.text,
            tier=routed.tier,
            model_used=routed.model_name,
            model_id=routed.model_id,
            cost_usd=actual_cost,
            baseline_cost_usd=baseline,
            latency_ms=resp.latency_ms,
            status="complete",
            user_id=user_id,
            net_saved=saved,
            saved_percent=saved_pct,
            savings_final=True,
            verify_verdict="agree",
            promoted_to_arbitration=False,
            db_path=DB_PATH,
        )
        print(f"💾 SAVED TO DB  : Request ID = {req_id[:8]}... (Logged to router.db)")
    except Exception as db_exc:
        print(f"⚠️ Warning: Could not log to DB: {db_exc}")

    print("\n💬 RESPONSE PREVIEW:")
    print("-" * 65)
    lines = resp.text.strip().split("\n")
    preview = "\n".join(lines[:8])
    if len(lines) > 8:
        preview += f"\n... [{len(lines) - 8} more lines]"
    print(preview)
    print("-" * 65 + "\n")


def run_interactive() -> None:
    print("⚡ LLM Router Interactive CLI (Type 'exit' or 'quit' to stop)\n")
    while True:
        try:
            prompt = input("Enter prompt > ").strip()
            if not prompt:
                continue
            if prompt.lower() in {"exit", "quit"}:
                print("Goodbye!")
                break
            run_test_prompt(prompt)
        except (KeyboardInterrupt, EOFError):
            print("\nExiting.")
            break


def run_batch(limit: int = 5) -> None:
    samples = [
        "What is the capital of Japan?",
        "Rewrite in formal tone: hey man can we talk tomorrow afternoon?",
        "Compare MySQL and MongoDB in a concise table with 3 pros and cons each.",
        "Write a Python function to reverse a linked list and explain time complexity.",
        "Analyze the system architecture of Apache Kafka vs AWS SQS for event streaming with partitioned ordering constraints.",
        "Design a multi-region active-active PostgreSQL replication topology handling split-brain scenarios.",
    ][:limit]

    print(f"\n🚀 Running batch test with {len(samples)} diverse prompts...\n")
    total_saved = 0.0
    total_actual = 0.0
    total_baseline = 0.0

    for i, p in enumerate(samples, 1):
        print(f"[{i}/{len(samples)}] Testing: {p[:55]}...")
        tier = classify_complexity(p)
        try:
            routed = route_and_call(p)
            resp = routed.response
            cost = resp.cost_usd
            base = calc_baseline_cost(resp.input_tokens, resp.output_tokens)
            diff = base - cost
            total_actual += cost
            total_baseline += base
            total_saved += diff

            print(
                f"   → Tier: {tier.upper():<8} | Model: {routed.model_name:<10} | Cost: ${cost:.5f} | Saved: ${diff:.5f}"
            )
        except Exception as e:
            print(f"   ❌ Failed: {e}")

    pct = (total_saved / total_baseline * 100) if total_baseline > 0 else 0.0
    print("\n" + "=" * 65)
    print("📊 BATCH RESULTS SUMMARY:")
    print(f"Total Router Cost: ${total_actual:.5f}")
    print(f"GPT-4o Baseline  : ${total_baseline:.5f}")
    print(f"Total Money Saved: ${total_saved:.5f} ({pct:.1f}% savings)")
    print("=" * 65 + "\n")


def add_training_sample(prompt: str, label: str) -> None:
    valid_labels = {"simple", "moderate", "complex"}
    label = label.lower().strip()
    if label not in valid_labels:
        print(f"❌ Invalid label '{label}'. Must be one of: {valid_labels}")
        return

    with open(DATA_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([prompt.strip(), label])

    print(f"✅ Added new training sample to {DATA_CSV}:")
    print(f"   Label : {label}")
    print(f"   Prompt: {prompt}")
    print("\n👉 Run 'python scripts/cli.py train' to update the classifier model!")


def main() -> None:
    parser = argparse.ArgumentParser(description="LLM Router Test & Training CLI")
    subparsers = parser.add_subparsers(dest="command")

    # test
    test_p = subparsers.add_parser("test", help="Test a single prompt")
    test_p.add_argument("prompt", type=str, help="Prompt text to test")

    # interactive
    subparsers.add_parser("interactive", help="Run interactive prompt loop")

    # batch
    batch_p = subparsers.add_parser("batch", help="Run quick batch test")
    batch_p.add_argument("--limit", type=int, default=5, help="Number of prompts to run")

    # add-sample
    add_p = subparsers.add_parser("add-sample", help="Add a labeled prompt to training set")
    add_p.add_argument("--prompt", required=True, type=str, help="Prompt text")
    add_p.add_argument("--label", required=True, choices=["simple", "moderate", "complex"], help="Label")

    # train
    subparsers.add_parser("train", help="Retrain complexity classifier")

    args = parser.parse_args()

    if args.command == "test":
        run_test_prompt(args.prompt)
    elif args.command == "interactive":
        run_interactive()
    elif args.command == "batch":
        run_batch(args.limit)
    elif args.command == "add-sample":
        add_training_sample(args.prompt, args.label)
    elif args.command == "train":
        print("🧠 Retraining complexity classifier on data/labeled_prompts.csv...")
        train_and_save()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
