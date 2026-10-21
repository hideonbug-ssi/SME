"""
AgentTracer — thread-safe, asyncio-compatible live trace collector.

Usage:
    from agent_tracer import tracer
    tracer.start_run("yellow")
    tracer.emit_step(agent="ForecastAgent", action="fetch_ledger", ...)
    tracer.finish_run()
"""
import asyncio
import json
from datetime import datetime, timezone
from typing import Any
from collections import deque


class TraceStep:
    def __init__(self, step_num, agent, action, status="running",
                 input_data=None, prompt=None, reasoning=None,
                 output=None, duration_ms=None, error=None):
        self.step_num = step_num
        self.agent = agent
        self.action = action
        self.status = status          # "running" | "done" | "error"
        self.input_data = input_data or {}
        self.prompt = prompt          # The literal prompt string sent to LLM (or None)
        self.reasoning = reasoning    # LLM response text or deterministic explanation
        self.output = output or {}
        self.duration_ms = duration_ms
        self.error = error
        self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self):
        return {
            "step_num": self.step_num,
            "agent": self.agent,
            "action": self.action,
            "status": self.status,
            "input_data": self.input_data,
            "prompt": self.prompt,
            "reasoning": self.reasoning,
            "output": self.output,
            "duration_ms": self.duration_ms,
            "error": self.error,
            "timestamp": self.timestamp,
        }


class AgentTracer:
    def __init__(self, maxlen=200):
        self._steps: deque[TraceStep] = deque(maxlen=maxlen)
        self._run_meta: dict = {}
        self._running = False
        self._step_counter = 0
        self._subscribers: list[asyncio.Queue] = []
        self._lock = asyncio.Lock()

    # ── Public API ─────────────────────────────────────────────────────────

    def start_run(self, scenario: str):
        """Clear previous trace and mark a new run as started."""
        self._steps.clear()
        self._step_counter = 0
        self._running = True
        self._run_meta = {
            "scenario": scenario,
            "started_at": datetime.now(timezone.utc).isoformat(),
        }
        self._broadcast({"type": "run_started", "scenario": scenario,
                         "started_at": self._run_meta["started_at"]})

    def emit_step(
        self,
        agent: str,
        action: str,
        input_data: dict | None = None,
        prompt: str | None = None,
        reasoning: str | None = None,
        output: dict | None = None,
        duration_ms: int | None = None,
        status: str = "done",
        error: str | None = None,
    ) -> TraceStep:
        """Record a completed step and push it to subscribers."""
        self._step_counter += 1
        step = TraceStep(
            step_num=self._step_counter,
            agent=agent,
            action=action,
            status=status,
            input_data=input_data,
            prompt=prompt,
            reasoning=reasoning,
            output=output,
            duration_ms=duration_ms,
            error=error,
        )
        self._steps.append(step)
        self._broadcast({"type": "step", "step": step.to_dict()})
        return step

    def finish_run(self):
        self._running = False
        self._broadcast({"type": "run_finished",
                         "finished_at": datetime.now(timezone.utc).isoformat(),
                         "total_steps": self._step_counter})

    @property
    def is_running(self) -> bool:
        return self._running

    def get_steps(self) -> list[dict]:
        return [s.to_dict() for s in self._steps]

    def get_meta(self) -> dict:
        return self._run_meta

    # ── SSE subscription ────────────────────────────────────────────────────

    async def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue):
        try:
            self._subscribers.remove(q)
        except ValueError:
            pass

    # ── Internal ─────────────────────────────────────────────────────────────

    def _broadcast(self, event: dict):
        dead = []
        for q in self._subscribers:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                dead.append(q)
        for q in dead:
            self.unsubscribe(q)


tracer = AgentTracer()
