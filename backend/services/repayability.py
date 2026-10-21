"""
Repayability assessment — NPL guard for the shortfall/recommendation pipeline.

Business rule: projected average monthly cashflow over the next 6 months must
exceed the product's monthly repayment by a factor of 1.2 (20% headroom).
This is a hard gate: if it fails, lending products are withheld entirely.
"""
from dataclasses import dataclass


@dataclass
class RepayabilityResult:
    passes: bool
    reason: str
    avg_monthly_cashflow: float
    required_monthly_cashflow: float
    headroom_ratio: float


def assess_repayability(
    projected_cashflow_series: list[float],
    product_monthly_repayment: float,
) -> RepayabilityResult:
    """
    Assess whether the SME can service a product's monthly repayment.

    Args:
        projected_cashflow_series: list of projected net monthly cashflows (credit - debit)
                                   for the next N months. Must have at least 1 entry.
        product_monthly_repayment: the product's monthly repayment obligation in THB.

    Returns:
        RepayabilityResult with passes bool and human-readable reason.
    """
    if not projected_cashflow_series:
        return RepayabilityResult(
            passes=False,
            reason="Insufficient cashflow data to assess repayability.",
            avg_monthly_cashflow=0.0,
            required_monthly_cashflow=product_monthly_repayment * 1.2,
            headroom_ratio=0.0,
        )

    if product_monthly_repayment <= 0:
        return RepayabilityResult(
            passes=True,
            reason="No repayment obligation — product is not a lending product.",
            avg_monthly_cashflow=sum(projected_cashflow_series) / len(projected_cashflow_series),
            required_monthly_cashflow=0.0,
            headroom_ratio=float("inf"),
        )

    avg_cashflow = sum(projected_cashflow_series) / len(projected_cashflow_series)
    required = product_monthly_repayment * 1.2
    headroom_ratio = avg_cashflow / product_monthly_repayment if product_monthly_repayment > 0 else float("inf")

    if avg_cashflow >= required:
        reason = (
            f"Average projected monthly net cashflow of ฿{avg_cashflow:,.0f} "
            f"covers the ฿{product_monthly_repayment:,.0f} monthly repayment "
            f"with {(headroom_ratio - 1) * 100:.0f}% headroom (required: 20%)."
        )
        return RepayabilityResult(
            passes=True,
            reason=reason,
            avg_monthly_cashflow=avg_cashflow,
            required_monthly_cashflow=required,
            headroom_ratio=headroom_ratio,
        )
    else:
        reason = (
            f"Average projected monthly net cashflow of ฿{avg_cashflow:,.0f} "
            f"does not cover the ฿{product_monthly_repayment:,.0f} monthly repayment "
            f"with required 20% headroom (would need ฿{required:,.0f}). "
            f"Lending product withheld — NPL guard triggered."
        )
        return RepayabilityResult(
            passes=False,
            reason=reason,
            avg_monthly_cashflow=avg_cashflow,
            required_monthly_cashflow=required,
            headroom_ratio=headroom_ratio,
        )
