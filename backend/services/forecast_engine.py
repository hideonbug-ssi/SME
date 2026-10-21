"""
Rolling 90-day cashflow forecast engine.

Pure computation — no I/O. Receives normalised dicts, returns structured result.
Business rules:
  - Surplus trigger: projected balance >= 1.5x avg_monthly_outflow for 14+ consecutive days
  - Shortfall trigger: projected balance drops below 0.5x avg_monthly_outflow anywhere in horizon
  - Confidence: "low" if < 90 days history, "high" if >= 180 days
"""
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional


@dataclass
class DataPoint:
    date: date
    projected_balance: float
    confidence: str


@dataclass
class ForecastSummary:
    min_point: float
    min_date: date
    max_point: float
    max_date: date
    key_drivers: list[str]


@dataclass
class ForecastResult:
    data_points: list[DataPoint]
    summary: ForecastSummary
    rolling_avg_monthly_outflow: float
    confidence_overall: str
    surplus_detected: bool
    shortfall_detected: bool
    surplus_start_date: Optional[date]
    shortfall_date: Optional[date]
    shortfall_amount: float  # how far below threshold
    alert_message_en: Optional[str]
    alert_message_th: Optional[str]


def compute_forecast(
    transactions: list[dict],
    accounts: dict,
    invoices_payable: list[dict],
    invoices_receivable: list[dict],
    today: Optional[date] = None,
    horizon_days: int = 90,
    predicted_events: list[dict] | None = None,
) -> ForecastResult:
    """
    Compute a rolling 90-day cashflow forecast.

    Args:
        transactions: list of transaction dicts with keys: date (str YYYY-MM-DD),
                      amount (float), direction ("credit"|"debit"), status, category
        accounts: dict with accounts list, each having balance float
        predicted_events: LLM-predicted recurring transactions — list of
                          {date: date, amount: float, direction: str, description: str}.
                          Applied in the day loop exactly like scheduled events.
        invoices_payable: list of payable invoice dicts (due_date, amount_thb, amount_paid_thb, payment_status)
        invoices_receivable: list of receivable invoice dicts
        today: reference date for projection (defaults to date.today())
        horizon_days: number of days to project forward

    Returns:
        ForecastResult with data_points, triggers, and alert messages
    """
    if today is None:
        today = date.today()

    # 1. Determine starting balance from accounts
    starting_balance = _get_starting_balance(accounts)

    # 2. Parse and filter historical transactions (completed only)
    parsed_txns = _parse_transactions(transactions)
    historical_txns = [t for t in parsed_txns if t["date"] <= today and t["status"] == "completed"]

    # 3. Determine history length for confidence
    if historical_txns:
        earliest = min(t["date"] for t in historical_txns)
        history_days = (today - earliest).days
    else:
        history_days = 0

    confidence_overall = "high" if history_days >= 180 else "low"

    # 4. Compute rolling average monthly outflow from last 90 days of history
    rolling_avg_monthly_outflow = _compute_avg_monthly_outflow(historical_txns, today)

    # 5. Compute average daily flows from history
    last_90_txns = [t for t in historical_txns if (today - t["date"]).days <= 90]
    avg_daily_credit, avg_daily_debit = _compute_avg_daily_flows(last_90_txns)

    # 6. Build scheduled events: payables and receivables with future due dates
    scheduled_events = _build_scheduled_events(
        transactions, invoices_payable, invoices_receivable, today
    )

    # 6b. Adjust daily baseline to avoid double-counting predicted recurring events.
    #
    # The daily avg already encodes recurring expenses (payroll, rent, etc.) as a smooth
    # per-day amount. Making those expenses explicit as point events improves timing
    # accuracy, but we must reduce the baseline by the same amount so total cash flow
    # stays correct over the horizon.
    adj_avg_daily_debit = avg_daily_debit
    adj_avg_daily_credit = avg_daily_credit
    if predicted_events and horizon_days > 0:
        pred_debit_total = sum(
            e["amount"] for e in predicted_events if e.get("direction") == "debit"
        )
        pred_credit_total = sum(
            e["amount"] for e in predicted_events if e.get("direction") == "credit"
        )
        adj_avg_daily_debit = max(0.0, avg_daily_debit - pred_debit_total / horizon_days)
        adj_avg_daily_credit = max(0.0, avg_daily_credit - pred_credit_total / horizon_days)

    # 7. Project forward day by day
    data_points = []
    balance = starting_balance
    surplus_consecutive_days = 0
    surplus_start_date = None
    surplus_detected = False
    shortfall_detected = False
    shortfall_date = None
    shortfall_amount = 0.0

    surplus_threshold = rolling_avg_monthly_outflow * 1.5
    shortfall_threshold = rolling_avg_monthly_outflow * 0.5

    for day_offset in range(horizon_days + 1):
        projection_date = today + timedelta(days=day_offset)

        # Apply daily flows (adjusted baseline — predicted events removed from smooth average)
        if day_offset > 0:
            balance += adj_avg_daily_credit - adj_avg_daily_debit

        # Apply scheduled events on this exact date
        for event in scheduled_events:
            if event["date"] == projection_date:
                if event["direction"] == "credit":
                    balance += event["amount"]
                else:
                    balance -= event["amount"]

        # Apply LLM-predicted recurring transactions on their predicted dates
        if predicted_events:
            for event in predicted_events:
                evt_date = event["date"] if isinstance(event["date"], date) else date.fromisoformat(event["date"])
                if evt_date == projection_date:
                    if event["direction"] == "credit":
                        balance += event["amount"]
                    else:
                        balance -= event["amount"]

        confidence = confidence_overall
        data_points.append(DataPoint(date=projection_date, projected_balance=round(balance, 2), confidence=confidence))

        # Surplus detection: consecutive days above threshold
        if balance >= surplus_threshold:
            if surplus_start_date is None:
                surplus_start_date = projection_date
            surplus_consecutive_days += 1
            if surplus_consecutive_days >= 14 and not surplus_detected:
                surplus_detected = True
        else:
            surplus_consecutive_days = 0
            surplus_start_date = None

        # Shortfall detection: first crossing sets the date; worst (deepest) point sets the amount
        if balance < shortfall_threshold:
            deficit = shortfall_threshold - balance
            if not shortfall_detected:
                shortfall_detected = True
                shortfall_date = projection_date
            if deficit > shortfall_amount:
                shortfall_amount = deficit  # track the worst dip, not just the first

    # 8. Compute summary
    balances = [dp.projected_balance for dp in data_points]
    min_balance = min(balances)
    max_balance = max(balances)
    min_idx = balances.index(min_balance)
    max_idx = balances.index(max_balance)

    key_drivers = _identify_key_drivers(
        scheduled_events, invoices_payable, invoices_receivable, predicted_events or []
    )

    summary = ForecastSummary(
        min_point=min_balance,
        min_date=data_points[min_idx].date,
        max_point=max_balance,
        max_date=data_points[max_idx].date,
        key_drivers=key_drivers,
    )

    # 9. Build alert messages
    alert_en, alert_th = _build_alert_messages(
        surplus_detected=surplus_detected,
        shortfall_detected=shortfall_detected,
        shortfall_date=shortfall_date,
        shortfall_amount=shortfall_amount,
        shortfall_threshold=shortfall_threshold,
        surplus_start_date=surplus_start_date,
        min_balance=min_balance,
        confidence_overall=confidence_overall,
    )

    return ForecastResult(
        data_points=data_points,
        summary=summary,
        rolling_avg_monthly_outflow=round(rolling_avg_monthly_outflow, 2),
        confidence_overall=confidence_overall,
        surplus_detected=surplus_detected,
        shortfall_detected=shortfall_detected,
        surplus_start_date=surplus_start_date,
        shortfall_date=shortfall_date,
        shortfall_amount=round(shortfall_amount, 2),
        alert_message_en=alert_en,
        alert_message_th=alert_th,
    )


def _get_starting_balance(accounts: dict) -> float:
    total = 0.0
    for account in accounts.get("accounts", []):
        if account.get("account_type") == "deposit":
            total += account.get("balance", 0.0)
    return total


def _parse_transactions(transactions: list[dict]) -> list[dict]:
    parsed = []
    for t in transactions:
        try:
            txn_date = date.fromisoformat(t["date"]) if isinstance(t["date"], str) else t["date"]
            parsed.append({**t, "date": txn_date})
        except (KeyError, ValueError):
            continue
    return parsed


def _compute_avg_monthly_outflow(historical_txns: list[dict], today: date) -> float:
    """Compute rolling average monthly outflow from last 90 days. Returns minimum of 50,000 to avoid division issues."""
    last_90 = [t for t in historical_txns if (today - t["date"]).days <= 90]
    total_outflow = sum(t["amount"] for t in last_90 if t.get("direction") == "debit")
    # 90 days ≈ 3 months
    monthly_avg = total_outflow / 3.0
    return max(monthly_avg, 50000.0)  # floor to prevent near-zero reference figure


def _compute_avg_daily_flows(txns: list[dict]) -> tuple[float, float]:
    """Returns (avg_daily_credit, avg_daily_debit) from the provided transaction set."""
    if not txns:
        return 6667.0, 5000.0  # conservative defaults (~200k/month in, 150k/month out)

    days_span = max((max(t["date"] for t in txns) - min(t["date"] for t in txns)).days, 1)
    total_credit = sum(t["amount"] for t in txns if t.get("direction") == "credit")
    total_debit = sum(t["amount"] for t in txns if t.get("direction") == "debit")
    return total_credit / days_span, total_debit / days_span


def _build_scheduled_events(
    transactions: list[dict],
    invoices_payable: list[dict],
    invoices_receivable: list[dict],
    today: date,
) -> list[dict]:
    """
    Build list of future point events that adjust the balance projection.

    Deduplication: if a scheduled transaction and an invoice payable fall on the
    same date with the same amount and direction (debit), count only the scheduled
    transaction. This prevents double-counting when a payable is already recorded
    as a scheduled bank transaction.
    """
    events = []

    # Track (date, amount, direction) tuples for scheduled transactions to dedup payables
    scheduled_keys: set[tuple] = set()

    # Scheduled transactions in the transaction list
    for t in transactions:
        try:
            txn_date = date.fromisoformat(t["date"]) if isinstance(t["date"], str) else t["date"]
            if txn_date > today and t.get("status") == "scheduled":
                key = (txn_date, round(t["amount"], 2), t.get("direction", "debit"))
                scheduled_keys.add(key)
                events.append({
                    "date": txn_date,
                    "amount": t["amount"],
                    "direction": t.get("direction", "debit"),
                    "description": t.get("description", "Scheduled payment"),
                })
        except (KeyError, ValueError):
            continue

    # Unpaid payables due in future — skip if already covered by a scheduled transaction
    for inv in invoices_payable:
        try:
            due = date.fromisoformat(inv["due_date"])
            if due > today and inv.get("payment_status") in ("unpaid", "partial"):
                remaining = inv["amount_thb"] - inv.get("amount_paid_thb", 0.0)
                if remaining > 0:
                    key = (due, round(remaining, 2), "debit")
                    if key in scheduled_keys:
                        # Already represented by a scheduled transaction — skip to avoid double-counting
                        continue
                    events.append({
                        "date": due,
                        "amount": remaining,
                        "direction": "debit",
                        "description": f"Payable: {inv.get('counterparty_name', 'Supplier')}",
                    })
        except (KeyError, ValueError):
            continue

    # Expected receivables (optimistic: assume payment on due date)
    for inv in invoices_receivable:
        try:
            due = date.fromisoformat(inv["due_date"])
            if due > today and inv.get("payment_status") in ("unpaid", "partial"):
                remaining = inv["amount_thb"] - inv.get("amount_paid_thb", 0.0)
                if remaining > 0:
                    events.append({
                        "date": due,
                        "amount": remaining,
                        "direction": "credit",
                        "description": f"Receivable: {inv.get('counterparty_name', 'Customer')}",
                    })
        except (KeyError, ValueError):
            continue

    return events


def _identify_key_drivers(
    scheduled_events: list[dict],
    invoices_payable: list[dict],
    invoices_receivable: list[dict],
    predicted_events: list[dict] | None = None,
) -> list[str]:
    """
    Rank the most impactful cashflow events — known scheduled events plus LLM-predicted
    recurring transactions — by amount and return the top 5 as human-readable strings.

    Predicted events are labelled so the reader knows they are forecast, not confirmed.
    """
    all_events: list[dict] = []

    for event in scheduled_events:
        all_events.append({
            "date": event["date"],
            "amount": event["amount"],
            "direction": event["direction"],
            "description": event["description"],
            "predicted": False,
        })

    for event in (predicted_events or []):
        evt_date = event["date"] if isinstance(event["date"], date) else date.fromisoformat(event["date"])
        all_events.append({
            "date": evt_date,
            "amount": event["amount"],
            "direction": event["direction"],
            "description": event["description"],
            "predicted": True,
        })

    # Deduplicate: if a predicted event closely matches a scheduled one (same date ±3 days,
    # same direction, amount within 10%) keep only the scheduled (confirmed) version.
    confirmed = [e for e in all_events if not e["predicted"]]
    for pred in [e for e in all_events if e["predicted"]]:
        duplicate = any(
            c["direction"] == pred["direction"]
            and abs((c["date"] - pred["date"]).days) <= 3
            and abs(c["amount"] - pred["amount"]) / max(pred["amount"], 1) <= 0.10
            for c in confirmed
        )
        if not duplicate:
            confirmed.append(pred)

    # For predicted recurring events, keep only the soonest occurrence of each pattern
    # (same direction + amount-bucket) so the same recurring expense doesn't fill the list.
    seen_recurring: set[tuple] = set()
    deduped: list[dict] = []
    for e in sorted(confirmed, key=lambda x: x["date"]):
        if e["predicted"]:
            bucket = (e["direction"], int(round(e["amount"] / 5000) * 5000))
            if bucket in seen_recurring:
                continue
            seen_recurring.add(bucket)
        deduped.append(e)

    sorted_events = sorted(deduped, key=lambda e: e["amount"], reverse=True)

    drivers = []
    for event in sorted_events[:5]:
        direction_word = "Payment due" if event["direction"] == "debit" else "Expected receipt"
        label = f"{direction_word}: {event['description']} (฿{event['amount']:,.0f}) on {event['date']}"
        if event["predicted"]:
            label += " [predicted recurring]"
        drivers.append(label)

    if not drivers:
        drivers.append("Routine operating cashflow — no large single events detected")
    return drivers


def compute_historical_balance(
    transactions: list[dict],
    start_date: str,
    account_opening_balance: float,
) -> list[dict]:
    """
    Compute daily running balance from start_date up to today (2026-07-14).

    Args:
        transactions: raw list of dicts with keys: date (str YYYY-MM-DD), amount (float),
                      direction ("credit"|"debit"), status, description
        start_date: ISO date string — first day of the output series
        account_opening_balance: balance at the start of start_date (before any transactions that day)

    Returns:
        list of {date: str, actual_balance: float} covering start_date … today inclusive
    """
    today = date(2026, 7, 14)
    start = date.fromisoformat(start_date)

    # Parse and index completed transactions by date
    daily_net: dict[date, float] = {}
    for t in transactions:
        try:
            txn_date = date.fromisoformat(t["date"]) if isinstance(t["date"], str) else t["date"]
            if t.get("status") != "completed":
                continue
            if txn_date < start or txn_date > today:
                continue
            direction = t.get("direction", "credit")
            amount = float(t.get("amount", 0))
            delta = amount if direction == "credit" else -amount
            daily_net[txn_date] = daily_net.get(txn_date, 0.0) + delta
        except (KeyError, ValueError, TypeError):
            continue

    result = []
    running_balance = account_opening_balance
    current = start
    while current <= today:
        running_balance += daily_net.get(current, 0.0)
        result.append({"date": current.isoformat(), "actual_balance": round(running_balance, 2)})
        current += timedelta(days=1)

    return result


def compute_with_product_projection(
    forecast_points: list[dict],
    product_impact: dict,
) -> list[dict]:
    """
    Apply a product impact to the forecast curve.

    Args:
        forecast_points: list of {date: str, projected_balance: float} dicts
        product_impact: dict with keys:
            type: "credit_facility" | "term_deposit" | "factoring"
            amount_thb: float
            effective_date: str (ISO date)

    Returns:
        list of {date: str, projected_balance: float} — same length as input
    """
    impact_type = product_impact.get("type", "")
    amount = float(product_impact.get("amount_thb", 0))
    effective_date = date.fromisoformat(product_impact["effective_date"])

    result = []
    applied = False
    running_extra = 0.0

    for point in forecast_points:
        pt_date = date.fromisoformat(point["date"]) if isinstance(point["date"], str) else point["date"]
        base = float(point["projected_balance"])

        if pt_date >= effective_date and not applied:
            applied = True
            if impact_type == "credit_facility":
                running_extra = amount  # one-off lump sum added
            elif impact_type == "factoring":
                running_extra = amount  # one-off receivable acceleration
            elif impact_type == "term_deposit":
                running_extra = 0.0  # term deposit applies compounding, not lump sum

        if impact_type == "term_deposit" and applied:
            # 0.3% per month ≈ 0.01% per day compounded
            daily_rate = (0.003 / 30)
            days_since_effective = (pt_date - effective_date).days
            extra = base * ((1 + daily_rate) ** days_since_effective - 1)
            adjusted = base + extra
        else:
            adjusted = base + running_extra

        result.append({"date": point["date"] if isinstance(point["date"], str) else pt_date.isoformat(),
                        "projected_balance": round(adjusted, 2)})

    return result


def _build_alert_messages(
    surplus_detected: bool,
    shortfall_detected: bool,
    shortfall_date,
    shortfall_amount: float,
    shortfall_threshold: float,
    surplus_start_date,
    min_balance: float,
    confidence_overall: str,
) -> tuple[Optional[str], Optional[str]]:
    if confidence_overall == "low":
        return None, None  # suppress alerts for low-confidence forecasts

    if shortfall_detected and shortfall_date:
        alert_en = (
            f"⚠️ Cash shortfall projected on {shortfall_date}. "
            f"Your balance is expected to fall ฿{shortfall_amount:,.0f} below the recommended 2-week buffer. "
            f"Consider arranging a credit facility or accelerating receivables collection."
        )
        alert_th = (
            f"⚠️ คาดว่าจะมีเงินสดไม่เพียงพอในวันที่ {shortfall_date} "
            f"ยอดเงินของคุณอาจต่ำกว่าระดับปลอดภัย ฿{shortfall_amount:,.0f} "
            f"ควรพิจารณาจัดหาวงเงินสินเชื่อหรือเร่งรับชำระลูกหนี้"
        )
        return alert_en, alert_th

    if surplus_detected and surplus_start_date:
        alert_en = (
            f"💰 Sustained surplus detected from {surplus_start_date}. "
            f"Your projected balance exceeds 1.5× your monthly operating costs for 14+ days. "
            f"Consider deploying idle cash into a high-yield account or investment product."
        )
        alert_th = (
            f"💰 ตรวจพบเงินสดส่วนเกินอย่างต่อเนื่องตั้งแต่วันที่ {surplus_start_date} "
            f"ยอดเงินคาดการณ์เกิน 1.5 เท่าของค่าใช้จ่ายรายเดือนเป็นเวลา 14+ วัน "
            f"ควรพิจารณาลงทุนเงินสดส่วนเกินในบัญชีดอกเบี้ยสูงหรือผลิตภัณฑ์ลงทุน"
        )
        return alert_en, alert_th

    return None, None
