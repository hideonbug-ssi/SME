"""
Forecast Agent (AIWSRT-2) — Rolling 90-day cashflow projection and alert generation.

This agent fetches ledger data via WireMock, runs the forecast engine, detects
surplus/shortfall triggers, generates plain-language alerts, and prepares a
handoff payload for AIWSRT-6.
"""
import asyncio
import json
import logging
import random
import time
from datetime import date, datetime, timedelta, timezone
from typing import Optional

import httpx

from config import settings
from services.wiremock_client import wiremock_client
from services.forecast_engine import (
    compute_forecast,
    ForecastResult,
    compute_historical_balance,
    compute_with_product_projection,
    _build_scheduled_events,
    _compute_avg_daily_flows,
    _parse_transactions,
)
from models.forecast import ForecastResponse, ForecastDataPoint, ForecastSummary
from agent_tracer import tracer

logger = logging.getLogger(__name__)


def _get_model():
    """Lazy-load LiteLlm so the import only happens when the agent is actually invoked."""
    from google.adk.models.lite_llm import LiteLlm  # noqa: PLC0415
    return LiteLlm(
        model=settings.litellm_model,
        api_base=settings.litellm_base_url,
        api_key=settings.litellm_api_key,
    )

# In-memory cache: last successful forecast result
_cache: dict = {}


async def _fetch_ledger_data(sme_id: str) -> tuple[dict, list[dict], list[dict], list[dict]]:
    """Fetch all ledger data. Uses scenario-injected data if available, else WireMock."""
    from demo_state import demo_state  # lazy import — avoids circular dependency at module load

    scenario_data = demo_state.get_scenario_raw_data()
    if scenario_data is not None:
        # Simulate 4 × WireMock round-trips (each 100–250 ms) so the agent takes real time
        for _ in range(4):
            await asyncio.sleep(random.uniform(0.10, 0.25))
        return (
            scenario_data["accounts"],
            scenario_data["transactions"],
            scenario_data["payables"],
            scenario_data["receivables"],
        )

    # Default: live WireMock fetch
    accounts = await wiremock_client.get_accounts(sme_id)
    transactions_data = await wiremock_client.get_transactions(sme_id)
    payables_data = await wiremock_client.get_invoices_payable(sme_id)
    receivables_data = await wiremock_client.get_invoices_receivable(sme_id)

    transactions = transactions_data.get("transactions", [])
    payables = payables_data.get("invoices", [])
    receivables = receivables_data.get("invoices", [])

    return accounts, transactions, payables, receivables


def _fallback_predict_recurring(
    transactions: list[dict],
    today: date,
    horizon_days: int,
) -> tuple[list[dict], list[dict]]:
    """
    Rule-based fallback: detect simple monthly-recurring transactions when LLM is unavailable.

    Groups completed transactions by (counterparty, direction, amount-bucket).
    If a group has 3+ occurrences spaced 25–35 days apart, it's treated as monthly recurring
    and projected forward into the horizon.
    """
    from collections import defaultdict

    parsed = _parse_transactions(transactions)
    completed = sorted(
        [t for t in parsed if t.get("status") == "completed" and t["date"] <= today],
        key=lambda t: t["date"],
    )

    # Bucket amount to nearest 5 000 so slight variations still cluster
    def _bucket(amt: float) -> int:
        return int(round(amt / 5000) * 5000)

    groups: dict[tuple, list] = defaultdict(list)
    for t in completed:
        key = (t.get("counterparty", ""), t.get("direction", "debit"), _bucket(t["amount"]))
        groups[key].append(t)

    patterns: list[dict] = []
    predicted: list[dict] = []

    for (counterparty, direction, amt_bucket), txns in groups.items():
        if len(txns) < 3:
            continue
        txns_sorted = sorted(txns, key=lambda t: t["date"])
        gaps = [(txns_sorted[i + 1]["date"] - txns_sorted[i]["date"]).days for i in range(len(txns_sorted) - 1)]
        avg_gap = sum(gaps) / len(gaps)
        if not (25 <= avg_gap <= 35):
            continue  # not monthly

        avg_amount = sum(t["amount"] for t in txns_sorted) / len(txns_sorted)
        last_date = txns_sorted[-1]["date"]
        evidence = ", ".join(t["date"].isoformat() for t in txns_sorted[-3:])
        # Strip month/year suffixes from description (e.g. "Payroll June 2026" → "Payroll")
        import re as _re
        raw_desc = txns_sorted[-1].get("description", counterparty or "Recurring transaction")
        desc = _re.sub(
            r"[\s\-]+(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|"
            r"Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
            r"\s+\d{4}",
            "",
            raw_desc,
            flags=_re.IGNORECASE,
        ).strip(" -")

        patterns.append({
            "description": desc,
            "direction": direction,
            "typical_amount": round(avg_amount, 2),
            "avg_interval_days": round(avg_gap, 1),
            "confidence": "medium",
            "evidence": f"Last 3 occurrences: {evidence}",
        })

        # Project occurrences into horizon
        next_date = last_date + timedelta(days=round(avg_gap))
        while next_date <= today + timedelta(days=horizon_days):
            if next_date > today:
                predicted.append({
                    "date": next_date,
                    "amount": round(avg_amount, 2),
                    "direction": direction,
                    "description": f"{desc} (predicted — monthly recurring)",
                    "confidence": "medium",
                })
            next_date += timedelta(days=round(avg_gap))

    return patterns, predicted


async def _predict_recurring_transactions(
    transactions: list[dict],
    today: date,
    horizon_days: int,
) -> tuple[str, list[dict], list[dict], str, int]:
    """
    Ask Claude to identify recurring cashflow patterns in the 90-day history and predict
    specific future transactions within the forecast horizon.

    Returns (prompt, patterns_identified, predicted_transactions, source, duration_ms).
    predicted_transactions: list of {date: date, amount: float, direction: str, description: str, confidence: str}
    """
    parsed = _parse_transactions(transactions)
    last_90_cutoff = today - timedelta(days=90)
    completed = sorted(
        [t for t in parsed if t.get("status") == "completed" and t["date"] >= last_90_cutoff and t["date"] <= today],
        key=lambda t: t["date"],
    )

    txn_lines = "\n".join(
        f"  {t['date'].isoformat()}  {'DEBIT ' if t.get('direction')=='debit' else 'CREDIT'}  "
        f"฿{t['amount']:>10,.0f}  {t.get('counterparty',''):<35}  {t.get('description','')}"
        for t in completed
    )
    horizon_end = (today + timedelta(days=horizon_days)).isoformat()

    prompt = f"""You are a cashflow analyst. Today is {today}. The forecast horizon ends on {horizon_end}.

Below are ALL bank transactions completed in the last 90 days for a Thai SME business:

{txn_lines}

Your task: identify EVERY recurring cashflow pattern — payroll, rent, supplier payments, customer receipts, subscriptions, tax payments, loan repayments, any repeating transaction — and predict the EXACT future occurrences that will fall within {today} to {horizon_end}.

Rules:
- A pattern needs at least 2 historical occurrences to qualify. 3+ makes it high-confidence.
- Use the actual dates and amounts from the history to infer the next dates — don't guess round numbers.
- If amounts vary slightly (e.g. ฿44,800, ฿45,200, ฿45,000) use the average.
- ONLY output transactions dated strictly after {today} and on or before {horizon_end}.
- Do NOT predict transactions that are already listed as scheduled (status=scheduled) in bank data.
- Do NOT predict one-off large transactions that appear only once.

Return a JSON object:
{{
  "patterns_identified": [
    {{
      "description": "what this recurring transaction is",
      "direction": "debit" or "credit",
      "typical_amount": <average amount in THB>,
      "interval": "monthly" or "weekly" or "biweekly" or "quarterly",
      "confidence": "high" (3+ occurrences) or "medium" (2 occurrences),
      "evidence": "dates seen in history e.g. 2026-04-05, 2026-05-05, 2026-06-05"
    }}
  ],
  "predicted_transactions": [
    {{
      "date": "YYYY-MM-DD",
      "amount": <float in THB>,
      "direction": "debit" or "credit",
      "description": "<pattern name> (predicted)",
      "confidence": "high" or "medium"
    }}
  ]
}}

Return only valid JSON. Every predicted_transaction date must be after {today} and on or before {horizon_end}."""

    t0 = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            resp = await client.post(
                f"{settings.litellm_base_url}/chat/completions",
                headers={"Authorization": f"Bearer {settings.litellm_api_key}"},
                json={
                    "model": settings.litellm_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 1500,
                },
            )
            resp.raise_for_status()
        llm_ms = int((time.monotonic() - t0) * 1000)
        content = resp.json()["choices"][0]["message"]["content"].strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        data = json.loads(content.strip())
        patterns = data.get("patterns_identified", [])
        raw_predicted = data.get("predicted_transactions", [])
        # Parse dates so engine can compare directly
        predicted = []
        for p in raw_predicted:
            try:
                predicted.append({
                    "date": date.fromisoformat(p["date"]),
                    "amount": float(p["amount"]),
                    "direction": p["direction"],
                    "description": p["description"],
                    "confidence": p.get("confidence", "medium"),
                })
            except (KeyError, ValueError):
                continue
        return prompt, patterns, predicted, "llm", llm_ms
    except Exception as exc:
        llm_ms = int((time.monotonic() - t0) * 1000)
        logger.warning("LLM pattern prediction failed (%dms): %s — using rule-based fallback", llm_ms, exc)
        patterns, predicted = _fallback_predict_recurring(transactions, today, horizon_days)
        return prompt, patterns, predicted, "fallback", llm_ms


async def _analyze_cashflow_with_llm(
    transactions: list[dict],
    payables: list[dict],
    receivables: list[dict],
    account_balance: float,
    result: ForecastResult,
    today: date,
) -> tuple[str, dict, str, int]:
    """
    Pass the transaction data + computed forecast to Claude for CFO-level analysis.

    The rule-based engine already computed the numbers (balance curve, shortfall amount, date).
    Claude's job here is interpretation: WHY this happened, what patterns it sees,
    what risks exist that the numbers alone don't surface.

    Returns (prompt_str, analysis_dict, source, duration_ms) where source is "llm" or "fallback".
    """
    if result.shortfall_amount > result.rolling_avg_monthly_outflow:
        tier_label = "RED — structural shortfall (gap exceeds one month's average outflow)"
    elif result.shortfall_detected:
        tier_label = "YELLOW — bridgeable shortfall (gap is within one month's average outflow)"
    elif result.surplus_detected:
        tier_label = "GREEN — sustained surplus (balance exceeds 1.5× monthly outflow for 14+ days)"
    else:
        tier_label = "GREEN — stable (no significant shortfall or surplus detected)"

    last_90_cutoff = today - timedelta(days=90)
    recent = sorted(
        [t for t in transactions if t.get("status") == "completed"
         and date.fromisoformat(t["date"]) >= last_90_cutoff],
        key=lambda t: t["date"],
    )
    scheduled = sorted(
        [t for t in transactions if t.get("status") == "scheduled"
         and date.fromisoformat(t["date"]) > today],
        key=lambda t: t["date"],
    )

    txn_block = "\n".join(
        f"  {t['date']}  {'DEBIT ' if t.get('direction')=='debit' else 'CREDIT'}  "
        f"฿{t['amount']:>10,.0f}  {t.get('counterparty',''):<35}  {t.get('description','')}"
        for t in recent
    )
    sched_block = "\n".join(
        f"  {t['date']}  {'DEBIT ' if t.get('direction')=='debit' else 'CREDIT'}  "
        f"฿{t['amount']:>10,.0f}  {t.get('counterparty',''):<35}  {t.get('description','')}"
        for t in scheduled
    ) or "  (none)"
    payable_block = "\n".join(
        f"  due {p.get('due_date')}  ฿{p.get('amount_thb',0):>10,.0f}  {p.get('counterparty_name','')}"
        for p in payables if p.get("payment_status") in ("unpaid", "partial")
    ) or "  (none)"
    receivable_block = "\n".join(
        f"  due {r.get('due_date')}  ฿{r.get('amount_thb',0):>10,.0f}  {r.get('counterparty_name','')}  [{r.get('payment_status','')}]"
        for r in receivables
    ) or "  (none)"

    shortfall_line = (
        f"Projected shortfall: ฿{result.shortfall_amount:,.0f} on {result.shortfall_date}"
        if result.shortfall_detected else
        f"Projected surplus peak: ฿{result.summary.max_point:,.0f} from {result.surplus_start_date}"
    )

    prompt = f"""You are a senior CFO analyst reviewing a Thai SME's cashflow position at KTB (Krungthai Bank). Today is {today}.

ACCOUNT BALANCE: ฿{account_balance:,.0f}
FORECAST TIER: {tier_label}
{shortfall_line}
ROLLING MONTHLY AVERAGE OUTFLOW: ฿{result.rolling_avg_monthly_outflow:,.0f}
SAFETY THRESHOLD (0.5× monthly avg): ฿{result.rolling_avg_monthly_outflow * 0.5:,.0f}

TRANSACTION HISTORY — last 90 days (completed):
{txn_block}

UPCOMING SCHEDULED TRANSACTIONS:
{sched_block}

OUTSTANDING INVOICES PAYABLE:
{payable_block}

EXPECTED RECEIVABLES:
{receivable_block}

The balance curve and shortfall figures above were computed by a deterministic engine. Your task is to provide the CFO-level interpretation that the numbers alone cannot — root causes, structural patterns, concentration risks, and prioritised actions.

Respond with a JSON object containing exactly these fields:
{{
  "situation_summary": "2-3 sentences: what is happening to this business's cashflow and why",
  "root_cause": "The specific transactions, counterparty relationships, or timing patterns that drive this forecast outcome",
  "risk_factors": ["specific risks identified from the transaction data — be concrete, name counterparties and amounts"],
  "pattern_observations": ["recurring patterns seen across the 90-day history: payment cycles, counterparty concentration, seasonal effects, anything that would affect future forecasts"],
  "priority_actions": ["ordered list: what this business owner must do first, second, third — specific and actionable given their actual position"]
}}

Return only valid JSON. No explanation outside the JSON."""

    t0 = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.post(
                f"{settings.litellm_base_url}/chat/completions",
                headers={"Authorization": f"Bearer {settings.litellm_api_key}"},
                json={
                    "model": settings.litellm_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 700,
                },
            )
            resp.raise_for_status()
        llm_ms = int((time.monotonic() - t0) * 1000)
        content = resp.json()["choices"][0]["message"]["content"].strip()
        # Strip markdown code fences if the model wrapped the JSON
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        analysis = json.loads(content.strip())
        return prompt, analysis, "llm", llm_ms
    except Exception as exc:
        llm_ms = int((time.monotonic() - t0) * 1000)
        logger.warning("LLM cashflow analysis failed (%dms): %s — using rule-based fallback", llm_ms, exc)
        return prompt, _fallback_analysis(result), "fallback", llm_ms


def _fallback_analysis(result: ForecastResult) -> dict:
    """Rule-based fallback when LLM is unreachable."""
    if result.shortfall_detected:
        tier = "red" if result.shortfall_amount > result.rolling_avg_monthly_outflow else "yellow"
        return {
            "situation_summary": (
                f"The business faces a {'structural' if tier == 'red' else 'bridgeable'} cashflow shortfall "
                f"of ฿{result.shortfall_amount:,.0f} projected on {result.shortfall_date}. "
                f"Immediate action is required to bridge the gap before that date."
            ),
            "root_cause": "; ".join(result.summary.key_drivers[:2]),
            "risk_factors": [
                f"Balance will fall ฿{result.shortfall_amount:,.0f} below the safety threshold on {result.shortfall_date}",
                "Timing mismatch between large payables and incoming receivables",
            ],
            "pattern_observations": ["Insufficient LLM connectivity to perform pattern analysis"],
            "priority_actions": [
                "Arrange bridging finance before the shortfall date",
                "Accelerate collection of outstanding receivables",
                "Defer non-critical supplier payments where contractually possible",
            ],
        }
    return {
        "situation_summary": (
            f"The business has a healthy cashflow position. "
            f"A surplus is projected to reach ฿{result.summary.max_point:,.0f}, "
            f"presenting an opportunity to deploy idle cash."
        ),
        "root_cause": "Inflows consistently exceed outflows with no large obligations in the near-term horizon.",
        "risk_factors": ["Idle cash not earning returns — opportunity cost"],
        "pattern_observations": ["Insufficient LLM connectivity to perform pattern analysis"],
        "priority_actions": [
            "Consider a KTB Business Term Deposit to earn returns on surplus",
            "Review whether surplus reflects timing (receivables arrived early) or structural improvement",
        ],
    }


async def get_cached_forecast(sme_id: str = "TH-SME-001", horizon_days: int = 90) -> "ForecastResponse":
    """Return the last forecast result from cache, or run fresh if no cache available.

    Called by ShortfallAgent so it reuses the ForecastAgent result without re-fetching
    data or emitting duplicate trace steps.
    """
    if "last_result" in _cache:
        return _cache["last_result"]
    return await run_forecast_agent(sme_id=sme_id, horizon_days=horizon_days)


def _build_handoff_payload(sme_id: str, result: ForecastResult, today: date) -> Optional[dict]:
    """Build the trigger payload for AIWSRT-6 if a surplus or shortfall was detected."""
    if result.surplus_detected and result.confidence_overall == "high":
        return {
            "sme_id": sme_id,
            "trigger_context": "opportunity",
            "forecast_window": f"{today} to {today.replace(day=today.day) if True else today}",
            "amount_thb": result.summary.max_point,
            "date_of_event": str(result.surplus_start_date),
            "confidence": result.confidence_overall,
        }
    elif result.shortfall_detected and result.confidence_overall == "high":
        shortfall_amount = result.shortfall_amount
        tier = "shortfall_red" if shortfall_amount > result.rolling_avg_monthly_outflow else "shortfall_yellow"
        return {
            "sme_id": sme_id,
            "trigger_context": tier,
            "forecast_window": f"{today} to {result.shortfall_date}",
            "amount_thb": shortfall_amount,
            "date_of_event": str(result.shortfall_date),
            "confidence": result.confidence_overall,
        }
    return None


async def run_forecast_agent(sme_id: str = "TH-SME-001", horizon_days: int = 90) -> ForecastResponse:
    """
    Run the forecast agent: fetch data, compute projection, detect triggers, generate alert.
    Returns a ForecastResponse. Falls back to cached result if WireMock is unreachable.
    """
    today = date(2026, 7, 14)  # PoC fixed date; use date.today() in production

    # Phase 1 — fetch ledger data
    try:
        t0 = time.monotonic()
        accounts, transactions, payables, receivables = await _fetch_ledger_data(sme_id)
        fetch_ms = int((time.monotonic() - t0) * 1000)
    except Exception as exc:
        logger.error("WireMock fetch failed: %s", exc)
        tracer.emit_step(
            agent="ForecastAgent",
            action="fetch_ledger_data",
            input_data={"sme_id": sme_id, "source": "WireMock Bank API (:8080)"},
            status="error",
            error=str(exc),
        )
        if _cache:
            logger.warning("Returning stale cached forecast.")
            return _cache["last_result"]
        raise

    account_balance = 0
    if isinstance(accounts.get("accounts"), list) and accounts["accounts"]:
        account_balance = accounts["accounts"][0].get("balance", 0)

    # --- Extract ledger facts for the trace step ---
    from demo_state import demo_state as _ds  # noqa: PLC0415
    _source = (
        f"Scenario '{_ds.active_scenario}' (pre-generated transaction set)"
        if _ds.get_scenario_raw_data() is not None
        else "WireMock Bank API (:8080)"
    )

    parsed_txns = _parse_transactions(transactions)
    completed = [t for t in parsed_txns if t.get("status") == "completed" and t["date"] <= today]
    scheduled_debits = sorted(
        [t for t in parsed_txns if t.get("status") == "scheduled" and t.get("direction") == "debit" and t["date"] > today],
        key=lambda t: t["date"],
    )
    hist_range = (
        f"{min(t['date'] for t in completed).isoformat()} to {max(t['date'] for t in completed).isoformat()}"
        if completed else "—"
    )
    last_90_cutoff = today - timedelta(days=90)
    recent = [t for t in completed if t["date"] >= last_90_cutoff]
    monthly_inflow = sum(t["amount"] for t in recent if t.get("direction") == "credit") / 3
    monthly_outflow = sum(t["amount"] for t in recent if t.get("direction") == "debit") / 3

    unpaid_payables = [
        {"counterparty": p.get("counterparty_name"), "amount_thb": p.get("amount_thb"), "due_date": p.get("due_date")}
        for p in payables
        if p.get("payment_status") in ("unpaid", "partial")
    ]
    expected_receivables = [
        {
            "counterparty": r.get("counterparty_name"),
            "amount_thb": r.get("amount_thb"),
            "due_date": r.get("due_date"),
            "status": r.get("payment_status"),
        }
        for r in receivables
        if r.get("payment_status") in ("unpaid", "partial")
        and date.fromisoformat(r["due_date"]) > today
    ]

    all_scheduled = sorted(
        [t for t in parsed_txns if t.get("status") == "scheduled" and t["date"] > today],
        key=lambda t: t["date"],
    )

    tracer.emit_step(
        agent="ForecastAgent",
        action="fetch_ledger_data",
        input_data={
            "sme_id": sme_id,
            "source": _source,
            "data_requested": ["accounts", "transactions", "invoices_payable", "invoices_receivable"],
        },
        output={
            "account_balance_thb": account_balance,
            "historical_transactions": [
                {
                    "date": t["date"].isoformat(),
                    "amount_thb": t["amount"],
                    "direction": t["direction"],
                    "description": t.get("description", ""),
                    "category": t.get("category", ""),
                    "counterparty": t.get("counterparty", ""),
                    "status": t.get("status", ""),
                }
                for t in sorted(completed, key=lambda x: x["date"])
            ],
            "scheduled_transactions": [
                {
                    "date": t["date"].isoformat(),
                    "amount_thb": t["amount"],
                    "direction": t["direction"],
                    "description": t.get("description", ""),
                    "category": t.get("category", ""),
                    "counterparty": t.get("counterparty", ""),
                    "status": t.get("status", ""),
                }
                for t in all_scheduled
            ],
            "invoices_payable": unpaid_payables,
            "invoices_receivable": expected_receivables,
        },
        duration_ms=fetch_ms,
    )

    # Phase 1b — LLM recurring-pattern prediction
    pred_prompt, pred_patterns, predicted_events, pred_source, pred_ms = await _predict_recurring_transactions(
        transactions=transactions,
        today=today,
        horizon_days=horizon_days,
    )
    tracer.emit_step(
        agent="ForecastAgent",
        action="predict_recurring_transactions",
        input_data={
            "historical_transactions_analyzed": len(recent),
            "date_range": (
                f"{min(t['date'] for t in recent).isoformat()} to {max(t['date'] for t in recent).isoformat()}"
                if recent else "—"
            ),
            "horizon_end": (today + timedelta(days=horizon_days)).isoformat(),
            "source": pred_source,
        },
        prompt=pred_prompt,
        reasoning=json.dumps(pred_patterns, ensure_ascii=False, indent=2),
        output={
            "patterns_identified": len(pred_patterns),
            "predicted_transactions": [
                {
                    "date": e["date"].isoformat() if isinstance(e["date"], date) else e["date"],
                    "amount_thb": e["amount"],
                    "direction": e["direction"],
                    "description": e["description"],
                    "confidence": e.get("confidence", "medium"),
                }
                for e in predicted_events
            ],
        },
        duration_ms=pred_ms,
    )

    # Phase 2 — compute forecast (using LLM-predicted events to drive the balance curve)
    t0 = time.monotonic()
    result: ForecastResult = compute_forecast(
        transactions=transactions,
        accounts=accounts,
        invoices_payable=payables,
        invoices_receivable=receivables,
        today=today,
        horizon_days=horizon_days,
        predicted_events=predicted_events,
    )
    compute_ms = int((time.monotonic() - t0) * 1000)

    # --- Build derivation reasoning from the actual scheduled events ---
    scheduled_events = _build_scheduled_events(transactions, payables, receivables, today)
    scheduled_events_sorted = sorted(scheduled_events, key=lambda e: (e["date"], -e["amount"]))
    avg_daily_credit, avg_daily_debit = _compute_avg_daily_flows(recent)
    daily_net = avg_daily_credit - avg_daily_debit
    shortfall_threshold = result.rolling_avg_monthly_outflow * 0.5

    all_events_for_trace = sorted(
        scheduled_events_sorted + [
            {**e, "date": e["date"] if isinstance(e["date"], date) else date.fromisoformat(e["date"]),
             "description": e["description"]}
            for e in predicted_events
        ],
        key=lambda e: (e["date"], -e["amount"]),
    )
    event_lines = "\n".join(
        f"  {'−' if e['direction'] == 'debit' else '+'} ฿{e['amount']:,.0f}  {e['date'].isoformat()}  {e['description']}"
        for e in all_events_for_trace[:12]
    ) or "  (none — relying on daily baseline only)"

    if result.shortfall_detected:
        outcome_line = (
            f"→ SHORTFALL detected on {result.shortfall_date}: balance drops to ฿{result.summary.min_point:,.0f}, "
            f"which is ฿{result.shortfall_amount:,.0f} below the safety threshold "
            f"(฿{shortfall_threshold:,.0f} = 0.5 × ฿{result.rolling_avg_monthly_outflow:,.0f} monthly avg outflow). "
            f"Tier: {'RED (structural gap)' if result.shortfall_amount > result.rolling_avg_monthly_outflow else 'YELLOW (bridgeable gap)'}."
        )
    elif result.surplus_detected:
        outcome_line = (
            f"→ SURPLUS detected from {result.surplus_start_date}: balance grows to ฿{result.summary.max_point:,.0f}, "
            f"sustained above the surplus threshold "
            f"(฿{result.rolling_avg_monthly_outflow * 1.5:,.0f} = 1.5 × monthly avg outflow) for 14+ consecutive days."
        )
    else:
        outcome_line = "→ No significant shortfall or surplus within the 90-day horizon."

    projection_reasoning = (
        f"Opening balance: ฿{account_balance:,.0f}.\n"
        f"Daily baseline: avg +฿{avg_daily_credit:,.0f} inflow / −฿{avg_daily_debit:,.0f} outflow "
        f"(net ฿{daily_net:+,.0f}/day from {len(recent)} historical transactions).\n"
        f"Safety threshold: ฿{shortfall_threshold:,.0f}  |  Surplus threshold: ฿{result.rolling_avg_monthly_outflow * 1.5:,.0f}\n\n"
        f"Scheduled events (next 90 days):\n{event_lines}\n\n"
        f"{outcome_line}"
    )

    tracer.emit_step(
        agent="ForecastAgent",
        action="compute_projection",
        input_data={
            "horizon_days": horizon_days,
            "opening_balance_thb": account_balance,
            "avg_daily_credit_thb": round(avg_daily_credit, 2),
            "avg_daily_debit_thb": round(avg_daily_debit, 2),
            "scheduled_events_count": len(scheduled_events),
            "llm_predicted_events_count": len(predicted_events),
        },
        reasoning=projection_reasoning,
        output={
            "shortfall_detected": result.shortfall_detected,
            "surplus_detected": result.surplus_detected,
            "shortfall_date": str(result.shortfall_date) if result.shortfall_date else None,
            "shortfall_amount_thb": round(result.shortfall_amount, 2),
            "safety_threshold_thb": round(shortfall_threshold, 2),
            "min_balance_thb": round(result.summary.min_point, 2),
            "min_balance_date": str(result.summary.min_date),
            "max_balance_thb": round(result.summary.max_point, 2),
            "confidence": result.confidence_overall,
            "key_drivers": result.summary.key_drivers[:3],
        },
        duration_ms=compute_ms,
    )

    # Phase 2b — LLM cashflow analysis (interpretation layer)
    llm_prompt, llm_analysis, llm_source, llm_ms = await _analyze_cashflow_with_llm(
        transactions=transactions,
        payables=payables,
        receivables=receivables,
        account_balance=account_balance,
        result=result,
        today=today,
    )
    tracer.emit_step(
        agent="ForecastAgent",
        action="analyze_cashflow_situation",
        input_data={
            "transactions_analyzed": len([t for t in transactions if t.get("status") == "completed"]),
            "forecast_tier": (
                "RED" if result.shortfall_detected and result.shortfall_amount > result.rolling_avg_monthly_outflow
                else "YELLOW" if result.shortfall_detected
                else "GREEN"
            ),
            "shortfall_amount_thb": round(result.shortfall_amount, 2) if result.shortfall_detected else 0,
            "source": llm_source,
        },
        prompt=llm_prompt,
        reasoning=json.dumps(llm_analysis, ensure_ascii=False, indent=2),
        output=llm_analysis,
        duration_ms=llm_ms,
    )

    handoff = _build_handoff_payload(sme_id, result, today)

    # Compute historical balance for the past 90 days
    historical_start = (today - timedelta(days=90)).isoformat()
    historical_data_points = compute_historical_balance(
        transactions=transactions,
        start_date=historical_start,
        account_opening_balance=280000.0,
    )

    # Determine product impact based on shortfall tier
    shortfall_amount = result.shortfall_amount
    if result.shortfall_detected and shortfall_amount > result.rolling_avg_monthly_outflow:
        # red: factoring
        product_impact = {
            "type": "factoring",
            "amount_thb": 120000.0,
            "effective_date": "2026-07-28",
        }
        product_description = "Invoice factoring: accelerate MegaCorp receivable (฿120,000)"
    elif result.shortfall_detected:
        # yellow: credit facility
        product_impact = {
            "type": "credit_facility",
            "amount_thb": 63962.0,
            "effective_date": "2026-07-20",
        }
        product_description = "KTB Business Credit Line (SCF): ฿63,962 available from 2026-07-20"
    else:
        # green: term deposit
        product_impact = {
            "type": "term_deposit",
            "amount_thb": 280000.0,
            "effective_date": today.isoformat(),
        }
        product_description = "KTB Business Term Deposit: 0.3% per month on ฿280,000"

    forecast_points_dicts = [
        {"date": dp.date.isoformat(), "projected_balance": dp.projected_balance}
        for dp in result.data_points
    ]
    with_product_data_points = compute_with_product_projection(forecast_points_dicts, product_impact)

    # Phase 3 — with-product projection
    if result.shortfall_detected:
        wp_min = min(pt["projected_balance"] for pt in with_product_data_points)
        wp_reasoning = (
            f"Without product: minimum balance ฿{result.summary.min_point:,.0f} on {result.summary.min_date} "
            f"(฿{result.shortfall_amount:,.0f} below safety threshold).\n"
            f"With product: {product_description}.\n"
            f"With-product minimum: ฿{wp_min:,.0f} — "
            f"{'shortfall eliminated' if wp_min >= shortfall_threshold else f'shortfall reduced to ฿{max(shortfall_threshold - wp_min, 0):,.0f}'}."
        )
    else:
        wp_bal_end = with_product_data_points[-1]["projected_balance"] if with_product_data_points else 0
        wp_reasoning = (
            f"No shortfall — deploying surplus. {product_description}.\n"
            f"Projected balance at end of horizon with product: ฿{wp_bal_end:,.0f}."
        )

    tracer.emit_step(
        agent="ForecastAgent",
        action="compute_with_product_projection",
        input_data={
            "product_type": product_impact["type"],
            "product_amount_thb": product_impact["amount_thb"],
            "effective_date": product_impact["effective_date"],
        },
        reasoning=wp_reasoning,
        output={
            "product": product_description,
            "with_product_min_balance_thb": round(min(pt["projected_balance"] for pt in with_product_data_points), 2) if with_product_data_points else None,
            "data_points_count": len(with_product_data_points),
        },
        duration_ms=0,
    )

    response = ForecastResponse(
        sme_id=sme_id,
        data_points=[
            ForecastDataPoint(date=dp.date, projected_balance=dp.projected_balance, confidence=dp.confidence)
            for dp in result.data_points
        ],
        summary=ForecastSummary(
            min_point=result.summary.min_point,
            min_date=result.summary.min_date,
            max_point=result.summary.max_point,
            max_date=result.summary.max_date,
            key_drivers=result.summary.key_drivers,
        ),
        rolling_avg_monthly_outflow=result.rolling_avg_monthly_outflow,
        confidence_overall=result.confidence_overall,
        updated_at=datetime.now(timezone.utc).isoformat(),
        alert_message=result.alert_message_en,
        alert_message_th=result.alert_message_th,
        surplus_detected=result.surplus_detected,
        shortfall_detected=result.shortfall_detected,
        handoff_payload=handoff,
        historical_data_points=historical_data_points,
        with_product_data_points=with_product_data_points,
        product_impact_description=product_description,
    )

    _cache["last_result"] = response
    return response
