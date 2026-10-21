"""
Unit tests for services/tax_engine.py.

All tests are pure (no I/O). The rules fixture loads tax_rules_2025.json once
and passes it into each function — matching the production call pattern.

Coverage targets:
  calc_pit       — worked example, WHT credit, multi-category, investment caps,
                   unknown category flag, zero income, below threshold
  calc_cit       — worked example, SME threshold bust, standard rate, WHT + PND51
                   credits, dividend exclusion flag, loss carryforward
  check_vat      — below threshold, at threshold, above threshold, registered estimate
  check_sbt      — applicable activity with/without receipts, non-applicable activity
  _apply_brackets — direct unit tests for boundary correctness
"""
import json
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Path setup — allow imports from backend root (services/, models/)
# ---------------------------------------------------------------------------
BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from services.tax_engine import (
    _apply_brackets,
    calc_cit,
    calc_pit,
    check_sbt,
    check_vat,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def rules() -> dict:
    rules_path = BACKEND_ROOT / "mock_data" / "tax_rules_2025.json"
    with open(rules_path) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# _apply_brackets — boundary tests
# ---------------------------------------------------------------------------

class TestApplyBrackets:
    def test_zero_taxable_returns_empty(self, rules: dict):
        bands, tax = _apply_brackets(rules["pit"]["tax_brackets"], 0.0)
        assert tax == 0.0
        assert bands == []

    def test_within_first_bracket_zero_rate(self, rules: dict):
        """Taxable income <= 150,000 → 0% bracket, no tax."""
        bands, tax = _apply_brackets(rules["pit"]["tax_brackets"], 100_000)
        assert tax == 0.0
        assert len(bands) == 1
        assert bands[0].rate == 0.0
        assert bands[0].taxable_amount == 100_000

    def test_exactly_at_bracket_boundary(self, rules: dict):
        """Taxable income = 150,000 → entirely in 0% bracket."""
        bands, tax = _apply_brackets(rules["pit"]["tax_brackets"], 150_000)
        assert tax == 0.0
        assert bands[0].taxable_amount == 150_000

    def test_one_baht_above_first_bracket(self, rules: dict):
        """150,001 → 150,000 @ 0% + 1 @ 5% = 0.05."""
        _, tax = _apply_brackets(rules["pit"]["tax_brackets"], 150_001)
        assert tax == pytest.approx(0.05, abs=0.01)

    def test_second_bracket_partial(self, rules: dict):
        """200,000 → 150,000 @ 0% + 50,000 @ 5% = 2,500."""
        _, tax = _apply_brackets(rules["pit"]["tax_brackets"], 200_000)
        assert tax == pytest.approx(2_500.0)

    def test_sme_brackets_zero_band(self, rules: dict):
        """SME net profit <= 300,000 → 0% band, no tax."""
        _, tax = _apply_brackets(rules["cit"]["sme_brackets"], 200_000)
        assert tax == 0.0

    def test_sme_bracket_partial_above_floor(self, rules: dict):
        """SME 400,000 → 0 + (400,000 - 300,000) × 15% = 15,000."""
        _, tax = _apply_brackets(rules["cit"]["sme_brackets"], 400_000)
        assert tax == pytest.approx(15_000.0)

    def test_flat_standard_rate_bracket(self):
        """Single unbounded bracket (standard CIT rate)."""
        brackets = [{"min": 0, "max": None, "rate": 0.20}]
        _, tax = _apply_brackets(brackets, 500_000)
        assert tax == pytest.approx(100_000.0)


# ---------------------------------------------------------------------------
# calc_pit — worked example and edge cases
# ---------------------------------------------------------------------------

class TestCalcPit:
    def test_pit_worked_example(self, rules: dict):
        """
        Canonical PIT worked example.
        income: 40_1_employment 615,000
        deduction: 50%, capped at 100,000 → 100,000
        net after expenses: 515,000
        personal allowance: 60,000
        taxable: 455,000
        tax: 0 + 7,500 + 15,500 = 23,000
        """
        result = calc_pit(
            tax_rules=rules,
            tax_year=2025,
            income_by_category={"40_1_employment": 615_000},
            expense_choices={},
            allowances={"personal": 60_000},
            wht_suffered=0.0,
        )
        assert result.gross_assessable == 615_000.0
        assert result.total_expenses == 100_000.0
        assert result.total_allowances == 60_000.0
        assert result.net_taxable_income == 455_000.0
        assert result.progressive_tax == pytest.approx(23_000.0)
        assert result.wht_credit_applied == 0.0
        assert result.net_tax_payable == pytest.approx(23_000.0)
        assert result.flags == []

    def test_pit_wht_credit_reduces_payable(self, rules: dict):
        """WHT of 10,000 applied against 23,000 tax → 13,000 net."""
        result = calc_pit(
            tax_rules=rules,
            tax_year=2025,
            income_by_category={"40_1_employment": 615_000},
            expense_choices={},
            allowances={"personal": 60_000},
            wht_suffered=10_000.0,
        )
        assert result.wht_credit_applied == 10_000.0
        assert result.net_tax_payable == pytest.approx(13_000.0)

    def test_pit_wht_cannot_exceed_progressive_tax(self, rules: dict):
        """WHT > progressive tax → net_tax_payable is zero, credit capped at tax."""
        result = calc_pit(
            tax_rules=rules,
            tax_year=2025,
            income_by_category={"40_1_employment": 615_000},
            expense_choices={},
            allowances={"personal": 60_000},
            wht_suffered=50_000.0,
        )
        assert result.wht_credit_applied == pytest.approx(result.progressive_tax)
        assert result.net_tax_payable == 0.0

    def test_pit_zero_tax_below_threshold(self, rules: dict):
        """Low income fully offset by deduction and allowance → zero tax."""
        result = calc_pit(
            tax_rules=rules,
            tax_year=2025,
            income_by_category={"40_1_employment": 200_000},
            expense_choices={},
            allowances={"personal": 60_000},
            wht_suffered=0.0,
        )
        # expenses = 100,000, income_after_expenses = 100,000, taxable = 40,000 (within 0% band)
        assert result.net_tax_payable == 0.0

    def test_pit_unknown_category_adds_flag(self, rules: dict):
        """Unknown income category: no deduction and a flag is added."""
        result = calc_pit(
            tax_rules=rules,
            tax_year=2025,
            income_by_category={"99_unknown": 100_000},
            expense_choices={},
            allowances={"personal": 60_000},
            wht_suffered=0.0,
        )
        assert result.total_expenses == 0.0
        assert len(result.flags) > 0
        assert any("99_unknown" in flag for flag in result.flags)

    def test_pit_investment_allowances_combined_cap(self, rules: dict):
        """RMF + SSF + ThaiESG exceeding combined cap of 500,000 is clamped, flag raised."""
        result = calc_pit(
            tax_rules=rules,
            tax_year=2025,
            income_by_category={"40_1_employment": 2_000_000},
            expense_choices={},
            allowances={
                "personal": 60_000,
                "rmf": 400_000,
                "ssf": 300_000,
                "thai_esg": 200_000,  # 400+300+200=900k > combined cap 500k
            },
            wht_suffered=0.0,
        )
        combined_cap = rules["pit"]["personal_allowances"]["combined_ssf_rmf_thai_esg_cap"]
        personal_allow = 60_000
        assert result.total_allowances == pytest.approx(personal_allow + combined_cap)
        assert any("combined limit" in flag or "combined" in flag.lower() for flag in result.flags)

    def test_pit_40_8_other_deduction_60pct_no_cap(self, rules: dict):
        """40_8_other: 60% deduction, no cap."""
        result = calc_pit(
            tax_rules=rules,
            tax_year=2025,
            income_by_category={"40_8_other": 500_000},
            expense_choices={},
            allowances={"personal": 60_000},
            wht_suffered=0.0,
        )
        assert result.total_expenses == pytest.approx(300_000.0)  # 500k × 60%, no cap
        assert result.net_taxable_income == pytest.approx(140_000.0)
        assert result.net_tax_payable == 0.0  # below 150k threshold

    def test_pit_multi_category_income(self, rules: dict):
        """Multiple income categories are summed correctly."""
        result = calc_pit(
            tax_rules=rules,
            tax_year=2025,
            income_by_category={
                "40_1_employment": 400_000,   # deduction capped at 100,000
                "40_8_other": 200_000,         # 60% = 120,000
            },
            expense_choices={},
            allowances={"personal": 60_000},
            wht_suffered=0.0,
        )
        assert result.gross_assessable == 600_000.0
        assert result.total_expenses == pytest.approx(100_000 + 120_000)  # 220,000
        assert result.net_taxable_income == pytest.approx(600_000 - 220_000 - 60_000)

    def test_pit_zero_income_zero_tax(self, rules: dict):
        result = calc_pit(
            tax_rules=rules,
            tax_year=2025,
            income_by_category={},
            expense_choices={},
            allowances={"personal": 60_000},
            wht_suffered=0.0,
        )
        assert result.gross_assessable == 0.0
        assert result.net_tax_payable == 0.0

    def test_pit_net_taxable_income_floor_is_zero(self, rules: dict):
        """Allowances exceeding income after expenses floor taxable at 0, not negative."""
        result = calc_pit(
            tax_rules=rules,
            tax_year=2025,
            income_by_category={"40_1_employment": 50_000},
            expense_choices={},
            allowances={"personal": 60_000},
            wht_suffered=0.0,
        )
        assert result.net_taxable_income == 0.0
        assert result.net_tax_payable == 0.0

    def test_pit_child_allowance(self, rules: dict):
        """child_count=2 → 2 × 30,000 = 60,000 additional allowance."""
        base = calc_pit(
            tax_rules=rules,
            tax_year=2025,
            income_by_category={"40_1_employment": 615_000},
            expense_choices={},
            allowances={"personal": 60_000},
            wht_suffered=0.0,
        )
        with_children = calc_pit(
            tax_rules=rules,
            tax_year=2025,
            income_by_category={"40_1_employment": 615_000},
            expense_choices={},
            allowances={"personal": 60_000, "child_count": 2},
            wht_suffered=0.0,
        )
        assert with_children.total_allowances == pytest.approx(base.total_allowances + 60_000)

    def test_pit_social_security_capped_at_9000(self, rules: dict):
        """Social security allowance capped at 9,000."""
        result = calc_pit(
            tax_rules=rules,
            tax_year=2025,
            income_by_category={"40_1_employment": 615_000},
            expense_choices={},
            allowances={"personal": 60_000, "social_security": 15_000},
            wht_suffered=0.0,
        )
        assert result.total_allowances == pytest.approx(60_000 + 9_000)


# ---------------------------------------------------------------------------
# calc_cit — worked example and edge cases
# ---------------------------------------------------------------------------

class TestCalcCit:
    def test_cit_sme_worked_example(self, rules: dict):
        """
        Canonical CIT SME worked example.
        net_profit = 2,000,000 - 1,100,000 - 450,000 - 50,000 = 400,000
        SME: 0–300,000 @ 0% + 100,000 @ 15% = 15,000
        """
        result = calc_cit(
            tax_rules=rules,
            tax_year=2025,
            is_sme=True,
            paid_up_capital=3_000_000,
            annual_revenue=8_000_000,
            revenue=2_000_000,
            cogs=1_100_000,
            deductible_expenses=450_000,
            depreciation=50_000,
            dividend_income=0.0,
            non_deductible_addbacks=0.0,
            loss_carryforward=0.0,
            pnd51_prepayment=0.0,
            wht_suffered=0.0,
        )
        assert result.net_profit_taxable == pytest.approx(400_000.0)
        assert result.rate_basis == "sme"
        assert result.net_tax_payable == pytest.approx(15_000.0)
        assert result.flags == []

    def test_cit_standard_rate_when_thresholds_exceeded(self, rules: dict):
        """annual_revenue > 30M → standard 20% rate even if is_sme=True."""
        result = calc_cit(
            tax_rules=rules,
            tax_year=2025,
            is_sme=True,
            paid_up_capital=3_000_000,
            annual_revenue=40_000_000,  # exceeds 30M threshold
            revenue=2_000_000,
            cogs=1_100_000,
            deductible_expenses=450_000,
            depreciation=50_000,
            dividend_income=0.0,
            non_deductible_addbacks=0.0,
            loss_carryforward=0.0,
            pnd51_prepayment=0.0,
            wht_suffered=0.0,
        )
        assert result.rate_basis == "standard"
        assert len(result.flags) > 0
        # 400,000 × 20% = 80,000
        assert result.net_tax_payable == pytest.approx(80_000.0)

    def test_cit_loss_carryforward_reduces_taxable_income(self, rules: dict):
        """Loss carryforward directly reduces net_profit_taxable; large enough zeros it out."""
        result = calc_cit(
            tax_rules=rules,
            tax_year=2025,
            is_sme=True,
            paid_up_capital=3_000_000,
            annual_revenue=8_000_000,
            revenue=2_000_000,
            cogs=1_100_000,
            deductible_expenses=450_000,
            depreciation=50_000,
            dividend_income=0.0,
            non_deductible_addbacks=0.0,
            loss_carryforward=500_000.0,  # larger than the 400,000 net profit
            pnd51_prepayment=0.0,
            wht_suffered=0.0,
        )
        assert result.net_profit_taxable == 0.0
        assert result.net_tax_payable == 0.0

    def test_cit_pnd51_credit_reduces_payable(self, rules: dict):
        """PND 51 prepayment is applied before WHT."""
        result = calc_cit(
            tax_rules=rules,
            tax_year=2025,
            is_sme=True,
            paid_up_capital=3_000_000,
            annual_revenue=8_000_000,
            revenue=2_000_000,
            cogs=1_100_000,
            deductible_expenses=450_000,
            depreciation=50_000,
            dividend_income=0.0,
            non_deductible_addbacks=0.0,
            loss_carryforward=0.0,
            pnd51_prepayment=8_000.0,
            wht_suffered=0.0,
        )
        assert result.pnd51_credit_applied == 8_000.0
        assert result.net_tax_payable == pytest.approx(7_000.0)

    def test_cit_standard_rate_entity_is_not_sme(self, rules: dict):
        """Non-SME: full 20% flat rate."""
        result = calc_cit(
            tax_rules=rules,
            tax_year=2025,
            is_sme=False,
            paid_up_capital=10_000_000,
            annual_revenue=50_000_000,
            revenue=5_000_000,
            cogs=2_000_000,
            deductible_expenses=1_000_000,
            depreciation=200_000,
            dividend_income=0.0,
            non_deductible_addbacks=0.0,
            loss_carryforward=0.0,
            pnd51_prepayment=0.0,
            wht_suffered=0.0,
        )
        expected_taxable = 5_000_000 - 2_000_000 - 1_000_000 - 200_000
        assert result.net_profit_taxable == pytest.approx(expected_taxable)
        assert result.rate_basis == "standard"
        assert result.net_tax_payable == pytest.approx(expected_taxable * 0.20)

    def test_cit_net_profit_taxable_floor_is_zero(self, rules: dict):
        """Large loss carryforward cannot make taxable profit negative."""
        result = calc_cit(
            tax_rules=rules,
            tax_year=2025,
            is_sme=True,
            paid_up_capital=3_000_000,
            annual_revenue=8_000_000,
            revenue=500_000,
            cogs=400_000,
            deductible_expenses=50_000,
            depreciation=0.0,
            dividend_income=0.0,
            non_deductible_addbacks=0.0,
            loss_carryforward=1_000_000.0,
            pnd51_prepayment=0.0,
            wht_suffered=0.0,
        )
        assert result.net_profit_taxable == 0.0
        assert result.net_tax_payable == 0.0

    def test_cit_dividend_income_excluded_and_flagged(self, rules: dict):
        """Dividend income excluded from taxable base and a flag is raised."""
        result = calc_cit(
            tax_rules=rules,
            tax_year=2025,
            is_sme=True,
            paid_up_capital=3_000_000,
            annual_revenue=8_000_000,
            revenue=2_000_000,
            cogs=1_100_000,
            deductible_expenses=450_000,
            depreciation=50_000,
            dividend_income=500_000.0,
            non_deductible_addbacks=0.0,
            loss_carryforward=0.0,
            pnd51_prepayment=0.0,
            wht_suffered=0.0,
        )
        # Dividend excluded: taxable still 400,000; tax still 15,000
        assert result.net_profit_taxable == pytest.approx(400_000.0)
        assert result.net_tax_payable == pytest.approx(15_000.0)
        assert any("dividend" in flag.lower() for flag in result.flags)


# ---------------------------------------------------------------------------
# check_vat — registration and monthly estimate
# ---------------------------------------------------------------------------

class TestCheckVat:
    def test_vat_not_required_below_threshold(self, rules: dict):
        """annual_turnover=1,000,000 → below 1,800,000 threshold → not required."""
        result = check_vat(
            tax_rules=rules,
            tax_year=2025,
            annual_turnover=1_000_000,
        )
        assert result.applicable is False
        assert result.registration_required is False
        assert result.indicative_net_vat_monthly is None

    def test_vat_at_threshold_not_required(self, rules: dict):
        """Exactly at threshold → not required (strictly greater than triggers)."""
        result = check_vat(
            tax_rules=rules,
            tax_year=2025,
            annual_turnover=1_800_000,
        )
        assert result.registration_required is False

    def test_vat_required_above_threshold(self, rules: dict):
        """annual_turnover=2,000,000 → above threshold → registration required."""
        result = check_vat(
            tax_rules=rules,
            tax_year=2025,
            annual_turnover=2_000_000,
        )
        assert result.applicable is True
        assert result.registration_required is True
        assert "PP.01" in result.obligation_note

    def test_vat_registered_with_monthly_estimate(self, rules: dict):
        """Registered entity with sales/purchases → monthly net VAT computed."""
        result = check_vat(
            tax_rules=rules,
            tax_year=2025,
            annual_turnover=3_000_000,
            taxable_sales=2_400_000,
            taxable_purchases=1_200_000,
            is_registered=True,
        )
        assert result.applicable is True
        assert result.registration_required is False
        # net = (2,400,000 - 1,200,000) / 12 × 7% = 7,000
        assert result.indicative_net_vat_monthly == pytest.approx(7_000.0)

    def test_vat_registered_without_sales_data_no_estimate(self, rules: dict):
        """Registered but no taxable_sales provided → no monthly estimate."""
        result = check_vat(
            tax_rules=rules,
            tax_year=2025,
            annual_turnover=3_000_000,
            is_registered=True,
        )
        assert result.indicative_net_vat_monthly is None
        assert "PP.30" in result.obligation_note


# ---------------------------------------------------------------------------
# check_sbt — applicable and non-applicable activities
# ---------------------------------------------------------------------------

class TestCheckSbt:
    def test_sbt_applicable_for_banking_activity(self, rules: dict):
        """activity_type='banking' is subject to SBT."""
        result = check_sbt(
            tax_rules=rules,
            tax_year=2025,
            activity_type="banking",
            gross_receipts=12_000_000,
        )
        assert result.applicable is True
        assert result.base_rate == pytest.approx(0.03)
        # 12,000,000 / 12 × 3% = 30,000
        assert result.indicative_sbt_monthly == pytest.approx(30_000.0)
        assert "PT.40" in result.obligation_note

    def test_sbt_not_applicable_for_retail(self, rules: dict):
        """activity_type='retail' is NOT subject to SBT."""
        result = check_sbt(
            tax_rules=rules,
            tax_year=2025,
            activity_type="retail",
        )
        assert result.applicable is False
        assert result.base_rate is None
        assert result.indicative_sbt_monthly is None
        assert "retail" in result.obligation_note

    def test_sbt_life_insurance_rate(self, rules: dict):
        result = check_sbt(
            tax_rules=rules,
            tax_year=2025,
            activity_type="life_insurance",
            gross_receipts=24_000_000,
        )
        assert result.base_rate == pytest.approx(0.025)
        assert result.indicative_sbt_monthly == pytest.approx(50_000.0)

    def test_sbt_applicable_without_gross_receipts_no_estimate(self, rules: dict):
        """Applicable activity but no gross_receipts → no monthly estimate."""
        result = check_sbt(
            tax_rules=rules,
            tax_year=2025,
            activity_type="real_estate_sale",
        )
        assert result.applicable is True
        assert result.indicative_sbt_monthly is None

    def test_sbt_all_applicable_activities_recognized(self, rules: dict):
        """Every activity in the rules dict is correctly recognized as applicable."""
        for activity in rules["sbt"]["applicable_activities"]:
            result = check_sbt(
                tax_rules=rules,
                tax_year=2025,
                activity_type=activity,
            )
            assert result.applicable is True, f"Expected applicable=True for '{activity}'"
