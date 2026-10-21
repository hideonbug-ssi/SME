from pydantic import BaseModel
from typing import Optional


class RecommendationRequest(BaseModel):
    sme_id: str
    trigger_context: str  # "tax_advisory"|"shortfall_yellow"|"shortfall_red"|"opportunity"
    signals: dict = {}


class ProductRecommendation(BaseModel):
    product_id: str
    product_name: str
    rationale: str
    relevance_score: float
    signal_basis: str
    repayability: str  # "passed" | "not_applicable"
    disclosures: list[str]


class RecommendationResponse(BaseModel):
    recommendation: Optional[ProductRecommendation] = None
