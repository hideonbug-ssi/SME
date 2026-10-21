"""
Forecast router — AIWSRT-2 cashflow projection endpoint.
"""
from fastapi import APIRouter, HTTPException, Query
from models.forecast import ForecastResponse
from agents.forecast_agent import run_forecast_agent
from demo_state import demo_state
from agent_tracer import tracer

router = APIRouter(prefix="/forecast", tags=["forecast"])


@router.get("/cashflow", response_model=ForecastResponse)
async def get_cashflow_forecast(
    sme_id: str = Query(default="TH-SME-001"),
    horizon_days: int = Query(default=90, ge=7, le=365),
):
    """
    Run the 90-day rolling cashflow forecast agent.
    Returns projected balance curve, surplus/shortfall triggers, and handoff payload.
    Falls back to cached result if WireMock is unreachable.
    """
    # Start a fresh trace run unless the demo scenario-switch router already started one.
    # finish_run() is intentionally NOT called here; recommendations router closes the trace
    # after all three agents have contributed their steps.
    if not tracer.is_running:
        tracer.start_run(demo_state.active_scenario)
    try:
        result = await run_forecast_agent(sme_id=sme_id, horizon_days=horizon_days)
    except Exception as exc:
        tracer.finish_run()  # close on error so the Console doesn't stay stuck
        raise HTTPException(status_code=503, detail=f"Forecast service unavailable: {exc}")
    return result
