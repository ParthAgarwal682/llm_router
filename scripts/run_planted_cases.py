"""Run the 4 planted portfolio test cases through arbitration and save JSON for screenshots.

Usage:
  # Local (no API server required):
  python scripts/run_planted_cases.py

  # Via running API:
  python scripts/run_planted_cases.py --api http://127.0.0.1:8000
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CASES_DIR = ROOT / "tests" / "test_cases"
OUT_DIR = ROOT / "data" / "planted_results"


def _run_local(case: dict) -> dict:
    from src.arbitration.graph import run_arbitration

    result = run_arbitration(case["prompt"], case["candidate_text"])
    verdict = result.get("verdict")
    return {
        "case_id": case["id"],
        "title": case["title"],
        "prompt": case["prompt"],
        "candidate_text": case["candidate_text"],
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


def _run_api(case: dict, api_base: str) -> dict:
    import urllib.request

    payload = json.dumps(
        {"prompt": case["prompt"], "text": case["candidate_text"]}
    ).encode()
    req = urllib.request.Request(
        f"{api_base.rstrip('/')}/v1/arbitrate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=300) as resp:
        body = json.loads(resp.read().decode())
    body["case_id"] = case["id"]
    body["title"] = case["title"]
    return body


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--api",
        default=None,
        help="If set, POST to {api}/v1/arbitrate instead of local graph",
    )
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cases = sorted(CASES_DIR.glob("*.json"))
    if len(cases) < 4:
        raise SystemExit(f"Expected >=4 test cases in {CASES_DIR}, found {len(cases)}")

    index = []
    for path in cases:
        case = json.loads(path.read_text(encoding="utf-8"))
        print(f"\n=== {case['id']} — {case['title']} ===")
        if args.api:
            result = _run_api(case, args.api)
        else:
            result = _run_local(case)

        out_path = OUT_DIR / f"{case['id']}.json"
        out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

        verdict = result.get("verdict") or {}
        score = verdict.get("overall_score")
        n_issues = len(verdict.get("confirmed_issues") or [])
        print(f"overall_score={score} confirmed_issues={n_issues}")
        print(f"saved → {out_path}")
        index.append(
            {
                "id": case["id"],
                "title": case["title"],
                "overall_score": score,
                "confirmed_issues": n_issues,
                "result_file": str(out_path),
                "api_id": result.get("id"),
            }
        )

    index_path = OUT_DIR / "index.json"
    index_path.write_text(json.dumps(index, indent=2), encoding="utf-8")
    print(f"\nIndex → {index_path}")
    print("Screenshot tip: open each JSON or inspect via dashboard Verdict explorer.")


if __name__ == "__main__":
    main()
