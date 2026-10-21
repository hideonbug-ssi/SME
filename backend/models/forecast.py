from pydantic import BaseModel
from typing import Optional
from datetime import date


class ForecastDataPoint(BaseModel):
    date: date
    projected_balance: float
    confidence: str  # "high" | "low"


class ForecastSummary(BaseModel):
    min_point: float
    min_date: date
    max_point: float
    max_date: date
    key_drivers: list[str]


class ForecastResponse(BaseModel):
    sme_id: str
    data_points: list[ForecastDataPoint]
    summary: ForecastSummary
    rolling_avg_monthly_outflow: float
    confidence_overall: str  # "high" | "low"
    updated_at: str  # ISO8601
    alert_message: Optional[str] = None
    alert_message_th: Optional[str] = None
    surplus_detected: bool = False
    shortfall_detected: bool = False
    handoff_payload: Optional[dict] = None
    historical_data_points: list[dict] = []
    with_product_data_points: list[dict] = []
    product_impact_description: str = ""


class ShortfallStatusResponse(BaseModel):
    tier: str  # "green" | "yellow" | "red"
    shortfall_amount_thb: Optional[float] = None
    shortfall_date: Optional[str] = None
    recovery_plan: Optional[str] = None
    product_trigger: Optional[dict] = None
    repayability_passed: Optional[bool] = None
