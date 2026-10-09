"""Tests for cost/savings math — pure functions, no DB or API needed."""

from __future__ import annotations

import pytest

from src.storage.db import compute_savings


class TestComputeSavings:
    def test_positive_savings(self) -> None:
        """Normal case: cheap model costs less than GPT-4o baseline."""
        result = compute_savings(
            baseline_cost_usd=0.01,
            answer_cost=0.0001,
            verification_cost=0.0005,
        )
        assert result["cost_usd"] == pytest.approx(0.0006)
        assert result["net_saved"] == pytest.approx(0.0094)
        assert result["saved_percent"] == pytest.approx(94.0)

    def test_negative_savings_not_clamped(self) -> None:
        """When verification costs exceed the baseline, net_saved is negative."""
        result = compute_savings(
            baseline_cost_usd=0.001,
            answer_cost=0.0005,
            verification_cost=0.005,   # expensive arbitration
        )
        assert result["net_saved"] == pytest.approx(-0.0045)
        assert result["saved_percent"] == pytest.approx(-450.0)
        # cost_usd should still be correct
        assert result["cost_usd"] == pytest.approx(0.0055)

    def test_zero_baseline(self) -> None:
        """Zero baseline: saved_percent is None, net_saved is negative of costs."""
        result = compute_savings(
            baseline_cost_usd=0.0,
            answer_cost=0.001,
            verification_cost=0.0,
        )
        assert result["net_saved"] == pytest.approx(-0.001)
        assert result["saved_percent"] is None

    def test_zero_costs(self) -> None:
        """Forced arbitration: answer and verification cost 0 (edge case)."""
        result = compute_savings(
            baseline_cost_usd=0.005,
            answer_cost=0.0,
            verification_cost=0.0,
        )
        assert result["cost_usd"] == pytest.approx(0.0)
        assert result["net_saved"] == pytest.approx(0.005)
        assert result["saved_percent"] == pytest.approx(100.0)

    def test_all_zeros(self) -> None:
        result = compute_savings(
            baseline_cost_usd=0.0,
            answer_cost=0.0,
            verification_cost=0.0,
        )
        assert result["net_saved"] == pytest.approx(0.0)
        assert result["saved_percent"] is None

    def test_exact_breakeven(self) -> None:
        """When actual cost equals baseline exactly."""
        result = compute_savings(
            baseline_cost_usd=0.01,
            answer_cost=0.007,
            verification_cost=0.003,
        )
        assert result["net_saved"] == pytest.approx(0.0, abs=1e-10)
        assert result["saved_percent"] == pytest.approx(0.0, abs=1e-6)

    def test_escalated_request_high_verification(self) -> None:
        """Simulates an escalated request where arbitration added significant cost."""
        result = compute_savings(
            baseline_cost_usd=0.005,     # GPT-4o for a short prompt
            answer_cost=0.00001,          # llama_8b answer
            verification_cost=0.003,     # gpt4o reference + critics + adjudicator
        )
        assert result["net_saved"] == pytest.approx(0.00199)
        assert result["saved_percent"] > 0  # still positive, just barely
