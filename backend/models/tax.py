from pydantic import BaseModel
from typing import Optional


class TaxBand(BaseModel):
    bracket_label: str
    taxable_amount: float
    rate: float
    tax_amount: float


class PITResult(BaseModel):
    gross_assessable: float
    total_expenses: float
    total_allowances: float
    net_taxable_income: float
    tax_by_band: list[TaxBand]
    progressive_tax: float
    wht_credit_applied: float
    net_tax_payable: float
    flags: list[str]


class CITResult(BaseModel):
    total_revenue: float
    total_deductions: float
    net_profit_taxable: float
    rate_basis: str  # "sme" | "standard"
    tax_by_band: list[TaxBand]
    pnd51_credit_applied: float
    wht_credit_applied: float
    net_tax_payable: float
    flags: list[str]


class VATResult(BaseModel):
    applicable: bool
    registration_required: bool
    indicative_net_vat_monthly: Optional[float] = None
    obligation_note: str


class SBTResult(BaseModel):
    applicable: bool
    base_rate: Optional[float] = None
    indicative_sbt_monthly: Optional[float] = None
    obligation_note: str


class TaxCalculateRequest(BaseModel):
    tax_year: int = 2025
    taxpayer_type: str  # "individual" | "juristic"
    # PIT fields
    income_by_category: Optional[dict] = None
    expense_choices: Optional[dict] = None
    allowances: Optional[dict] = None
    wht_suffered: Optional[float] = None
    # CIT fields
    is_sme: Optional[bool] = None
    paid_up_capital: Optional[float] = None
    annual_revenue: Optional[float] = None
    revenue: Optional[float] = None
    cogs: Optional[float] = None
    deductible_expenses: Optional[float] = None
    depreciation: Optional[float] = None
    dividend_income: Optional[float] = None
    non_deductible_addbacks: Optional[float] = None
    loss_carryforward: Optional[float] = None
    pnd51_prepayment: Optional[float] = None
    # VAT/SBT
    annual_turnover: Optional[float] = None
    taxable_sales: Optional[float] = None
    taxable_purchases: Optional[float] = None
    is_vat_registered: Optional[bool] = None
    activity_type: Optional[str] = None
    gross_receipts: Optional[float] = None
    is_sbt_registered: Optional[bool] = None


class TaxSessionResponse(BaseModel):
    session_id: str
    taxpayer_type: str
    status: str  # "ready" | "needs_input"
    prefilled_fields: dict
    disclaimer: str


class TaxCalculateResponse(BaseModel):
    session_id: str
    taxpayer_type: str
    pit_result: Optional[PITResult] = None
    cit_result: Optional[CITResult] = None
    vat_result: Optional[VATResult] = None
    sbt_result: Optional[SBTResult] = None
    disclaimer: str
    handoff_to_upsell: Optional[dict] = None
