import client from './client';

// ─── Legacy types (kept for backward compatibility with old agent-trace endpoint) ─

export interface AgentStep {
  step: number;
  agent: string;
  action: string;
  input: Record<string, unknown>;
  output: Record<string, unknown>;
  duration_ms: number;
}

export interface AgentTrace {
  scenario: string;
  timestamp: string;
  steps: AgentStep[];
  raw_inputs: {
    account_balance: number;
    transactions_30d_summary: {
      inflow: number;
      outflow: number;
      net: number;
    };
    receivables: Array<Record<string, unknown>>;
    payables: Array<Record<string, unknown>>;
  };
  final_outputs: {
    forecast_tier: string;
    shortfall_amount_thb: number;
    recommended_product: string;
    relevance_score: number;
    npg_guard_status: string;
  };
}

export async function getAgentTrace(): Promise<AgentTrace> {
  const { data } = await client.get<AgentTrace>('/api/v1/console/agent-trace');
  return data;
}

// ─── Live trace types ──────────────────────────────────────────────────────────

export interface TraceStep {
  step_num: number;
  agent: string;
  action: string;
  status: 'running' | 'done' | 'error';
  input_data: Record<string, unknown>;
  prompt: string | null;
  reasoning: string | null;
  output: Record<string, unknown>;
  duration_ms: number | null;
  error: string | null;
  timestamp: string;
}

export interface TraceMeta {
  scenario: string;
  started_at: string;
}

export interface TraceSnapshot {
  running: boolean;
  meta: TraceMeta;
  steps: TraceStep[];
}

export async function getTraceSnapshot(): Promise<TraceSnapshot> {
  const { data } = await client.get<TraceSnapshot>('/api/v1/console/trace');
  return data;
}
