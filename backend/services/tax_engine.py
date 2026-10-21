"""
Tax calculation engine for Thailand 2025 tax rules.

Pure deterministic functions — all rates, caps, and thresholds come from the
rules dict passed in (loaded from tax_rules_2025.json once per session by the
caller). Nothing is hard-coded here.

Output is guidance only — not a tax filing, not certified tax advice.

Worked examples (used in unit tests):
  PIT freelancer:
    income_by_category={"40_1_employment": 615000}, expense_choices={},
    allowances={"personal": 60000}, wht_suffered=0, tax_year=2025
    → net_tax_payable=23000

  CIT SME:
    is_sme=True, paid_up_capital=3_000_000, annual_revenue=8_000_000,
    revenue=2_000_000, cogs=1_100_000, deductible_expenses=450_000,
    depreciation=50_000, dividend_income=0, non_deductible_addbacks=0,
    loss_carryforward=0, pnd51_prepayment=0, wht_suffered=0, tax_year=2025
    → net_tax_payable=15000
"""
from typing import Optional

from models.tax import CITResult, PITResult, SBTResult, TaxBand, VATResult


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def calc_pit(
    tax_rules: dict,
    tax_year: int,
    income_by_category: dict,
    expense_choices: dict,
    allowances: dict,
    wht_suffered: float,
) -> PITResult:
    """
    Compute Thai Personal Income Tax (PIT).

    Args:
        tax_rules: full rules dict (e.g. loaded from tax_rules_2025.json).
        tax_year: tax year for reference (rules already scoped to year by caller).
        income_by_category: {category_key: gross_income_float}
            Valid keys: 40_1_employment, 40_2_freelance, 40_3_goodwill,
                        40_4_interest_dividend, 40_5_rent, 40_6_professional,
                        40_7_contract, 40_8_other
        expense_choices: reserved for future "actual" expense overrides; pass {}
            to accept standard deductions for all categories.
        allowances: {allowance_key: amount_or_count}
            Supported keys (all optional):
              personal, spouse — include key to claim (value ignored, fixed amount used)
              child_count — int, number of children
              parent_count — int, number of qualifying parents
              life_insurance, health_insurance, social_security, mortgage_interest — float
              rmf, ssf, thai_esg — float (subject to rate & absolute caps)
              donation_general, donation_edu — float (capped at % of net income)
        wht_suffered: withholding tax already deducted at source (credit against PIT).

    Returns:
        PITResult with full breakdown and net_tax_payable.
    """
    pit_rules = tax_rules["pit"]
    income_type_rules = pit_rules["income_types"]
    allowance_rules = pit_rules["personal_allowances"]
    brackets = pit_rules["tax_brackets"]
    flags: list[str] = []

    # ------------------------------------------------------------------
    # Step 1: Gross assessable income and standard expense deductions
    # ------------------------------------------------------------------
    gross_assessable = 0.0
    total_expenses = 0.0

    for category, gross_income in income_by_category.items():
        gross_assessable += gross_income

        if category not in income_type_rules:
            flags.append(
                f"Unknown income category '{category}' — no expense deduction applied."
            )
            continue

        type_rule = income_type_rules[category]
        deduction_rate: float = type_rule["expense_deduction_rate"]
        max_deduction: Optional[float] = type_rule["max_deduction"]

        std_deduction = gross_income * deduction_rate
        if max_deduction is not None:
            std_deduction = min(std_deduction, max_deduction)

        total_expenses += std_deduction

    income_after_expenses = gross_assessable - total_expenses

    # ------------------------------------------------------------------
    # Step 2: Personal allowances
    # ------------------------------------------------------------------
    total_allowances = 0.0

    # Fixed-amount allowances
    if "personal" in allowances:
        total_allowances += allowance_rules["personal"]
    if "spouse" in allowances:
        total_allowances += allowance_rules["spouse"]

    # Count-based allowances
    child_count = int(allowances.get("child_count", 0))
    if child_count > 0:
        total_allowances += child_count * allowance_rules["child_per_child"]

    parent_count = int(allowances.get("parent_count", 0))
    if parent_count > 0:
        total_allowances += parent_count * allowance_rules["parent_per_parent"]

    # Individually capped insurance / debt allowances
    for key in ("life_insurance", "health_insurance", "social_security", "mortgage_interest"):
        if key in allowances:
            cap_key = f"{key}_max"
            cap = allowance_rules.get(cap_key, float("inf"))
            total_allowances += min(float(allowances[key]), cap)

    # Investment allowances: RMF, SSF, Thai ESG — individual rate/absolute caps,
    # then a combined cap shared across all three.
    investment_total = 0.0
    investment_cfg = {
        "rmf": ("rmf_max_rate", "rmf_max_absolute"),
        "ssf": ("ssf_max_rate", "ssf_max_absolute"),
        "thai_esg": ("thai_esg_max_rate", "thai_esg_max_absolute"),
    }
    for inv_key, (rate_key, abs_key) in investment_cfg.items():
        if inv_key in allowances:
            inv_amount = float(allowances[inv_key])
            rate_cap = gross_assessable * allowance_rules[rate_key]
            abs_cap = allowance_rules[abs_key]
            investment_total += min(inv_amount, rate_cap, abs_cap)

    combined_cap = allowance_rules["combined_ssf_rmf_thai_esg_cap"]
    if investment_total > combined_cap:
        flags.append(
            f"Investment allowances (RMF/SSF/ThaiESG) capped at combined limit "
            f"฿{combined_cap:,.0f}."
        )
        investment_total = combined_cap
    total_allowances += investment_total

    # Donation allowances — capped as % of income after expenses
    donation_base = income_after_expenses
    for don_key in ("donation_general", "donation_edu"):
        if don_key in allowances:
            rate_key = f"{don_key}_max_rate"
            rate_cap = allowance_rules.get(rate_key, 0.10)
            don_cap = donation_base * rate_cap
            total_allowances += min(float(allowances[don_key]), don_cap)

    # ------------------------------------------------------------------
    # Step 3: Net taxable income
    # ------------------------------------------------------------------
    net_taxable_income = max(income_after_expenses - total_allowances, 0.0)

    # ------------------------------------------------------------------
    # Step 4: Progressive tax
    # ------------------------------------------------------------------
    tax_by_band, progressive_tax = _apply_brackets(brackets, net_taxable_income)

    # ------------------------------------------------------------------
    # Step 5: WHT credit
    # ------------------------------------------------------------------
    wht_credit_applied = min(wht_suffered, progressive_tax)
    net_tax_payable = max(progressive_tax - wht_credit_applied, 0.0)

    return PITResult(
        gross_assessable=round(gross_assessable, 2),
        total_expenses=round(total_expenses, 2),
        total_allowances=round(total_allowances, 2),
        net_taxable_income=round(net_taxable_income, 2),
        tax_by_band=tax_by_band,
        progressive_tax=round(progressive_tax, 2),
        wht_credit_applied=round(wht_credit_applied, 2),
        net_tax_payable=round(net_tax_payable, 2),
        flags=flags,
    )


def calc_cit(
    tax_rules: dict,
    tax_year: int,
    is_sme: bool,
    paid_up_capital: float,
    annual_revenue: float,
    revenue: float,
    cogs: float,
    deductible_expenses: float,
    depreciation: float,
    dividend_income: float,
    non_deductible_addbacks: float,
    loss_carryforward: float,
    pnd51_prepayment: float,
    wht_suffered: float,
) -> CITResult:
    """
    Compute Thai Corporate Income Tax (CIT).

    SME qualification: is_sme=True AND paid_up_capital <= 5,000,000 AND
    annual_revenue <= 30,000,000. If any threshold is exceeded, standard rate applies.

    Dividend income received from a Thai company is excluded from the taxable base
    (already taxed at source). It is included in total_revenue for informational
    purposes only.

    Args:
        tax_rules: full rules dict.
        tax_year: tax year for reference.
        is_sme: caller-declared SME status (thresholds still verified here).
        paid_up_capital: registered paid-up capital in THB.
        annual_revenue: full-year revenue for SME threshold check.
        revenue: revenue to use in this calculation period.
        cogs: cost of goods sold.
        deductible_expenses: other allowable operating expenses.
        depreciation: tax-deductible depreciation.
        dividend_income: dividend income received (excluded from taxable base).
        non_deductible_addbacks: disallowable expenses to add back to taxable profit.
        loss_carryforward: carried-forward tax losses to deduct (max 5 years).
        pnd51_prepayment: half-year estimated tax already paid (PND 51 credit).
        wht_suffered: withholding tax suffered (credit after PND 51).

    Returns:
        CITResult with full breakdown and net_tax_payable.
    """
    cit_rules = tax_rules["cit"]
    sme_thresholds = cit_rules["sme_thresholds"]
    flags: list[str] = []

    # ------------------------------------------------------------------
    # Step 1: SME eligibility check
    # ------------------------------------------------------------------
    qualifies_sme = (
        is_sme
        and paid_up_capital <= sme_thresholds["max_paid_up_capital"]
        and annual_revenue <= sme_thresholds["max_annual_revenue"]
    )
    rate_basis = "sme" if qualifies_sme else "standard"

    if is_sme and not qualifies_sme:
        flags.append(
            "SME flag set but one or more thresholds exceeded "
            "(paid-up capital > ฿5,000,000 or annual revenue > ฿30,000,000) — "
            "standard 20% rate applies."
        )

    # ------------------------------------------------------------------
    # Step 2: Taxable profit
    # ------------------------------------------------------------------
    # Dividend income is excluded from the CIT taxable base (Thai company assumption).
    if dividend_income > 0:
        flags.append(
            "Dividend income excluded from CIT taxable base "
            "(assumption: received from a Thai company — already taxed at source)."
        )

    net_profit_before_adjustments = revenue - cogs - deductible_expenses - depreciation
    net_profit_taxable = max(
        net_profit_before_adjustments + non_deductible_addbacks - loss_carryforward,
        0.0,
    )

    total_revenue = revenue + dividend_income
    total_deductions = cogs + deductible_expenses + depreciation

    # ------------------------------------------------------------------
    # Step 3: Apply tax brackets
    # ------------------------------------------------------------------
    if qualifies_sme:
        brackets = cit_rules["sme_brackets"]
    else:
        # Single flat rate expressed as a one-bracket list for uniform handling
        brackets = [{"min": 0, "max": None, "rate": cit_rules["standard_rate"]}]

    tax_by_band, total_tax = _apply_brackets(brackets, net_profit_taxable)

    # ------------------------------------------------------------------
    # Step 4: Credits (PND 51 first, then WHT)
    # ------------------------------------------------------------------
    pnd51_credit_applied = min(pnd51_prepayment, total_tax)
    remaining_after_pnd51 = max(total_tax - pnd51_credit_applied, 0.0)
    wht_credit_applied = min(wht_suffered, remaining_after_pnd51)
    net_tax_payable = max(remaining_after_pnd51 - wht_credit_applied, 0.0)

    return CITResult(
        total_revenue=round(total_revenue, 2),
        total_deductions=round(total_deductions, 2),
        net_profit_taxable=round(net_profit_taxable, 2),
        rate_basis=rate_basis,
        tax_by_band=tax_by_band,
        pnd51_credit_applied=round(pnd51_credit_applied, 2),
        wht_credit_applied=round(wht_credit_applied, 2),
        net_tax_payable=round(net_tax_payable, 2),
        flags=flags,
    )


def check_vat(
    tax_rules: dict,
    tax_year: int,
    annual_turnover: float,
    taxable_sales: Optional[float] = None,
    taxable_purchases: Optional[float] = None,
    is_registered: Optional[bool] = None,
) -> VATResult:
    """
    Assess VAT obligations.

    VAT and SBT are mutually exclusive — do not call both for the same entity.

    Args:
        tax_rules: full rules dict.
        tax_year: tax year for reference.
        annual_turnover: total annual revenue from VAT-able sales.
        taxable_sales: annual taxable sales (for monthly output-VAT estimate).
        taxable_purchases: annual taxable purchases (for monthly input-VAT estimate).
        is_registered: True if the entity is already VAT-registered.

    Returns:
        VATResult with registration status and monthly net VAT estimate.
    """
    vat_rules = tax_rules["vat"]
    threshold: float = vat_rules["registration_threshold"]
    rate: float = vat_rules["standard_rate"]

    already_registered = is_registered is True
    registration_required = (annual_turnover > threshold) and not already_registered

    indicative_net_vat_monthly: Optional[float] = None
    if already_registered and taxable_sales is not None and taxable_purchases is not None:
        monthly_output = (taxable_sales / 12.0) * rate
        monthly_input = (taxable_purchases / 12.0) * rate
        indicative_net_vat_monthly = round(monthly_output - monthly_input, 2)

    # Determine obligation note
    if not already_registered and annual_turnover <= threshold:
        applicable = False
        obligation_note = (
            f"Annual turnover ฿{annual_turnover:,.0f} is below the VAT registration "
            f"threshold of ฿{threshold:,.0f}. Registration is not required but is optional."
        )
    elif registration_required:
        applicable = True
        obligation_note = (
            f"Annual turnover ฿{annual_turnover:,.0f} exceeds the ฿{threshold:,.0f} "
            f"threshold. VAT registration is mandatory — file Form PP.01 with the "
            f"Revenue Department."
        )
    else:
        applicable = True
        if indicative_net_vat_monthly is not None:
            obligation_note = (
                f"VAT registered. File monthly PP.30 returns. "
                f"Indicative net VAT payable: ฿{indicative_net_vat_monthly:,.0f}/month."
            )
        else:
            obligation_note = "VAT registered. File monthly PP.30 returns."

    return VATResult(
        applicable=applicable,
        registration_required=registration_required,
        indicative_net_vat_monthly=indicative_net_vat_monthly,
        obligation_note=obligation_note,
    )


def check_sbt(
    tax_rules: dict,
    tax_year: int,
    activity_type: str,
    gross_receipts: Optional[float] = None,
    is_registered: Optional[bool] = None,
) -> SBTResult:
    """
    Assess Specific Business Tax (SBT) obligations.

    SBT and VAT are mutually exclusive — do not call both for the same entity.
    SBT applies to: banking, finance, life_insurance, pawn_brokerage,
    real_estate_sale. All other activity types are not subject to SBT.

    Args:
        tax_rules: full rules dict.
        tax_year: tax year for reference.
        activity_type: one of the SBT-liable activity strings.
        gross_receipts: annual gross receipts (for monthly SBT estimate).
        is_registered: True if already SBT-registered (informational only).

    Returns:
        SBTResult with applicability, rate, and monthly estimate.
    """
    sbt_rules = tax_rules["sbt"]
    applicable_activities: list[str] = sbt_rules["applicable_activities"]
    rates: dict = sbt_rules["rates"]

    if activity_type not in applicable_activities:
        return SBTResult(
            applicable=False,
            base_rate=None,
            indicative_sbt_monthly=None,
            obligation_note=(
                f"Activity '{activity_type}' is not subject to SBT. "
                f"Standard VAT rules may apply instead."
            ),
        )

    base_rate = rates[activity_type]

    indicative_sbt_monthly: Optional[float] = None
    if gross_receipts is not None:
        indicative_sbt_monthly = round((gross_receipts / 12.0) * base_rate, 2)

    if indicative_sbt_monthly is not None:
        obligation_note = (
            f"SBT applies to '{activity_type}' at {base_rate * 100:.1f}% of gross receipts. "
            f"Indicative monthly SBT: ฿{indicative_sbt_monthly:,.0f}. "
            f"File monthly PT.40 returns with the Revenue Department."
        )
    else:
        obligation_note = (
            f"SBT applies to '{activity_type}' at {base_rate * 100:.1f}% of gross receipts. "
            f"File monthly PT.40 returns with the Revenue Department."
        )

    return SBTResult(
        applicable=True,
        base_rate=base_rate,
        indicative_sbt_monthly=indicative_sbt_monthly,
        obligation_note=obligation_note,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _apply_brackets(brackets: list[dict], taxable_amount: float) -> tuple[list[TaxBand], float]:
    """
    Apply a progressive bracket schedule to taxable_amount.

    Each bracket dict must contain:
        min  (int)  — bracket floor (inclusive). The first bracket should have min=0.
        max  (int|None) — bracket ceiling (inclusive). None means unbounded.
        rate (float)   — marginal rate for this bracket.

    The amount taxable in a bracket is:
        min(taxable_amount, b_max) - (b_min - 1)   when b_max is not None
        taxable_amount - (b_min - 1)                when b_max is None (top bracket)
    ...but only when taxable_amount > b_min - 1 (i.e. there is anything in this bracket).

    Special case: b_min == 0 → bracket floor is 0, not -1.

    Returns:
        (tax_by_band, total_tax) — band list contains only brackets with non-zero tax.
    """
    tax_by_band: list[TaxBand] = []
    total_tax = 0.0

    for bracket in brackets:
        b_min: int = bracket["min"]
        b_max: Optional[int] = bracket["max"]
        rate: float = bracket["rate"]

        # Floor of the bracket for calculation: for b_min=0 the floor is 0;
        # for b_min=150001 the floor is 150000 (the boundary below this band).
        floor = b_min - 1 if b_min > 0 else 0

        # Nothing in this bracket if taxable_amount doesn't reach the floor
        if taxable_amount <= floor:
            break

        if b_max is None:
            amount_in_bracket = taxable_amount - floor
        else:
            amount_in_bracket = min(taxable_amount, b_max) - floor

        if amount_in_bracket <= 0:
            continue

        band_tax = amount_in_bracket * rate
        total_tax += band_tax

        if b_max is None:
            label = f"฿{b_min:,}+"
        else:
            label = f"฿{b_min:,}–฿{b_max:,}"

        # Only append bands with non-zero tax (rate>0) for readability,
        # but always append the band so the caller gets a full picture.
        tax_by_band.append(
            TaxBand(
                bracket_label=label,
                taxable_amount=round(amount_in_bracket, 2),
                rate=rate,
                tax_amount=round(band_tax, 2),
            )
        )

    return tax_by_band, round(total_tax, 2)
