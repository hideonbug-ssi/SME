"""
Tax Agent (AIWSRT-4) — conversational tax calculation assistant.

Single-turn PoC: takes income inputs, loads tax_rules_2025.json once,
calls the deterministic tax_engine tools, returns result + AIWSRT-6 handoff.
"""
import json
import logging
import uuid
from pathlib import Path
from typing import Optional

from config import settings
from services.tax_engine import calc_pit, calc_cit, check_vat, check_sbt
from models.tax import (
    TaxSessionResponse, TaxCalculateResponse, PITResult, CITResult, VATResult, SBTResult, TaxBand
)

logger = logging.getLogger(__name__)

RULES_FILE = Path(__file__).parent.parent / "mock_data" / "tax_rules_2025.json"
DISCLAIMER = (
    "This output is for guidance only — it is not a tax filing and does not constitute "
    "certified tax advice. Please verify all figures with a qualified Thai tax professional "
    "before filing."
)

# In-memory session store
_sessions: dict[str, dict] = {}


def _load_tax_rules() -> dict:
    with open(RULES_FILE) as f:
        return json.load(f)


def _dataclass_to_model(dc_result, model_class, band_class):
    """Convert tax_engine dataclass result to Pydantic model."""
    bands = [
        band_class(
            bracket_label=b.bracket_label,
            taxable_amount=b.taxable_amount,
            rate=b.rate,
            tax_amount=b.tax_amount,
        )
        for b in dc_result.tax_by_band
    ]
    data = {k: v for k, v in dc_result.__dict__.items() if k != "tax_by_band"}
    data["tax_by_band"] = bands
    return model_class(**data)


async def create_tax_session(taxpayer_type: Optional[str] = None) -> TaxSessionResponse:
    """
    Start a tax session. Derives taxpayer type if not provided (PoC: use passed value).
    Pre-fills illustrative figures from the mock ledger.
    """
    session_id = str(uuid.uuid4())
    if not taxpayer_type:
        # PoC default: individual for demo
        taxpayer_type = "individual"
        logger.info("Taxpayer type not provided — defaulting to 'individual' for demo")

    # Pre-filled from mock ledger (illustrative figures)
    prefilled = {
        "income_by_category": {"40_1_employment": 615000.0},
        "allowances": {"personal": 60000},
        "wht_suffered": 0.0,
        "annual_turnover": 615000.0,
    }

    _sessions[session_id] = {
        "session_id": session_id,
        "taxpayer_type": taxpayer_type,
        "prefilled": prefilled,
    }

    return TaxSessionResponse(
        session_id=session_id,
        taxpayer_type=taxpayer_type,
        status="ready",
        prefilled_fields=prefilled,
        disclaimer=DISCLAIMER,
    )


async def calculate_tax(session_id: str, request_data: dict) -> TaxCalculateResponse:
    """
    Run the tax calculation for the given session.
    Returns PIT or CIT result + VAT or SBT (never both VAT and SBT).
    """
    session = _sessions.get(session_id)
    if not session:
        raise KeyError(f"Session {session_id} not found")

    tax_rules = _load_tax_rules()
    taxpayer_type = session["taxpayer_type"]
    prefilled = session["prefilled"]

    # Merge prefilled with any overrides from request_data
    income_by_category = request_data.get("income_by_category", prefilled.get("income_by_category", {}))
    allowances = request_data.get("allowances", prefilled.get("allowances", {}))
    wht_suffered = request_data.get("wht_suffered", prefilled.get("wht_suffered", 0.0))
    annual_turnover = request_data.get("annual_turnover", prefilled.get("annual_turnover", 0.0))

    pit_result_model = None
    cit_result_model = None
    vat_result_model = None
    sbt_result_model = None
    handoff = None

    if taxpayer_type == "individual":
        pit_dc = calc_pit(
            tax_rules=tax_rules,
            tax_year=request_data.get("tax_year", 2025),
            income_by_category=income_by_category,
            expense_choices=request_data.get("expense_choices", {}),
            allowances=allowances,
            wht_suffered=wht_suffered,
        )
        pit_result_model = PITResult(
            gross_assessable=pit_dc.gross_assessable,
            total_expenses=pit_dc.total_expenses,
            total_allowances=pit_dc.total_allowances,
            net_taxable_income=pit_dc.net_taxable_income,
            tax_by_band=[TaxBand(bracket_label=b.bracket_label, taxable_amount=b.taxable_amount, rate=b.rate, tax_amount=b.tax_amount) for b in pit_dc.tax_by_band],
            progressive_tax=pit_dc.progressive_tax,
            wht_credit_applied=pit_dc.wht_credit_applied,
            net_tax_payable=pit_dc.net_tax_payable,
            flags=pit_dc.flags,
        )

        # VAT check (SBT is mutually exclusive — PoC assumes not SBT)
        activity_type = request_data.get("activity_type")
        if activity_type and activity_type in tax_rules["sbt"]["applicable_activities"]:
            sbt_dc = check_sbt(tax_rules, 2025, activity_type=activity_type, gross_receipts=annual_turnover)
            sbt_result_model = SBTResult(applicable=sbt_dc.applicable, base_rate=sbt_dc.base_rate, indicative_sbt_monthly=sbt_dc.indicative_sbt_monthly, obligation_note=sbt_dc.obligation_note)
        else:
            vat_dc = check_vat(tax_rules, 2025, annual_turnover=annual_turnover, is_registered=request_data.get("is_vat_registered"))
            vat_result_model = VATResult(applicable=vat_dc.applicable, registration_required=vat_dc.registration_required, indicative_net_vat_monthly=vat_dc.indicative_net_vat_monthly, obligation_note=vat_dc.obligation_note)

        # Handoff to AIWSRT-6 if there's investable surplus (SSF headroom)
        ssf_cap = tax_rules["pit"]["personal_allowances"]["ssf_max_absolute"]
        ssf_used = allowances.get("ssf", 0.0)
        ssf_headroom = max(ssf_cap - ssf_used, 0.0)
        if ssf_headroom > 0 and pit_dc.net_tax_payable > 0:
            handoff = {
                "trigger_context": "tax_advisory",
                "ssf_headroom_thb": ssf_headroom,
                "net_tax_payable": pit_dc.net_tax_payable,
                "taxpayer_type": "individual",
            }

    else:  # juristic
        cit_dc = calc_cit(
            tax_rules=tax_rules,
            tax_year=request_data.get("tax_year", 2025),
            is_sme=request_data.get("is_sme", True),
            paid_up_capital=request_data.get("paid_up_capital", 3000000.0),
            annual_revenue=request_data.get("annual_revenue", annual_turnover),
            revenue=request_data.get("revenue", annual_turnover),
            cogs=request_data.get("cogs", 0.0),
            deductible_expenses=request_data.get("deductible_expenses", 0.0),
            depreciation=request_data.get("depreciation", 0.0),
            dividend_income=request_data.get("dividend_income", 0.0),
            non_deductible_addbacks=request_data.get("non_deductible_addbacks", 0.0),
            loss_carryforward=request_data.get("loss_carryforward", 0.0),
            pnd51_prepayment=request_data.get("pnd51_prepayment", 0.0),
            wht_suffered=wht_suffered,
        )
        cit_result_model = CITResult(
            total_revenue=cit_dc.total_revenue,
            total_deductions=cit_dc.total_deductions,
            net_profit_taxable=cit_dc.net_profit_taxable,
            rate_basis=cit_dc.rate_basis,
            tax_by_band=[TaxBand(bracket_label=b.bracket_label, taxable_amount=b.taxable_amount, rate=b.rate, tax_amount=b.tax_amount) for b in cit_dc.tax_by_band],
            pnd51_credit_applied=cit_dc.pnd51_credit_applied,
            wht_credit_applied=cit_dc.wht_credit_applied,
            net_tax_payable=cit_dc.net_tax_payable,
            flags=cit_dc.flags,
        )
        if cit_dc.net_tax_payable > 0:
            handoff = {
                "trigger_context": "tax_advisory",
                "net_tax_payable": cit_dc.net_tax_payable,
                "taxpayer_type": "juristic",
            }

    return TaxCalculateResponse(
        session_id=session_id,
        taxpayer_type=taxpayer_type,
        pit_result=pit_result_model,
        cit_result=cit_result_model,
        vat_result=vat_result_model,
        sbt_result=sbt_result_model,
        disclaimer=DISCLAIMER,
        handoff_to_upsell=handoff,
    )
