"""Pydantic schemas for multi-critic arbitration."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Issue(BaseModel):
    quote: str = Field(description="Short quote or paraphrase from the candidate text")
    severity: Literal["low", "medium", "high"] = Field(
        description="How serious the issue is"
    )
    explanation: str = Field(description="Why this is a problem")


class CritiqueReport(BaseModel):
    dimension: Literal["accuracy", "logic", "completeness"]
    score: int = Field(ge=1, le=5, description="1=poor, 5=excellent on this dimension")
    issues: list[Issue] = Field(default_factory=list)
    self_confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Critic's confidence in its own assessment",
    )
    model_name: str = Field(
        default="",
        description="Registry model name that produced this critique",
    )


class Verdict(BaseModel):
    overall_score: int = Field(ge=1, le=10, description="1=bad, 10=excellent")
    confidence: float = Field(ge=0.0, le=1.0)
    confirmed_issues: list[Issue] = Field(default_factory=list)
    dismissed_flags: list[str] = Field(
        default_factory=list,
        description="Critic flags that were considered and rejected",
    )
    summary: str = Field(description="One-paragraph adjudication summary")
    should_escalate: bool = Field(
        default=False,
        description="True if the candidate should be regenerated on a stronger model",
    )
