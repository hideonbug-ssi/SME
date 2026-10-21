"""Unit tests for services/repayability.py — 100% business logic coverage."""
import math
import pytest

from services.repayability import assess_repayability, RepayabilityResult


class TestRepayabilityPass:
    def test_passes_when_cashflow_exceeds_repayment_with_headroom(self):
        # avg cashflow = 24,000; repayment = 15,000; ratio = 1.6 → 60% headroom (>20%) → passes
        result = assess_repayability([24000.0] * 6, 15000.0)
        assert result.passes is True

    def test_passes_exactly_at_120pct_headroom(self):
        # avg = 18,000; repayment = 15,000; ratio = 1.2 → exactly 20% headroom → passes
        result = assess_repayability([18000.0] * 6, 15000.0)
        assert result.passes is True

    def test_passes_when_repayment_is_zero(self):
        # Zero repayment → not a lending product → always passes
        result = assess_repayability([1000.0, 2000.0, 3000.0], 0.0)
        assert result.passes is True
        assert result.required_monthly_cashflow == 0.0
        assert result.headroom_ratio == float("inf")

    def test_passes_when_repayment_is_negative(self):
        # Negative repayment treated same as zero (not a lending product)
        result = assess_repayability([5000.0] * 6, -100.0)
        assert result.passes is True

    def test_passes_with_varying_cashflows_if_average_sufficient(self):
        # Mix of high and low months; average = 24,000
        cashflows = [10000.0, 20000.0, 30000.0, 40000.0, 20000.0, 24000.0]
        avg = sum(cashflows) / len(cashflows)  # 24,000
        result = assess_repayability(cashflows, 15000.0)
        assert result.passes is True
        assert abs(result.avg_monthly_cashflow - avg) < 0.01


class TestRepayabilityFail:
    def test_fails_when_cashflow_insufficient(self):
        # avg cashflow = 10,000; repayment = 15,000; ratio = 0.67 → fails
        result = assess_repayability([10000.0] * 6, 15000.0)
        assert result.passes is False

    def test_fails_when_no_cashflow_data(self):
        result = assess_repayability([], 15000.0)
        assert result.passes is False
        assert result.avg_monthly_cashflow == 0.0

    def test_fails_just_below_120pct_threshold(self):
        # avg = 17,999; repayment = 15,000; required = 18,000 → fails by 1 baht
        result = assess_repayability([17999.0] * 6, 15000.0)
        assert result.passes is False

    def test_fails_with_negative_cashflows(self):
        # Negative cashflow (structural loss) → definitely fails
        result = assess_repayability([-5000.0] * 6, 15000.0)
        assert result.passes is False


class TestRepayabilityOutputFields:
    def test_headroom_ratio_calculated_correctly(self):
        # avg = 30,000; repayment = 15,000; ratio = 2.0
        result = assess_repayability([30000.0] * 6, 15000.0)
        assert abs(result.headroom_ratio - 2.0) < 0.001

    def test_required_monthly_cashflow_is_repayment_times_1_2(self):
        result = assess_repayability([50000.0] * 6, 20000.0)
        assert result.required_monthly_cashflow == 24000.0  # 20,000 × 1.2

    def test_reason_string_contains_amounts_on_pass(self):
        result = assess_repayability([30000.0] * 6, 15000.0)
        assert "30,000" in result.reason
        assert "15,000" in result.reason

    def test_reason_string_contains_amounts_on_fail(self):
        result = assess_repayability([10000.0] * 6, 15000.0)
        assert "10,000" in result.reason
        assert "15,000" in result.reason

    def test_reason_mentions_npl_guard_on_fail(self):
        result = assess_repayability([5000.0] * 6, 15000.0)
        assert "NPL guard" in result.reason

    def test_avg_monthly_cashflow_correct_for_single_entry(self):
        result = assess_repayability([25000.0], 15000.0)
        assert result.avg_monthly_cashflow == 25000.0

    def test_empty_series_required_cashflow_still_set(self):
        result = assess_repayability([], 15000.0)
        assert result.required_monthly_cashflow == 18000.0  # 15,000 × 1.2
