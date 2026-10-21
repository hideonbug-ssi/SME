"""
Shortfall Evaluator Agent (AIWSRT-5).

Reads the latest forecast result, evaluates the three-tier logic (Green/Yellow/Red),
runs the NPL repayability check for Yellow/Red tiers, and prepares the AIWSRT-6 trigger.
"""
import logging
from typing import Optional

from config import settings
from agents.forecast_agent import get_cached_forecast
from services.repayability import assess_repayability
from services.approval_gateway import approval_gateway
from models.forecast import ShortfallStatusResponse
from agent_tracer import tracer

logger = logging.getLogger(__name__)

# Monthly repayment for a typical revolving credit line (used in repayability check)
_DEFAULT_PRODUCT_MONTHLY_REPAYMENT = 15000.0  # ฿15,000/month for a ฿180k line


async def run_shortfall_agent(sme_id: str = "TH-SME-001") -> ShortfallStatusResponse:
    """
    Evaluate cashflow shortfall tier and run NPL guard.

    Tier logic:
      - Green: no shortfall detected, or confidence is low
      - Yellow: shortfall detected, shortfall_amount <= rolling_avg_monthly_outflow (< 1 month gap)
      - Red: shortfall_amount > rolling_avg_monthly_outflow (structural gap)
    """
    forecast = await get_cached_forecast(sme_id=sme_id)

    if not forecast.shortfall_detected or forecast.confidence_overall == "low":
        return ShortfallStatusResponse(tier="green")

    shortfall_amount = 0.0
    shortfall_date = None
    if forecast.handoff_payload:
        shortfall_amount = forecast.handoff_payload.get("amount_thb", 0.0)
        shortfall_date = forecast.handoff_payload.get("date_of_event")

    # Determine tier
    if shortfall_amount <= forecast.rolling_avg_monthly_outflow:
        tier = "yellow"
        trigger_context = "shortfall_yellow"
    else:
        tier = "red"
        trigger_context = "shortfall_red"

    tracer.emit_step(
        agent="ShortfallAgent",
        action="evaluate_tier",
        input_data={
            "shortfall_detected": forecast.shortfall_detected,
            "shortfall_amount_thb": shortfall_amount,
            "shortfall_date": shortfall_date,
            "rolling_avg_monthly_outflow": forecast.rolling_avg_monthly_outflow,
        },
        reasoning=(
            f"Shortfall of ฿{shortfall_amount:,.0f} vs rolling avg outflow ฿{forecast.rolling_avg_monthly_outflow:,.0f}. "
            f"Ratio: {shortfall_amount / max(forecast.rolling_avg_monthly_outflow, 1):.2f}x. "
            f"Tier assigned: {tier.upper()} ({'structural gap > 1 month outflow' if tier == 'red' else 'manageable gap < 1 month outflow'})."
        ),
        output={"tier": tier, "trigger_context": trigger_context},
    )

    # Build projected monthly cashflow series (6 months) from forecast data_points
    monthly_cashflows = _extract_monthly_cashflows(forecast)

    # NPL guard: assess repayability before firing product trigger
    repayability = assess_repayability(
        projected_cashflow_series=monthly_cashflows,
        product_monthly_repayment=_DEFAULT_PRODUCT_MONTHLY_REPAYMENT,
    )

    product_trigger = None
    if repayability.passes:
        product_trigger = {
            "trigger_context": trigger_context,
            "sme_id": sme_id,
            "amount_thb": shortfall_amount,
            "date_of_event": shortfall_date,
        }
    else:
        logger.info("NPL guard fired for %s: %s", sme_id, repayability.reason)

    tracer.emit_step(
        agent="ShortfallAgent",
        action="npg_guard_check",
        input_data={
            "monthly_cashflows": monthly_cashflows,
            "product_monthly_repayment": _DEFAULT_PRODUCT_MONTHLY_REPAYMENT,
            "required_coverage_ratio": 1.2,
        },
        reasoning=repayability.reason,
        output={
            "passes": repayability.passes,
            "lending_products_allowed": repayability.passes,
            "product_trigger_fired": product_trigger is not None,
        },
    )

    recovery_plan = None
    if tier in ("yellow", "red"):
        recovery_plan = _build_recovery_plan(tier, shortfall_amount, shortfall_date, repayability)

    # Create a pending action for the set-aside suggestion if Yellow/Red
    pending_action_id = None
    if tier != "green" and shortfall_amount > 0:
        try:
            action = approval_gateway.create_pending_action(
                action_type="tax_setaside",
                memo=f"Proposed cash reserve to cover projected {tier}-tier shortfall of ฿{shortfall_amount:,.0f} on {shortfall_date}",
                amount=shortfall_amount,
                source_account="ACC-KTB-001",
                dest_account="reserve",
            )
            pending_action_id = action.id
        except Exception as exc:
            logger.warning("Could not create pending action: %s", exc)

    return ShortfallStatusResponse(
        tier=tier,
        shortfall_amount_thb=round(shortfall_amount, 2) if shortfall_amount else None,
        shortfall_date=shortfall_date,
        recovery_plan=recovery_plan,
        product_trigger=product_trigger,
        repayability_passed=repayability.passes,
    )


def _extract_monthly_cashflows(forecast) -> list[float]:
    """Approximate monthly net cashflows from the day-by-day data points (next 6 months)."""
    if not forecast.data_points:
        return []

    monthly = {}
    for dp in forecast.data_points:
        key = (dp.date.year, dp.date.month)
        monthly.setdefault(key, []).append(dp.projected_balance)

    # Net cashflow per month ≈ last balance - first balance in the month
    result = []
    for balances in list(monthly.values())[:6]:
        net = balances[-1] - balances[0]
        result.append(net)
    return result


def _build_recovery_plan(tier: str, shortfall_amount: float, shortfall_date, repayability) -> str:
    if tier == "yellow":
        if repayability.passes:
            return (
                f"A projected cash shortfall of ฿{shortfall_amount:,.0f} is expected around {shortfall_date}. "
                f"Recommended actions: (1) Draw on your revolving credit line; "
                f"(2) Accelerate collection of outstanding receivables; "
                f"(3) Defer non-critical supplier payments where possible."
            )
        else:
            return (
                f"A projected cash shortfall of ฿{shortfall_amount:,.0f} is expected around {shortfall_date}. "
                f"Recommended actions: (1) Accelerate receivables collection; "
                f"(2) Negotiate extended payment terms with suppliers; "
                f"(3) Review and defer non-essential expenditure. "
                f"Note: a lending product was evaluated but withheld — {repayability.reason}"
            )
    else:  # red
        if repayability.passes:
            return (
                f"A significant structural cashflow gap of ฿{shortfall_amount:,.0f} is projected by {shortfall_date}. "
                f"Recommended actions: (1) Arrange an SME term loan or overdraft facility immediately; "
                f"(2) Review pricing and accelerate billing cycles; "
                f"(3) Consider invoice financing for large outstanding receivables."
            )
        else:
            return (
                f"A significant structural cashflow gap of ฿{shortfall_amount:,.0f} is projected by {shortfall_date}. "
                f"A lending product was evaluated but the repayability assessment did not pass. "
                f"Recommended actions: (1) Urgently review cost structure and reduce operating expenses; "
                f"(2) Accelerate all outstanding receivables; "
                f"(3) Engage a financial advisor. {repayability.reason}"
            )
