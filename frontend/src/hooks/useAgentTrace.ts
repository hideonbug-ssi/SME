import { useState, useEffect, useRef } from 'react';
import type { TraceStep, TraceMeta } from '../api/console';

export interface AgentTraceState {
  running: boolean;
  meta: TraceMeta | null;
  steps: TraceStep[];
  connected: boolean;
}

export function useAgentTrace(): AgentTraceState {
  const [state, setState] = useState<AgentTraceState>({
    running: false,
    meta: null,
    steps: [],
    connected: false,
  });
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    const es = new EventSource('/api/v1/console/trace/stream');
    esRef.current = es;

    es.onopen = () => setState(s => ({ ...s, connected: true }));

    es.onmessage = (event) => {
      const data = JSON.parse(event.data);

      if (data.type === 'snapshot') {
        setState({
          connected: true,
          running: data.running,
          meta: data.meta ?? null,
          steps: data.steps ?? [],
        });
      } else if (data.type === 'run_started') {
        setState(s => ({
          ...s,
          running: true,
          meta: { scenario: data.scenario, started_at: data.started_at },
          steps: [],
        }));
      } else if (data.type === 'step') {
        setState(s => ({
          ...s,
          steps: [...s.steps, data.step],
        }));
      } else if (data.type === 'run_finished') {
        setState(s => ({ ...s, running: false }));
      }
    };

    es.onerror = () => setState(s => ({ ...s, connected: false }));

    return () => {
      es.close();
      esRef.current = null;
    };
  }, []);

  return state;
}
