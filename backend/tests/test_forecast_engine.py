"""
Unit tests for services/forecast_engine.py.

All tests are pure (no I/O). Input is crafted inline.
Coverage targets:
  compute_forecast — data_point count, starting balance, shortfall, surplus,
                     confidence (low/high), alert suppression, alert text,
                     key_drivers, scheduled events, avg_monthly_outflow floor,
                     handoff payload, ForecastResult fields
"""
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

# Path setup — allow imports from backend root
BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from services.forecast_engine import compute_forecast

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_accounts(deposit_balance: float = 500_000.0, include_credit_card: bool = False) -> dict:
    accounts = [
        {"account_id": "ACC-001", "account_type": "deposit", "balance": deposit_balance},
    ]
    if include_credit_card:
        accounts.append(
            {"account_id": "ACC-002", "account_type": "credit_card", "balance": 999_999.0}
        )
    return {"accounts": accounts}


def _make_transactions(
    n_days: int,
    today: date,
    daily_credit: float = 10_000.0,
    daily_debit: float = 8_000.0,
) -> list[dict]:
    """Create n_days of historical completed transactions ending yesterday."""
    txns = []
    for i in range(n_days):
        txn_date = today - timedelta(days=n_days - i)
        txns.append({
            "date": txn_date.isoformat(),
            "amount": daily_credit,
            "direction": "credit",
            "status": "completed",
            "category": "revenue",
        })
        txns.append({
            "date": txn_date.isoformat(),
            "amount": daily_debit,
            "direction": "debit",
            "status": "completed",
            "category": "operating_expense",
        })
    return txns


TODAY = date(2026, 7, 14)


# ---------------------------------------------------------------------------
# Test: data_points count
# ---------------------------------------------------------------------------

class TestDataPointsCount:
    def test_default_horizon_91_points(self):
        """horizon_days=90 → 91 data_points (day 0 through day 90 inclusive)."""
        result = compute_forecast(
            transactions=[],
            accounts=_make_accounts(),
            invoices_payable=[],
            invoices_receivable=[],
            today=TODAY,
            horizon_days=90,
        )
        assert len(result.data_points) == 91

    @pytest.mark.parametrize("horizon", [7, 30, 60, 180])
    def test_custom_horizon_correct_count(self, horizon: int):
        result = compute_forecast(
            transactions=[],
            accounts=_make_accounts(),
            invoices_payable=[],
            invoices_receivable=[],
            today=TODAY,
            horizon_days=horizon,
        )
        assert len(result.data_points) == horizon + 1


# ---------------------------------------------------------------------------
# Test: starting balance — deposit accounts only
# ---------------------------------------------------------------------------

class TestStartingBalance:
    def test_only_deposit_accounts_count(self):
        """Credit card account balances must NOT be added to starting balance."""
        result = compute_forecast(
            transactions=[],
            accounts=_make_accounts(deposit_balance=300_000.0, include_credit_card=True),
            invoices_payable=[],
            invoices_receivable=[],
            today=TODAY,
            horizon_days=0,  # just the starting day
        )
        # With 0 days of history and no transactions, avg_daily flows use defaults.
        # The day-0 data point (no daily flow applied) should reflect starting balance only.
        # Starting balance = 300,000 (deposit); credit_card 999,999 is excluded.
        assert result.data_points[0].projected_balance == pytest.approx(300_000.0)

    def test_multiple_deposit_accounts_summed(self):
        accounts = {
            "accounts": [
                {"account_type": "deposit", "balance": 100_000.0},
                {"account_type": "deposit", "balance": 200_000.0},
                {"account_type": "credit_card", "balance": 999_000.0},
            ]
        }
        result = compute_forecast(
            transactions=[],
            accounts=accounts,
            invoices_payable=[],
            invoices_receivable=[],
            today=TODAY,
            horizon_days=0,
        )
        assert result.data_points[0].projected_balance == pytest.approx(300_000.0)


# ---------------------------------------------------------------------------
# Test: shortfall detection
# ---------------------------------------------------------------------------

class TestShortfallDetection:
    def test_shortfall_detected_when_balance_drops_below_threshold(self):
        """
        Starting balance 100,000 with avg monthly outflow 50,000 (floor).
        Shortfall threshold = 50,000 × 0.5 = 25,000.
        With no inflows and daily debit > credit, balance eventually crosses threshold.
        """
        # Force a large payable in the near future to drop balance immediately
        tomorrow = TODAY + timedelta(days=1)
        result = compute_forecast(
            transactions=[],
            accounts=_make_accounts(deposit_balance=10_000.0),
            invoices_payable=[
                {
                    "due_date": tomorrow.isoformat(),
                    "amount_thb": 100_000.0,
                    "amount_paid_thb": 0.0,
                    "payment_status": "unpaid",
                    "counterparty_name": "Supplier A",
                }
            ],
            invoices_receivable=[],
            today=TODAY,
            horizon_days=90,
        )
        assert result.shortfall_detected is True
        assert result.shortfall_amount > 0

    def test_no_shortfall_when_balance_sustained(self):
        """Large starting balance with no large outflows — no shortfall."""
        result = compute_forecast(
            transactions=_make_transactions(90, TODAY, daily_credit=10_000, daily_debit=5_000),
            accounts=_make_accounts(deposit_balance=10_000_000.0),
            invoices_payable=[],
            invoices_receivable=[],
            today=TODAY,
            horizon_days=90,
        )
        assert result.shortfall_detected is False


# ---------------------------------------------------------------------------
# Test: surplus detection
# ---------------------------------------------------------------------------

class TestSurplusDetection:
    def test_surplus_detected_when_balance_sustained_above_threshold(self):
        """
        avg_monthly_outflow floor = 50,000. Surplus threshold = 50,000 × 1.5 = 75,000.
        Starting balance 10,000,000 >> surplus threshold → surplus after 14 days.
        """
        result = compute_forecast(
            transactions=[],
            accounts=_make_accounts(deposit_balance=10_000_000.0),
            invoices_payable=[],
            invoices_receivable=[],
            today=TODAY,
            horizon_days=90,
        )
        assert result.surplus_detected is True
        assert result.surplus_start_date is not None

    def test_no_surplus_below_14_consecutive_days(self):
        """
        Balance just barely above threshold but horizon < 14 days → no surplus trigger.
        """
        result = compute_forecast(
            transactions=[],
            accounts=_make_accounts(deposit_balance=10_000_000.0),
            invoices_payable=[],
            invoices_receivable=[],
            today=TODAY,
            horizon_days=10,  # fewer than 14 days required
        )
        # With horizon_days=10 we only have 11 data points; can't accumulate 14 consecutive
        assert result.surplus_detected is False


# ---------------------------------------------------------------------------
# Test: confidence levels
# ---------------------------------------------------------------------------

class TestConfidenceLevels:
    def test_confidence_low_when_less_than_90_days_history(self):
        """Transactions only spanning 30 days → confidence 'low'."""
        txns = _make_transactions(30, TODAY)
        result = compute_forecast(
            transactions=txns,
            accounts=_make_accounts(),
            invoices_payable=[],
            invoices_receivable=[],
            today=TODAY,
            horizon_days=90,
        )
        assert result.confidence_overall == "low"

    def test_confidence_low_when_no_transactions(self):
        """No history → history_days = 0 → confidence 'low'."""
        result = compute_forecast(
            transactions=[],
            accounts=_make_accounts(),
            invoices_payable=[],
            invoices_receivable=[],
            today=TODAY,
        )
        assert result.confidence_overall == "low"

    def test_confidence_high_when_180_plus_days_history(self):
        """Transactions spanning 200 days → confidence 'high'."""
        txns = _make_transactions(200, TODAY)
        result = compute_forecast(
            transactions=txns,
            accounts=_make_accounts(),
            invoices_payable=[],
            invoices_receivable=[],
            today=TODAY,
            horizon_days=90,
        )
        assert result.confidence_overall == "high"

    def test_confidence_exactly_180_days_is_high(self):
        """Exactly 180 days history → 'high' (boundary: >= 180 is high)."""
        txns = _make_transactions(180, TODAY)
        result = compute_forecast(
            transactions=txns,
            accounts=_make_accounts(),
            invoices_payable=[],
            invoices_receivable=[],
            today=TODAY,
        )
        assert result.confidence_overall == "high"

    def test_confidence_179_days_is_low(self):
        """179 days history → still 'low' (< 180)."""
        txns = _make_transactions(179, TODAY)
        result = compute_forecast(
            transactions=txns,
            accounts=_make_accounts(),
            invoices_payable=[],
            invoices_receivable=[],
            today=TODAY,
        )
        assert result.confidence_overall == "low"


# ---------------------------------------------------------------------------
# Test: alert message suppression
# ---------------------------------------------------------------------------

class TestAlertMessages:
    def test_alert_suppressed_when_confidence_low(self):
        """Even if there's a shortfall, alert_message_en must be None when confidence is low."""
        # Low confidence (< 30 days txns) + shortfall trigger
        tomorrow = TODAY + timedelta(days=1)
        result = compute_forecast(
            transactions=[],  # no history → confidence low
            accounts=_make_accounts(deposit_balance=10_000.0),
            invoices_payable=[
                {
                    "due_date": tomorrow.isoformat(),
                    "amount_thb": 200_000.0,
                    "amount_paid_thb": 0.0,
                    "payment_status": "unpaid",
                    "counterparty_name": "Big Supplier",
                }
            ],
            invoices_receivable=[],
            today=TODAY,
            horizon_days=90,
        )
        assert result.confidence_overall == "low"
        assert result.shortfall_detected is True
        assert result.alert_message_en is None
        assert result.alert_message_th is None

    def test_shortfall_alert_present_when_high_confidence(self):
        """With high confidence and shortfall detected, alert_message_en must not be None."""
        txns = _make_transactions(200, TODAY)
        tomorrow = TODAY + timedelta(days=1)
        result = compute_forecast(
            transactions=txns,
            accounts=_make_accounts(deposit_balance=10_000.0),
            invoices_payable=[
                {
                    "due_date": tomorrow.isoformat(),
                    "amount_thb": 500_000.0,
                    "amount_paid_thb": 0.0,
                    "payment_status": "unpaid",
                    "counterparty_name": "Big Supplier",
                }
            ],
            invoices_receivable=[],
            today=TODAY,
            horizon_days=90,
        )
        assert result.confidence_overall == "high"
        assert result.shortfall_detected is True
        assert result.alert_message_en is not None
        assert "shortfall" in result.alert_message_en.lower() or "cash" in result.alert_message_en.lower()

    def test_surplus_alert_present_when_high_confidence(self):
        """With high confidence and surplus detected, alert_message_en must not be None."""
        txns = _make_transactions(200, TODAY)
        result = compute_forecast(
            transactions=txns,
            accounts=_make_accounts(deposit_balance=10_000_000.0),
            invoices_payable=[],
            invoices_receivable=[],
            today=TODAY,
            horizon_days=90,
        )
        assert result.confidence_overall == "high"
        assert result.surplus_detected is True
        assert result.alert_message_en is not None
        assert "surplus" in result.alert_message_en.lower() or "deploy" in result.alert_message_en.lower()

    def test_no_alert_when_no_triggers(self):
        """No shortfall or surplus → both alert messages None regardless of confidence."""
        # Use a moderate balance: above shortfall threshold but below surplus threshold
        # With floor outflow = 50,000: shortfall threshold = 25,000, surplus = 75,000
        # Use balance 50,000 — above shortfall, below surplus
        txns = _make_transactions(200, TODAY, daily_credit=1000, daily_debit=800)
        result = compute_forecast(
            transactions=txns,
            accounts=_make_accounts(deposit_balance=50_000.0),
            invoices_payable=[],
            invoices_receivable=[],
            today=TODAY,
            horizon_days=13,  # not enough days to trigger surplus; balance moderate
        )
        # If neither triggered, alerts should be None
        if not result.shortfall_detected and not result.surplus_detected:
            assert result.alert_message_en is None
            assert result.alert_message_th is None


# ---------------------------------------------------------------------------
# Test: key_drivers
# ---------------------------------------------------------------------------

class TestKeyDrivers:
    def test_key_drivers_returns_list_with_at_least_one_entry(self):
        result = compute_forecast(
            transactions=[],
            accounts=_make_accounts(),
            invoices_payable=[],
            invoices_receivable=[],
            today=TODAY,
        )
        assert isinstance(result.summary.key_drivers, list)
        assert len(result.summary.key_drivers) >= 1

    def test_key_drivers_routine_message_when_no_scheduled_events(self):
        result = compute_forecast(
            transactions=[],
            accounts=_make_accounts(),
            invoices_payable=[],
            invoices_receivable=[],
            today=TODAY,
        )
        assert any("routine" in d.lower() or "no large" in d.lower() for d in result.summary.key_drivers)

    def test_scheduled_payable_appears_in_key_drivers(self):
        future_date = TODAY + timedelta(days=30)
        result = compute_forecast(
            transactions=[],
            accounts=_make_accounts(),
            invoices_payable=[
                {
                    "due_date": future_date.isoformat(),
                    "amount_thb": 250_000.0,
                    "amount_paid_thb": 0.0,
                    "payment_status": "unpaid",
                    "counterparty_name": "Supplier X",
                }
            ],
            invoices_receivable=[],
            today=TODAY,
        )
        # The large payable should appear in key_drivers
        assert any("250" in d or "Supplier" in d for d in result.summary.key_drivers)


# ---------------------------------------------------------------------------
# Test: scheduled payable reduces projected balance on exact date
# ---------------------------------------------------------------------------

class TestScheduledEvents:
    def test_scheduled_payable_reduces_balance_on_due_date(self):
        """A payable due in 10 days should reduce the projected balance on that day."""
        due_day_offset = 10
        due_date = TODAY + timedelta(days=due_day_offset)
        payable_amount = 50_000.0

        result_no_payable = compute_forecast(
            transactions=[],
            accounts=_make_accounts(deposit_balance=500_000.0),
            invoices_payable=[],
            invoices_receivable=[],
            today=TODAY,
            horizon_days=30,
        )
        result_with_payable = compute_forecast(
            transactions=[],
            accounts=_make_accounts(deposit_balance=500_000.0),
            invoices_payable=[
                {
                    "due_date": due_date.isoformat(),
                    "amount_thb": payable_amount,
                    "amount_paid_thb": 0.0,
                    "payment_status": "unpaid",
                    "counterparty_name": "Vendor Y",
                }
            ],
            invoices_receivable=[],
            today=TODAY,
            horizon_days=30,
        )

        # On the due date day_offset, balance should be lower by the payable amount
        balance_no_payable = result_no_payable.data_points[due_day_offset].projected_balance
        balance_with_payable = result_with_payable.data_points[due_day_offset].projected_balance
        assert balance_with_payable == pytest.approx(balance_no_payable - payable_amount)

    def test_scheduled_receivable_increases_balance_on_due_date(self):
        """A receivable due in 5 days should increase the projected balance on that day."""
        due_day_offset = 5
        due_date = TODAY + timedelta(days=due_day_offset)
        receivable_amount = 80_000.0

        result_no_receivable = compute_forecast(
            transactions=[],
            accounts=_make_accounts(deposit_balance=200_000.0),
            invoices_payable=[],
            invoices_receivable=[],
            today=TODAY,
            horizon_days=30,
        )
        result_with_receivable = compute_forecast(
            transactions=[],
            accounts=_make_accounts(deposit_balance=200_000.0),
            invoices_payable=[],
            invoices_receivable=[
                {
                    "due_date": due_date.isoformat(),
                    "amount_thb": receivable_amount,
                    "amount_paid_thb": 0.0,
                    "payment_status": "unpaid",
                    "counterparty_name": "Customer Z",
                }
            ],
            today=TODAY,
            horizon_days=30,
        )

        balance_no_recv = result_no_receivable.data_points[due_day_offset].projected_balance
        balance_with_recv = result_with_receivable.data_points[due_day_offset].projected_balance
        assert balance_with_recv == pytest.approx(balance_no_recv + receivable_amount)

    def test_scheduled_transaction_status_applies(self):
        """Transactions with status='scheduled' and future date are treated as point events."""
        future = TODAY + timedelta(days=7)
        txns = [
            {
                "date": future.isoformat(),
                "amount": 30_000.0,
                "direction": "debit",
                "status": "scheduled",
                "category": "payment",
                "description": "Scheduled rent payment",
            }
        ]
        result_no_scheduled = compute_forecast(
            transactions=[],
            accounts=_make_accounts(deposit_balance=200_000.0),
            invoices_payable=[],
            invoices_receivable=[],
            today=TODAY,
            horizon_days=30,
        )
        result_with_scheduled = compute_forecast(
            transactions=txns,
            accounts=_make_accounts(deposit_balance=200_000.0),
            invoices_payable=[],
            invoices_receivable=[],
            today=TODAY,
            horizon_days=30,
        )
        bal_no = result_no_scheduled.data_points[7].projected_balance
        bal_with = result_with_scheduled.data_points[7].projected_balance
        assert bal_with == pytest.approx(bal_no - 30_000.0)


# ---------------------------------------------------------------------------
# Test: avg_monthly_outflow floor
# ---------------------------------------------------------------------------

class TestAvgMonthlyOutflowFloor:
    def test_empty_transactions_returns_floor_50000(self):
        """No historical transactions → outflow is 0 / 3 → floored at 50,000."""
        result = compute_forecast(
            transactions=[],
            accounts=_make_accounts(),
            invoices_payable=[],
            invoices_receivable=[],
            today=TODAY,
        )
        assert result.rolling_avg_monthly_outflow >= 50_000.0

    def test_low_outflow_transactions_returns_floor(self):
        """Tiny debits → monthly avg < 50,000 → floored at 50,000."""
        txns = _make_transactions(90, TODAY, daily_credit=100.0, daily_debit=10.0)
        result = compute_forecast(
            transactions=txns,
            accounts=_make_accounts(),
            invoices_payable=[],
            invoices_receivable=[],
            today=TODAY,
        )
        # 10 * 90 = 900 total debit in 90 days → 300/month → floor = 50,000
        assert result.rolling_avg_monthly_outflow == pytest.approx(50_000.0)

    def test_large_outflow_exceeds_floor(self):
        """Large debit transactions → outflow above floor."""
        txns = _make_transactions(90, TODAY, daily_credit=100_000.0, daily_debit=90_000.0)
        result = compute_forecast(
            transactions=txns,
            accounts=_make_accounts(),
            invoices_payable=[],
            invoices_receivable=[],
            today=TODAY,
        )
        # 90,000 × 90 = 8,100,000 / 3 = 2,700,000 > floor
        assert result.rolling_avg_monthly_outflow > 50_000.0


# ---------------------------------------------------------------------------
# Test: summary min/max
# ---------------------------------------------------------------------------

class TestForecastSummary:
    def test_summary_min_max_within_data_points(self):
        result = compute_forecast(
            transactions=[],
            accounts=_make_accounts(deposit_balance=500_000.0),
            invoices_payable=[],
            invoices_receivable=[],
            today=TODAY,
        )
        balances = [dp.projected_balance for dp in result.data_points]
        assert result.summary.min_point == min(balances)
        assert result.summary.max_point == max(balances)

    def test_summary_dates_correspond_to_min_max_balance(self):
        result = compute_forecast(
            transactions=[],
            accounts=_make_accounts(deposit_balance=500_000.0),
            invoices_payable=[],
            invoices_receivable=[],
            today=TODAY,
        )
        min_dp = min(result.data_points, key=lambda dp: dp.projected_balance)
        max_dp = max(result.data_points, key=lambda dp: dp.projected_balance)
        assert result.summary.min_date == min_dp.date
        assert result.summary.max_date == max_dp.date


# ---------------------------------------------------------------------------
# Test: handoff payload (shortfall below avg monthly = yellow / opportunity trigger)
# ---------------------------------------------------------------------------

class TestHandoffPayload:
    def test_result_has_no_handoff_payload_field(self):
        """ForecastResult (the engine dataclass) doesn't have handoff_payload — it's added by agent."""
        result = compute_forecast(
            transactions=[],
            accounts=_make_accounts(),
            invoices_payable=[],
            invoices_receivable=[],
            today=TODAY,
        )
        # The engine result does NOT include handoff_payload (that's built by the agent layer)
        assert not hasattr(result, "handoff_payload")

    def test_shortfall_fields_present_when_triggered(self):
        """shortfall_date and shortfall_amount are populated when shortfall is detected."""
        tomorrow = TODAY + timedelta(days=1)
        result = compute_forecast(
            transactions=[],
            accounts=_make_accounts(deposit_balance=5_000.0),
            invoices_payable=[
                {
                    "due_date": tomorrow.isoformat(),
                    "amount_thb": 200_000.0,
                    "amount_paid_thb": 0.0,
                    "payment_status": "unpaid",
                    "counterparty_name": "Creditor",
                }
            ],
            invoices_receivable=[],
            today=TODAY,
            horizon_days=90,
        )
        assert result.shortfall_detected is True
        assert result.shortfall_date is not None
        assert result.shortfall_amount > 0


# ---------------------------------------------------------------------------
# Test: data_point date continuity
# ---------------------------------------------------------------------------

class TestDataPointDates:
    def test_data_points_start_at_today(self):
        result = compute_forecast(
            transactions=[],
            accounts=_make_accounts(),
            invoices_payable=[],
            invoices_receivable=[],
            today=TODAY,
        )
        assert result.data_points[0].date == TODAY

    def test_data_points_end_at_today_plus_horizon(self):
        horizon = 90
        result = compute_forecast(
            transactions=[],
            accounts=_make_accounts(),
            invoices_payable=[],
            invoices_receivable=[],
            today=TODAY,
            horizon_days=horizon,
        )
        assert result.data_points[-1].date == TODAY + timedelta(days=horizon)

    def test_data_point_confidence_matches_overall(self):
        result = compute_forecast(
            transactions=[],
            accounts=_make_accounts(),
            invoices_payable=[],
            invoices_receivable=[],
            today=TODAY,
        )
        for dp in result.data_points:
            assert dp.confidence == result.confidence_overall


# ---------------------------------------------------------------------------
# Test: partially paid invoice — only remainder counts
# ---------------------------------------------------------------------------

class TestPartiallyPaidInvoice:
    def test_partial_payable_deducts_only_remaining_amount(self):
        """Payable: 100k total, 60k already paid → only 40k deducted on due date."""
        due_date = TODAY + timedelta(days=5)

        result_full = compute_forecast(
            transactions=[],
            accounts=_make_accounts(deposit_balance=200_000.0),
            invoices_payable=[
                {
                    "due_date": due_date.isoformat(),
                    "amount_thb": 100_000.0,
                    "amount_paid_thb": 0.0,
                    "payment_status": "unpaid",
                    "counterparty_name": "Vendor",
                }
            ],
            invoices_receivable=[],
            today=TODAY,
            horizon_days=30,
        )
        result_partial = compute_forecast(
            transactions=[],
            accounts=_make_accounts(deposit_balance=200_000.0),
            invoices_payable=[
                {
                    "due_date": due_date.isoformat(),
                    "amount_thb": 100_000.0,
                    "amount_paid_thb": 60_000.0,
                    "payment_status": "partial",
                    "counterparty_name": "Vendor",
                }
            ],
            invoices_receivable=[],
            today=TODAY,
            horizon_days=30,
        )

        bal_full = result_full.data_points[5].projected_balance
        bal_partial = result_partial.data_points[5].projected_balance
        # partial should be 60k higher than full-unpaid result
        assert bal_partial == pytest.approx(bal_full + 60_000.0)
