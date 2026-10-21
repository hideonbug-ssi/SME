"""
Demo scenario state — holds the active scenario in memory and provides
scenario-specific raw data for each scenario so the real agent pipeline
runs with correct inputs and produces real timing + live trace events.
"""
import json
import math
import os
from datetime import date, timedelta

_MOCK_DATA_DIR = os.path.join(os.path.dirname(__file__), "mock_data")


def _load_base_data() -> tuple[dict, list, list, list]:
    """Load the base WireMock mock data files once at startup."""
    with open(os.path.join(_MOCK_DATA_DIR, "accounts.json")) as f:
        accounts = json.load(f)
    with open(os.path.join(_MOCK_DATA_DIR, "transactions.json")) as f:
        txns = json.load(f)["transactions"]
    with open(os.path.join(_MOCK_DATA_DIR, "invoices_payable.json")) as f:
        payables = json.load(f)["invoices"]
    with open(os.path.join(_MOCK_DATA_DIR, "invoices_receivable.json")) as f:
        receivables = json.load(f)["invoices"]
    return accounts, txns, payables, receivables


try:
    _BASE_ACCOUNTS, _BASE_TXNS, _BASE_PAYABLES, _BASE_RECEIVABLES = _load_base_data()
    _RAW_DATA_AVAILABLE = True
except Exception:
    _BASE_ACCOUNTS = {}
    _BASE_TXNS: list = []
    _BASE_PAYABLES: list = []
    _BASE_RECEIVABLES: list = []
    _RAW_DATA_AVAILABLE = False


def _build_scenario_raw_data() -> dict:
    """Build scenario-specific raw datasets by mutating the base mock data."""
    if not _RAW_DATA_AVAILABLE:
        return {}

    # GREEN: remove the ฿180k scheduled payable — no large outflow → surplus
    green_txns = [t for t in _BASE_TXNS if t.get("transaction_id") != "TXN-20260726-001"]
    green_payables = [p for p in _BASE_PAYABLES if p.get("invoice_id") != "PAY-003"]

    # RED: keep ฿180k + add two more large scheduled debits; remove MegaCorp receivable
    red_extra_txns = [
        {
            "transaction_id": "TXN-20260730-RED-001",
            "account_id": "ACC-KTB-001",
            "date": "2026-07-30",
            "amount": 250000.0,
            "direction": "debit",
            "category": "scheduled_payable",
            "description": "Quarterly Property Lease — PropertyLandlord Co",
            "status": "scheduled",
            "counterparty": "PropertyLandlord Co",
        },
        {
            "transaction_id": "TXN-20260805-RED-001",
            "account_id": "ACC-KTB-001",
            "date": "2026-08-05",
            "amount": 180000.0,
            "direction": "debit",
            "category": "scheduled_payable",
            "description": "Corporate Income Tax Payment Q2-2026",
            "status": "scheduled",
            "counterparty": "Revenue Department",
        },
    ]
    red_extra_payables = [
        {
            "invoice_id": "PAY-004-RED",
            "counterparty_name": "PropertyLandlord Co",
            "amount_thb": 250000.0,
            "amount_paid_thb": 0.0,
            "due_date": "2026-07-30",
            "payment_status": "unpaid",
        },
        {
            "invoice_id": "PAY-005-RED",
            "counterparty_name": "Revenue Department",
            "amount_thb": 180000.0,
            "amount_paid_thb": 0.0,
            "due_date": "2026-08-05",
            "payment_status": "unpaid",
        },
    ]
    red_receivables = [r for r in _BASE_RECEIVABLES if r.get("invoice_id") != "RCV-001"]

    # OVERDUE: same cashflow as yellow but MegaCorp receivable is marked overdue
    # (due date in the past → forecast engine won't count it as future credit)
    overdue_receivables = [
        {**r, "due_date": "2026-06-01", "payment_status": "overdue"}
        if r.get("invoice_id") == "RCV-001"
        else r
        for r in _BASE_RECEIVABLES
    ]

    return {
        "green": {
            "accounts": _BASE_ACCOUNTS,
            "transactions": green_txns,
            "payables": green_payables,
            "receivables": _BASE_RECEIVABLES,
        },
        "red": {
            "accounts": _BASE_ACCOUNTS,
            "transactions": _BASE_TXNS + red_extra_txns,
            "payables": _BASE_PAYABLES + red_extra_payables,
            "receivables": red_receivables,
        },
        "overdue": {
            "accounts": _BASE_ACCOUNTS,
            "transactions": _BASE_TXNS,
            "payables": _BASE_PAYABLES,
            "receivables": overdue_receivables,
        },
    }


_SCENARIO_RAW_DATA = _build_scenario_raw_data()

BASE_DATE = date(2026, 7, 14)
HIST_START = date(2026, 4, 15)  # 90 days before BASE_DATE


def _date_str(offset_days: int) -> str:
    return (BASE_DATE + timedelta(days=offset_days)).isoformat()


def _hist_date_str(offset_days: int) -> str:
    """offset_days from HIST_START (2026-04-15)."""
    return (HIST_START + timedelta(days=offset_days)).isoformat()


def _historical_data_points() -> list[dict]:
    """
    90 daily points from 2026-04-15 to 2026-07-13.
    Start at ฿160,000, grow to ฿280,000 with realistic ups and downs.
    Uses a sinusoidal overlay on a linear trend to simulate cash rhythm.
    """
    points = []
    total_days = (BASE_DATE - HIST_START).days  # 90
    for i in range(total_days):
        # Linear trend from 160k to 280k
        trend = 160000 + (280000 - 160000) * i / (total_days - 1)
        # Sinusoidal noise: ±15k with ~15-day business cycle
        noise = 15000 * math.sin(2 * math.pi * i / 15)
        # Additional smaller weekly pattern ±5k
        weekly = 5000 * math.sin(2 * math.pi * i / 7)
        balance = trend + noise + weekly
        points.append({
            "date": _hist_date_str(i),
            "actual_balance": round(balance, 2),
        })
    return points


def _green_data_points() -> list[dict]:
    """91 points linearly increasing from 280,000 to 380,000."""
    return [
        {
            "date": _date_str(i),
            "projected_balance": round(280000 + (100000 * i / 90), 2),
            "confidence": "high",
        }
        for i in range(91)
    ]


def _yellow_data_points() -> list[dict]:
    """91 points: start 280,000 → dip to 71,313 at index 12 → recover to 302,650 at index 90."""
    points = []
    for i in range(91):
        if i <= 12:
            balance = 280000 + (71313 - 280000) * i / 12
        else:
            balance = 71313 + (302650 - 71313) * (i - 12) / (90 - 12)
        points.append({
            "date": _date_str(i),
            "projected_balance": round(balance, 2),
            "confidence": "high",
        })
    return points


def _red_data_points() -> list[dict]:
    """91 points: start 280,000 → crash to -60,000 at index 18 → slow recovery to 100,000."""
    points = []
    for i in range(91):
        if i <= 18:
            balance = 280000 + (-60000 - 280000) * i / 18
        else:
            balance = -60000 + (100000 - (-60000)) * (i - 18) / (90 - 18)
        points.append({
            "date": _date_str(i),
            "projected_balance": round(balance, 2),
            "confidence": "high",
        })
    return points


def _with_product_green() -> list[dict]:
    """Green: apply 0.3% monthly interest (term deposit) from day 0."""
    daily_rate = 0.003 / 30
    points = []
    for i in range(91):
        base = 280000 + (100000 * i / 90)
        extra = base * ((1 + daily_rate) ** i - 1)
        points.append({
            "date": _date_str(i),
            "projected_balance": round(base + extra, 2),
        })
    return points


def _with_product_yellow() -> list[dict]:
    """Yellow: add ฿63,962 at day 6 (2026-07-20), balance floors at ~135,000."""
    points = []
    extra = 0.0
    for i in range(91):
        if i == 6:
            extra = 63962.0
        if i <= 12:
            base = 280000 + (71313 - 280000) * i / 12
        else:
            base = 71313 + (302650 - 71313) * (i - 12) / (90 - 12)
        adjusted = base + extra
        # Floor at 135,000 for the dip period (days 6–20)
        if 6 <= i <= 20:
            adjusted = max(adjusted, 135000.0)
        points.append({
            "date": _date_str(i),
            "projected_balance": round(adjusted, 2),
        })
    return points


def _with_product_red() -> list[dict]:
    """Red: add ฿120,000 at day 14 (2026-07-28), balance dips only to ~80,000."""
    points = []
    extra = 0.0
    for i in range(91):
        if i == 14:
            extra = 120000.0
        if i <= 18:
            base = 280000 + (-60000 - 280000) * i / 18
        else:
            base = -60000 + (100000 - (-60000)) * (i - 18) / (90 - 18)
        adjusted = base + extra
        # Floor at 80,000 after factoring kicks in
        if i >= 14:
            adjusted = max(adjusted, 80000.0)
        points.append({
            "date": _date_str(i),
            "projected_balance": round(adjusted, 2),
        })
    return points


def _with_product_overdue() -> list[dict]:
    """Overdue: same as yellow."""
    return _with_product_yellow()


# Pre-bake all data points once at import time.
_HIST_POINTS = _historical_data_points()
_GREEN_POINTS = _green_data_points()
_YELLOW_POINTS = _yellow_data_points()
_RED_POINTS = _red_data_points()
_OVERDUE_POINTS = _yellow_data_points()  # same as yellow
_WITH_PRODUCT_GREEN = _with_product_green()
_WITH_PRODUCT_YELLOW = _with_product_yellow()
_WITH_PRODUCT_RED = _with_product_red()
_WITH_PRODUCT_OVERDUE = _with_product_overdue()

SCENARIO_FORECAST: dict[str, dict] = {
    "green": {
        "sme_id": "TH-SME-001",
        "data_points": _GREEN_POINTS,
        "historical_data_points": _HIST_POINTS,
        "with_product_data_points": _WITH_PRODUCT_GREEN,
        "product_impact_description": "KTB Business Term Deposit: 0.3% per month on ฿280,000 surplus",
        "summary": {
            "min_point": 280000,
            "min_date": "2026-07-14",
            "max_point": 380000,
            "max_date": "2026-10-12",
            "key_drivers": [
                "Strong recurring revenue inflows averaging ฿90,000/month",
                "All payables current, no large obligations due",
                "Accumulated surplus presents investment opportunity",
            ],
        },
        "rolling_avg_monthly_outflow": 75000.0,
        "confidence_overall": "high",
        "updated_at": "2026-07-14T00:00:00Z",
        "shortfall_detected": False,
        "surplus_detected": True,
        "handoff_payload": {
            "trigger_context": "opportunity",
            "amount_thb": None,
            "date_of_event": None,
        },
        "alert_message": "✅ Cash position is healthy. A surplus of ฿100,000 is projected by end of 90-day window.",
    },
    "yellow": {
        "sme_id": "TH-SME-001",
        "data_points": _YELLOW_POINTS,
        "historical_data_points": _HIST_POINTS,
        "with_product_data_points": _WITH_PRODUCT_YELLOW,
        "product_impact_description": "KTB Business Credit Line (SCF): ฿63,962 available from 2026-07-20 — floors shortfall dip at ฿135,000",
        "summary": {
            "min_point": 71313,
            "min_date": "2026-07-26",
            "max_point": 302650,
            "max_date": "2026-10-12",
            "key_drivers": [
                "Payment due: Large Supplier Invoice CIS-INV-2026-0234 (฿180,000) on 2026-07-26",
                "Expected receipt: MegaCorp Thailand Ltd (฿120,000) on 2026-08-01",
                "Payment due: TechSupplies Co Ltd (฿45,000) on 2026-07-20",
            ],
        },
        "rolling_avg_monthly_outflow": 120000.0,
        "confidence_overall": "high",
        "updated_at": "2026-07-14T00:00:00Z",
        "shortfall_detected": True,
        "surplus_detected": False,
        "handoff_payload": {
            "trigger_context": "shortfall_yellow",
            "amount_thb": 63961.67,
            "date_of_event": "2026-07-26",
        },
        "alert_message": "⚠️ Cash shortfall projected on 2026-07-26. Balance expected to fall ฿63,962 below the recommended 2-week buffer.",
    },
    "red": {
        "sme_id": "TH-SME-001",
        "data_points": _RED_POINTS,
        "historical_data_points": _HIST_POINTS,
        "with_product_data_points": _WITH_PRODUCT_RED,
        "product_impact_description": "Invoice factoring: accelerate MegaCorp receivable (฿120,000) — balance floors at ฿80,000",
        "summary": {
            "min_point": -60000,
            "min_date": "2026-08-01",
            "max_point": 280000,
            "max_date": "2026-07-14",
            "key_drivers": [
                "CRITICAL: Multiple large payables due simultaneously — ฿450,000 total obligations",
                "Receivable default: MegaCorp overdue 60 days (฿120,000 at risk)",
                "Operating expenses elevated — average monthly burn ฿185,000",
            ],
        },
        "rolling_avg_monthly_outflow": 185000.0,
        "confidence_overall": "high",
        "updated_at": "2026-07-14T00:00:00Z",
        "shortfall_detected": True,
        "surplus_detected": False,
        "handoff_payload": {
            "trigger_context": "shortfall_red",
            "amount_thb": 340000,
            "date_of_event": "2026-08-01",
        },
        "alert_message": "🚨 CRITICAL: Severe cash shortfall of ฿340,000 projected by 2026-08-01. Immediate action required.",
    },
    "overdue": {
        "sme_id": "TH-SME-001",
        "data_points": _OVERDUE_POINTS,
        "historical_data_points": _HIST_POINTS,
        "with_product_data_points": _WITH_PRODUCT_OVERDUE,
        "product_impact_description": "KTB Business Credit Line (SCF): ฿63,962 available from 2026-07-20 — covers shortfall while MegaCorp collection escalated",
        "summary": {
            "min_point": 71313,
            "min_date": "2026-07-26",
            "max_point": 302650,
            "max_date": "2026-10-12",
            "key_drivers": [
                "Payment due: Large Supplier Invoice CIS-INV-2026-0234 (฿180,000) on 2026-07-26",
                "Expected receipt: MegaCorp Thailand Ltd (฿120,000) on 2026-08-01",
                "Payment due: TechSupplies Co Ltd (฿45,000) on 2026-07-20",
            ],
        },
        "rolling_avg_monthly_outflow": 120000.0,
        "confidence_overall": "high",
        "updated_at": "2026-07-14T00:00:00Z",
        "shortfall_detected": True,
        "surplus_detected": False,
        "handoff_payload": {
            "trigger_context": "shortfall_yellow",
            "amount_thb": 63961.67,
            "date_of_event": "2026-07-26",
        },
        "alert_message": "⚠️ Cash shortfall projected on 2026-07-26. Balance expected to fall ฿63,962 below the recommended 2-week buffer.",
    },
}

SCENARIO_SHORTFALL: dict[str, dict] = {
    "green": {
        "tier": "green",
        "shortfall_amount_thb": None,
        "shortfall_date": None,
        "recovery_plan": None,
    },
    "yellow": {
        "tier": "yellow",
        "shortfall_amount_thb": 63961.67,
        "shortfall_date": "2026-07-26",
        "recovery_plan": (
            "Accelerate receivables collection or arrange a short-term credit facility. "
            "Lending products withheld — NPL guard triggered (cashflow coverage insufficient)."
        ),
    },
    "red": {
        "tier": "red",
        "shortfall_amount_thb": 340000,
        "shortfall_date": "2026-08-01",
        "recovery_plan": (
            "URGENT: (1) Contact creditors immediately for payment deferral. "
            "(2) Pursue emergency invoice factoring for MegaCorp receivable. "
            "(3) Consider KTB Business Cash Flow (SCF) — repayability assessment passed for factoring products."
        ),
    },
    "overdue": {
        "tier": "yellow",
        "shortfall_amount_thb": 63961.67,
        "shortfall_date": "2026-07-26",
        "recovery_plan": (
            "MegaCorp Thailand Ltd invoice overdue 45 days (฿120,000). "
            "Sending payment reminder and escalating to relationship manager."
        ),
    },
}


SCENARIO_AGENT_TRACE: dict[str, dict] = {
    "green": {
        "scenario": "green",
        "timestamp": "2026-07-14T00:00:00Z",
        "steps": [
            {
                "step": 1,
                "agent": "ForecastAgent",
                "action": "fetch_transactions",
                "input": {"account_id": "ACC-KTB-001", "days": 90},
                "output": {
                    "transaction_count": 63,
                    "total_inflow": 540000,
                    "total_outflow": 225000,
                    "date_range": "2026-04-15 to 2026-07-14",
                },
                "duration_ms": 42,
            },
            {
                "step": 2,
                "agent": "ForecastAgent",
                "action": "compute_projection",
                "input": {"horizon_days": 90, "opening_balance": 280000},
                "output": {
                    "shortfall_detected": False,
                    "surplus_detected": True,
                    "surplus_start_date": "2026-07-14",
                    "surplus_amount": 100000,
                    "tier": "green",
                },
                "duration_ms": 10,
            },
            {
                "step": 3,
                "agent": "ShortfallAgent",
                "action": "evaluate_tier",
                "input": {"shortfall_amount": 0, "cashflow_coverage_ratio": 1.80},
                "output": {
                    "tier": "green",
                    "npg_guard": "not_triggered",
                    "lending_products_blocked": False,
                },
                "duration_ms": 6,
            },
            {
                "step": 4,
                "agent": "RecommendationEngine",
                "action": "score_products",
                "input": {"trigger_context": "opportunity", "excluded_categories": []},
                "output": {
                    "products_evaluated": 11,
                    "threshold": 0.70,
                    "winner": "KTB Business Term Deposit",
                    "score": 0.91,
                },
                "duration_ms": 13,
            },
        ],
        "raw_inputs": {
            "account_balance": 280000,
            "transactions_30d_summary": {"inflow": 180000, "outflow": 75000, "net": 105000},
            "receivables": [],
            "payables": [],
        },
        "final_outputs": {
            "forecast_tier": "green",
            "shortfall_amount_thb": 0,
            "recommended_product": "KTB Business Term Deposit",
            "relevance_score": 0.91,
            "npg_guard_status": "not_triggered",
        },
    },
    "yellow": {
        "scenario": "yellow",
        "timestamp": "2026-07-14T00:00:00Z",
        "steps": [
            {
                "step": 1,
                "agent": "ForecastAgent",
                "action": "fetch_transactions",
                "input": {"account_id": "ACC-KTB-001", "days": 90},
                "output": {
                    "transaction_count": 63,
                    "total_inflow": 540000,
                    "total_outflow": 270550,
                    "date_range": "2026-04-15 to 2026-07-14",
                },
                "duration_ms": 45,
            },
            {
                "step": 2,
                "agent": "ForecastAgent",
                "action": "compute_projection",
                "input": {"horizon_days": 90, "opening_balance": 280000},
                "output": {
                    "shortfall_detected": True,
                    "shortfall_amount": 63961.67,
                    "shortfall_date": "2026-07-26",
                    "tier": "yellow",
                },
                "duration_ms": 12,
            },
            {
                "step": 3,
                "agent": "ShortfallAgent",
                "action": "evaluate_tier",
                "input": {"shortfall_amount": 63961.67, "cashflow_coverage_ratio": 0.88},
                "output": {
                    "tier": "yellow",
                    "npg_guard": "triggered",
                    "lending_products_blocked": True,
                },
                "duration_ms": 8,
            },
            {
                "step": 4,
                "agent": "RecommendationEngine",
                "action": "score_products",
                "input": {"trigger_context": "shortfall_yellow", "excluded_categories": ["lending"]},
                "output": {
                    "products_evaluated": 11,
                    "threshold": 0.70,
                    "winner": "KTB Business Credit Line (SCF)",
                    "score": 0.85,
                },
                "duration_ms": 15,
            },
        ],
        "raw_inputs": {
            "account_balance": 280000,
            "transactions_30d_summary": {"inflow": 180000, "outflow": 135000, "net": 45000},
            "receivables": [
                {"counterparty": "MegaCorp Thailand Ltd", "amount": 120000, "due": "2026-08-01"}
            ],
            "payables": [
                {"counterparty": "Large Supplier", "amount": 180000, "due": "2026-07-26"},
                {"counterparty": "TechSupplies Co Ltd", "amount": 45000, "due": "2026-07-20"},
            ],
        },
        "final_outputs": {
            "forecast_tier": "yellow",
            "shortfall_amount_thb": 63961.67,
            "recommended_product": "KTB Business Credit Line (SCF)",
            "relevance_score": 0.85,
            "npg_guard_status": "lending_blocked_non_lending_recommended",
        },
    },
    "red": {
        "scenario": "red",
        "timestamp": "2026-07-14T00:00:00Z",
        "steps": [
            {
                "step": 1,
                "agent": "ForecastAgent",
                "action": "fetch_transactions",
                "input": {"account_id": "ACC-KTB-001", "days": 90},
                "output": {
                    "transaction_count": 63,
                    "total_inflow": 540000,
                    "total_outflow": 555000,
                    "date_range": "2026-04-15 to 2026-07-14",
                },
                "duration_ms": 48,
            },
            {
                "step": 2,
                "agent": "ForecastAgent",
                "action": "compute_projection",
                "input": {"horizon_days": 90, "opening_balance": 280000},
                "output": {
                    "shortfall_detected": True,
                    "shortfall_amount": 340000,
                    "shortfall_date": "2026-08-01",
                    "tier": "red",
                },
                "duration_ms": 14,
            },
            {
                "step": 3,
                "agent": "ShortfallAgent",
                "action": "evaluate_tier",
                "input": {"shortfall_amount": 340000, "cashflow_coverage_ratio": 0.51},
                "output": {
                    "tier": "red",
                    "npg_guard": "triggered",
                    "lending_products_blocked": True,
                },
                "duration_ms": 9,
            },
            {
                "step": 4,
                "agent": "RecommendationEngine",
                "action": "score_products",
                "input": {"trigger_context": "shortfall_red", "excluded_categories": ["lending"]},
                "output": {
                    "products_evaluated": 11,
                    "threshold": 0.70,
                    "winner": "KTB Business Cash Flow (Factoring)",
                    "score": 0.79,
                },
                "duration_ms": 18,
            },
        ],
        "raw_inputs": {
            "account_balance": 280000,
            "transactions_30d_summary": {"inflow": 180000, "outflow": 185000, "net": -5000},
            "receivables": [
                {"counterparty": "MegaCorp Thailand Ltd", "amount": 120000, "due": "2026-08-01", "overdue_days": 60}
            ],
            "payables": [
                {"counterparty": "Large Supplier", "amount": 180000, "due": "2026-07-26"},
                {"counterparty": "TechSupplies Co Ltd", "amount": 45000, "due": "2026-07-20"},
                {"counterparty": "PropertyLandlord Co", "amount": 225000, "due": "2026-08-01"},
            ],
        },
        "final_outputs": {
            "forecast_tier": "red",
            "shortfall_amount_thb": 340000,
            "recommended_product": "KTB Business Cash Flow (Factoring)",
            "relevance_score": 0.79,
            "npg_guard_status": "lending_blocked_factoring_recommended",
        },
    },
    "overdue": {
        "scenario": "overdue",
        "timestamp": "2026-07-14T00:00:00Z",
        "steps": [
            {
                "step": 1,
                "agent": "ForecastAgent",
                "action": "fetch_transactions",
                "input": {"account_id": "ACC-KTB-001", "days": 90},
                "output": {
                    "transaction_count": 63,
                    "total_inflow": 420000,
                    "total_outflow": 270550,
                    "date_range": "2026-04-15 to 2026-07-14",
                },
                "duration_ms": 47,
            },
            {
                "step": 2,
                "agent": "ForecastAgent",
                "action": "compute_projection",
                "input": {"horizon_days": 90, "opening_balance": 280000},
                "output": {
                    "shortfall_detected": True,
                    "shortfall_amount": 63961.67,
                    "shortfall_date": "2026-07-26",
                    "tier": "yellow",
                },
                "duration_ms": 12,
            },
            {
                "step": 3,
                "agent": "OverdueAgent",
                "action": "detect_overdue_receivables",
                "input": {"receivables": [{"counterparty": "MegaCorp Thailand Ltd", "amount": 120000}]},
                "output": {
                    "overdue_count": 1,
                    "overdue_amount_thb": 120000,
                    "oldest_overdue_days": 45,
                    "escalation_required": True,
                },
                "duration_ms": 7,
            },
            {
                "step": 4,
                "agent": "ShortfallAgent",
                "action": "evaluate_tier",
                "input": {"shortfall_amount": 63961.67, "cashflow_coverage_ratio": 0.88},
                "output": {
                    "tier": "yellow",
                    "npg_guard": "triggered",
                    "lending_products_blocked": True,
                },
                "duration_ms": 8,
            },
            {
                "step": 5,
                "agent": "RecommendationEngine",
                "action": "score_products",
                "input": {"trigger_context": "shortfall_yellow_overdue", "excluded_categories": ["lending"]},
                "output": {
                    "products_evaluated": 11,
                    "threshold": 0.70,
                    "winner": "KTB Business Credit Line (SCF)",
                    "score": 0.82,
                },
                "duration_ms": 16,
            },
        ],
        "raw_inputs": {
            "account_balance": 280000,
            "transactions_30d_summary": {"inflow": 140000, "outflow": 135000, "net": 5000},
            "receivables": [
                {
                    "counterparty": "MegaCorp Thailand Ltd",
                    "amount": 120000,
                    "due": "2026-05-30",
                    "overdue_days": 45,
                    "status": "overdue",
                }
            ],
            "payables": [
                {"counterparty": "Large Supplier", "amount": 180000, "due": "2026-07-26"},
                {"counterparty": "TechSupplies Co Ltd", "amount": 45000, "due": "2026-07-20"},
            ],
        },
        "final_outputs": {
            "forecast_tier": "yellow",
            "shortfall_amount_thb": 63961.67,
            "recommended_product": "KTB Business Credit Line (SCF)",
            "relevance_score": 0.82,
            "npg_guard_status": "lending_blocked_non_lending_recommended",
        },
    },
}


class DemoState:
    def __init__(self) -> None:
        self.active_scenario: str = "yellow"

    def get_scenario_raw_data(self) -> dict | None:
        """Return scenario-specific raw data for the agent pipeline.
        Returns None for 'yellow' (use WireMock directly for the default scenario).
        """
        if not _RAW_DATA_AVAILABLE or self.active_scenario == "yellow":
            return None
        return _SCENARIO_RAW_DATA.get(self.active_scenario)

    def get_agent_trace(self) -> dict | None:
        return SCENARIO_AGENT_TRACE.get(self.active_scenario)


demo_state = DemoState()
