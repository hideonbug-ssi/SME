"""
Shortfall router — AIWSRT-5 three-tier evaluation and pending-action CRUD.
"""
from fastapi import APIRouter, HTTPException
from models.forecast import ShortfallStatusResponse
from agents.shortfall_agent import run_shortfall_agent
from services.approval_gateway import approval_gateway
from demo_state import demo_state
from agent_tracer import tracer

router = APIRouter(tags=["shortfall"])


@router.get("/shortfall/status", response_model=ShortfallStatusResponse)
async def get_shortfall_status(sme_id: str = "TH-SME-001"):
    """
    Evaluate current shortfall tier (Green/Yellow/Red), run NPL guard, return recovery plan.
    """
    try:
        # If forecast already started the trace run, append shortfall steps to it.
        # If called standalone (no ongoing run), start and finish the run here.
        standalone = not tracer.is_running
        if standalone:
            tracer.start_run(demo_state.active_scenario)
        result = await run_shortfall_agent(sme_id=sme_id)
        if standalone:
            tracer.finish_run()
        return result
    except Exception as exc:
        tracer.finish_run()
        raise HTTPException(status_code=503, detail=f"Shortfall agent unavailable: {exc}")


@router.get("/pending-actions")
async def list_pending_actions():
    """List all pending actions awaiting owner confirmation."""
    actions = approval_gateway.list_pending()
    return {"pending_actions": [a.__dict__ for a in actions]}


@router.post("/pending-actions/{action_id}/confirm")
async def confirm_pending_action(action_id: str):
    """Owner confirms a proposed action — marks it executed (stub in PoC)."""
    try:
        action = approval_gateway.confirm_action(action_id)
        return {"status": "confirmed", "action": action.__dict__}
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Pending action {action_id} not found")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.delete("/pending-actions/{action_id}")
async def reject_pending_action(action_id: str):
    """Owner rejects/dismisses a proposed action."""
    try:
        action = approval_gateway.reject_action(action_id)
        return {"status": "rejected", "action": action.__dict__}
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Pending action {action_id} not found")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
