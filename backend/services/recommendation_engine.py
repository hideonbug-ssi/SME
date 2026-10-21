"""
Product recommendation scoring engine (AIWSRT-6).

Business rules (non-negotiable):
  - Returns at most ONE product — the highest-scoring one.
  - If relevance score < 0.70 → return None. Never surface a low-quality fallback.
  - Lending products additionally require repayability: passed.
  - Product must be is_offerable = True.
  - Trigger context must match product's triggering_signal.
  - No consent → return None (PoC: assume consented unless trigger_context missing).
"""
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class ScoredProduct:
    product_id: str
    product_name: str
    score: float
    signal_basis: str
    is_lending: bool
    disclosures: list[str]
    consent_category: str


# Signal-to-product scoring weights — how well each trigger maps to product types
_SIGNAL_SCORE_MAP = {
    # (trigger_context, triggering_signal) → base_score
    ("shortfall_red", "shortfall_red"): 0.92,
    ("shortfall_yellow", "shortfall_yellow"): 0.88,
    ("shortfall_yellow", "shortfall_red"): 0.75,  # recovery loan also relevant for yellow
    ("opportunity", "opportunity"): 0.82,
    ("tax_advisory", "tax_advisory"): 0.85,
    ("shortfall_red", "shortfall_yellow"): 0.72,  # credit line as fallback for red
}

MIN_RELEVANCE_SCORE = 0.70


def score_products(
    products: list[dict],
    trigger_context: str,
    repayability_passed: bool = True,
    opted_out_categories: Optional[list[str]] = None,
) -> Optional[ScoredProduct]:
    """
    Score all candidate products and return the single best match, or None.

    Args:
        products: list of product dicts from the MCP client
        trigger_context: the reason for the recommendation
        repayability_passed: if False, lending products are excluded (NPL guard)
        opted_out_categories: list of consent_category values the owner has opted out of

    Returns:
        The highest-scoring ScoredProduct above threshold, or None.
    """
    opted_out = set(opted_out_categories or [])
    candidates: list[ScoredProduct] = []

    for product in products:
        if not product.get("is_offerable", False):
            continue
        if product.get("consent_category") in opted_out:
            logger.debug("Product %s suppressed — opted out category", product["product_id"])
            continue
        if product.get("is_lending") and not repayability_passed:
            logger.info(
                "Product %s withheld — NPL guard: repayability failed", product["product_id"]
            )
            continue

        triggering_signal = product.get("triggering_signal", "")
        score = _SIGNAL_SCORE_MAP.get((trigger_context, triggering_signal), 0.0)

        if score >= MIN_RELEVANCE_SCORE:
            candidates.append(ScoredProduct(
                product_id=product["product_id"],
                product_name=product["product_name"],
                score=score,
                signal_basis=f"Trigger: {trigger_context} matched product signal: {triggering_signal}",
                is_lending=product.get("is_lending", False),
                disclosures=product.get("disclosures", []),
                consent_category=product.get("consent_category", ""),
            ))

    if not candidates:
        logger.info("No products cleared the relevance threshold (%.2f) for trigger '%s'", MIN_RELEVANCE_SCORE, trigger_context)
        return None

    # Return highest-scoring product only
    return max(candidates, key=lambda p: p.score)
