"""LangGraph multi-critic arbitration: parallel critics → disagreements → adjudicator.

Fan-out/fan-in uses LangGraph 1.2.x fixed parallel edges (verified against docs):
  START → accuracy / logic / completeness (same superstep)
  each critic → detect_disagreements (fan-in)
  detect_disagreements → adjudicate → END
Each critic writes a distinct state key, so no reducer is required.
"""

from __future__ import annotations

import re
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from src.arbitration.adjudicator import adjudicate
from src.arbitration.critics import accuracy_critic, completeness_critic, logic_critic
from src.arbitration.schemas import CritiqueReport, Issue, Verdict


class ArbitrationState(TypedDict):
    prompt: str
    candidate_text: str
    accuracy_report: CritiqueReport | None
    logic_report: CritiqueReport | None
    completeness_report: CritiqueReport | None
    disagreements: list[str]
    verdict: Verdict | None


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def _issue_key(issue: Issue) -> str:
    return _normalize(f"{issue.quote} {issue.explanation}")[:160]


def detect_disagreements(
    accuracy: CritiqueReport,
    logic: CritiqueReport,
    completeness: CritiqueReport,
) -> list[str]:
    """Flag score spreads of 2+ and issues found by only one critic."""
    reports = [accuracy, logic, completeness]
    disagreements: list[str] = []

    scores = [r.score for r in reports]
    if max(scores) - min(scores) >= 2:
        score_bits = ", ".join(f"{r.dimension}={r.score}" for r in reports)
        disagreements.append(f"Score divergence >= 2 ({score_bits})")

    ownership: dict[str, list[str]] = {}
    for report in reports:
        for issue in report.issues:
            ownership.setdefault(_issue_key(issue), []).append(report.dimension)

    for key, dims in ownership.items():
        unique_dims = sorted(set(dims))
        if len(unique_dims) == 1:
            disagreements.append(
                f"Issue only flagged by {unique_dims[0]} critic: {key[:120]}"
            )

    return disagreements


def _accuracy_node(state: ArbitrationState) -> dict:
    report = accuracy_critic(state["prompt"], state["candidate_text"])
    return {"accuracy_report": report}


def _logic_node(state: ArbitrationState) -> dict:
    report = logic_critic(state["prompt"], state["candidate_text"])
    return {"logic_report": report}


def _completeness_node(state: ArbitrationState) -> dict:
    report = completeness_critic(state["prompt"], state["candidate_text"])
    return {"completeness_report": report}


def _detect_node(state: ArbitrationState) -> dict:
    accuracy = state["accuracy_report"]
    logic = state["logic_report"]
    completeness = state["completeness_report"]
    assert accuracy and logic and completeness
    return {
        "disagreements": detect_disagreements(accuracy, logic, completeness),
    }


def _adjudicate_node(state: ArbitrationState) -> dict:
    accuracy = state["accuracy_report"]
    logic = state["logic_report"]
    completeness = state["completeness_report"]
    assert accuracy and logic and completeness
    verdict = adjudicate(
        state["prompt"],
        state["candidate_text"],
        [accuracy, logic, completeness],
        state.get("disagreements") or [],
    )
    return {"verdict": verdict}


def build_arbitration_graph():
    graph = StateGraph(ArbitrationState)
    graph.add_node("accuracy_critic", _accuracy_node)
    graph.add_node("logic_critic", _logic_node)
    graph.add_node("completeness_critic", _completeness_node)
    graph.add_node("detect_disagreements", _detect_node)
    graph.add_node("adjudicate", _adjudicate_node)

    # Fan-out to three critics in parallel
    graph.add_edge(START, "accuracy_critic")
    graph.add_edge(START, "logic_critic")
    graph.add_edge(START, "completeness_critic")

    # Fan-in
    graph.add_edge("accuracy_critic", "detect_disagreements")
    graph.add_edge("logic_critic", "detect_disagreements")
    graph.add_edge("completeness_critic", "detect_disagreements")

    graph.add_edge("detect_disagreements", "adjudicate")
    graph.add_edge("adjudicate", END)
    return graph.compile()


_COMPILED = None


def get_arbitration_graph():
    global _COMPILED
    if _COMPILED is None:
        _COMPILED = build_arbitration_graph()
    return _COMPILED


def run_arbitration(prompt: str, candidate_text: str) -> ArbitrationState:
    graph = get_arbitration_graph()
    return graph.invoke(
        {
            "prompt": prompt,
            "candidate_text": candidate_text,
            "accuracy_report": None,
            "logic_report": None,
            "completeness_report": None,
            "disagreements": [],
            "verdict": None,
        }
    )


if __name__ == "__main__":
    # Planted factually wrong + incomplete answer
    prompt = (
        "Name the capital of France and give one famous landmark there. "
        "Answer in exactly two short sentences."
    )
    bad_output = (
        "The capital of France is Berlin. "
        "It is known mainly for its beaches and tropical climate."
    )

    print("Running multi-critic arbitration on planted bad output...\n")
    result = run_arbitration(prompt, bad_output)
    verdict = result["verdict"]
    assert verdict is not None

    print("disagreements:")
    for d in result["disagreements"]:
        print(f"  - {d}")
    print()
    print(f"overall_score: {verdict.overall_score}/10")
    print(f"confidence: {verdict.confidence:.2f}")
    print(f"should_escalate: {verdict.should_escalate}")
    print(f"confirmed_issues ({len(verdict.confirmed_issues)}):")
    for issue in verdict.confirmed_issues:
        print(f"  [{issue.severity}] {issue.quote} — {issue.explanation}")
    print(f"dismissed_flags: {verdict.dismissed_flags}")
    print(f"summary: {verdict.summary}")
