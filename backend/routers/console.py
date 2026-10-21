"""
Developer Console router — exposes the agent execution trace for the active demo scenario.
"""
import asyncio
import json
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from demo_state import demo_state
from agent_tracer import tracer

router = APIRouter(prefix="/console", tags=["console"])


@router.get("/agent-trace")
def get_agent_trace():
    """
    Return the structured agent execution trace for the currently active demo scenario.
    Used by the developer Console tab to visualise agent decision steps, raw inputs,
    and final outputs.
    """
    trace = demo_state.get_agent_trace()
    if trace is None:
        raise HTTPException(status_code=404, detail="No agent trace available for the active scenario.")
    return trace


@router.get("/trace")
def get_trace():
    """Return current live trace snapshot."""
    return {
        "running": tracer.is_running,
        "meta": tracer.get_meta(),
        "steps": tracer.get_steps(),
    }


@router.get("/trace/stream")
async def stream_trace():
    """SSE endpoint — streams trace events to the browser in real time."""

    async def generator():
        q = await tracer.subscribe()
        # Immediately send current snapshot so new tab subscribers get context
        snapshot = {
            "type": "snapshot",
            "running": tracer.is_running,
            "meta": tracer.get_meta(),
            "steps": tracer.get_steps(),
        }
        yield f"data: {json.dumps(snapshot)}\n\n"
        try:
            while True:
                try:
                    event = await asyncio.wait_for(q.get(), timeout=25.0)
                    yield f"data: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"
        finally:
            tracer.unsubscribe(q)

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
