"""
Demo scenario router — allows a presenter to switch between pre-baked
demo scenarios without restarting services.
"""
from fastapi import APIRouter, HTTPException
from demo_state import demo_state
from agent_tracer import tracer

router = APIRouter(prefix="/demo", tags=["demo"])

VALID_SCENARIOS = {"green", "yellow", "red", "overdue"}


@router.get("/scenario")
def get_active_scenario():
    return {"active_scenario": demo_state.active_scenario}


@router.post("/scenario/{name}")
def switch_scenario(name: str):
    if name not in VALID_SCENARIOS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown scenario. Valid: {sorted(VALID_SCENARIOS)}",
        )
    demo_state.active_scenario = name
    # Clear the forecast cache so shortfall agent uses the new scenario's data
    from agents.forecast_agent import _cache as _forecast_cache
    _forecast_cache.clear()
    # Broadcast run_started immediately so the Console clears before agents re-run
    tracer.start_run(name)
    return {"active_scenario": name, "ok": True}
