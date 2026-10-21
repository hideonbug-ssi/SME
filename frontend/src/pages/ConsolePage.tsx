import { useState, useEffect, useRef } from 'react';
import { useAgentTrace } from '../hooks/useAgentTrace';
import type { TraceStep } from '../api/console';

// ─── Helpers ─────────────────────────────────────────────────────────────────

function relativeTime(isoString: string): string {
  const diff = Date.now() - new Date(isoString).getTime();
  const secs = Math.floor(diff / 1000);
  if (secs < 60) return `${secs}s ago`;
  const mins = Math.floor(secs / 60);
  if (mins < 60) return `${mins}m ago`;
  return `${Math.floor(mins / 60)}h ago`;
}

// ─── Scenario badge ──────────────────────────────────────────────────────────

const SCENARIO_COLORS: Record<string, string> = {
  green:   'bg-green-100 text-green-800 border-green-200',
  yellow:  'bg-amber-100 text-amber-800 border-amber-200',
  red:     'bg-red-100 text-red-800 border-red-200',
  overdue: 'bg-orange-100 text-orange-800 border-orange-200',
};

function ScenarioBadge({ scenario }: { scenario: string }) {
  const cls = SCENARIO_COLORS[scenario] ?? 'bg-gray-100 text-gray-800 border-gray-200';
  return (
    <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-sm font-semibold border ${cls}`}>
      <span className="inline-block h-2 w-2 rounded-full bg-current" />
      {scenario.toUpperCase()}
    </span>
  );
}

// ─── JSON viewer ─────────────────────────────────────────────────────────────

function JsonViewer({ data }: { data: Record<string, unknown> | unknown[] | null }) {
  if (!data) return null;
  const raw = JSON.stringify(data, null, 2);
  const highlighted = raw
    .replace(/("[\w_]+"):/g, '<span class="text-green-400">$1</span>:')
    .replace(/: ("(?:[^"\\]|\\.)*")/g, ': <span class="text-amber-300">$1</span>')
    .replace(/: (true|false)/g, ': <span class="text-violet-400">$1</span>')
    .replace(/: (-?\d+(?:\.\d+)?)/g, ': <span class="text-cyan-300">$1</span>');

  return (
    <pre
      className="text-xs font-mono bg-gray-900 text-green-400 p-3 rounded overflow-x-auto leading-relaxed max-h-48"
      dangerouslySetInnerHTML={{ __html: highlighted }}
    />
  );
}

// ─── Agent badge ──────────────────────────────────────────────────────────────

const AGENT_COLORS: Record<string, string> = {
  ForecastAgent:        'bg-green-100 text-green-800',
  ShortfallAgent:       'bg-amber-100 text-amber-800',
  RecommendationEngine: 'bg-blue-100 text-blue-800',
};

function AgentBadge({ name }: { name: string }) {
  const cls = AGENT_COLORS[name] ?? 'bg-gray-100 text-gray-700';
  return (
    <span className={`inline-block px-2 py-0.5 rounded text-xs font-semibold ${cls}`}>{name}</span>
  );
}

// ─── Status indicator ─────────────────────────────────────────────────────────

function StatusIndicator({ status }: { status: TraceStep['status'] }) {
  if (status === 'running') {
    return (
      <span className="inline-flex items-center gap-1 text-xs text-amber-600">
        <svg className="animate-spin h-3 w-3" viewBox="0 0 24 24" fill="none">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
        </svg>
        Running
      </span>
    );
  }
  if (status === 'error') {
    return <span className="text-xs text-red-600 font-semibold">✗ Error</span>;
  }
  return <span className="text-xs text-green-600 font-semibold">✓ Done</span>;
}

// ─── Collapsible section ──────────────────────────────────────────────────────

function CollapsibleSection({
  label,
  children,
  defaultOpen = false,
  accent,
}: {
  label: string;
  children: React.ReactNode;
  defaultOpen?: boolean;
  accent?: string;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="border border-gray-200 rounded">
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-3 py-2 text-xs font-semibold uppercase tracking-wide text-gray-500 hover:bg-gray-50 transition-colors rounded"
      >
        <span className={accent}>{label}</span>
        <span>{open ? '▲' : '▼'}</span>
      </button>
      {open && <div className="px-3 pb-3">{children}</div>}
    </div>
  );
}

// ─── Step card ────────────────────────────────────────────────────────────────

function StepCard({ step, isLast }: { step: TraceStep; isLast: boolean }) {
  const isLLMCall = step.action === 'generate_rationale';

  return (
    <div className="flex gap-4">
      {/* Timeline column */}
      <div className="flex-shrink-0 flex flex-col items-center">
        <div className="h-8 w-8 rounded-full bg-indigo-600 text-white flex items-center justify-center text-sm font-bold shadow">
          {step.step_num}
        </div>
        {!isLast && <div className="flex-1 w-0.5 bg-gray-200 mt-2" />}
      </div>

      {/* Card */}
      <div className={`flex-1 pb-6 ${isLast ? '' : ''}`}>
        <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
          {/* Header */}
          <div className="flex flex-wrap items-center gap-2 mb-3">
            <AgentBadge name={step.agent} />
            <code className="text-sm font-mono text-gray-700 bg-gray-50 px-2 py-0.5 rounded border border-gray-200">
              {step.action}
            </code>
            {step.duration_ms !== null && (
              <span className="text-xs text-gray-400 font-mono bg-gray-50 px-2 py-0.5 rounded border border-gray-200">
                {step.duration_ms}ms
              </span>
            )}
            <span className="ml-auto">
              <StatusIndicator status={step.status} />
            </span>
          </div>

          {/* Error */}
          {step.error && (
            <div className="mb-3 text-xs text-red-700 bg-red-50 border border-red-200 rounded p-2">
              {step.error}
            </div>
          )}

          {/* Collapsible sections */}
          <div className="space-y-2">
            {/* Input */}
            {step.input_data && Object.keys(step.input_data).length > 0 && (
              <CollapsibleSection label="Input" defaultOpen={false}>
                <JsonViewer data={step.input_data} />
              </CollapsibleSection>
            )}

            {/* Prompt — only when present */}
            {step.prompt !== null && (
              <CollapsibleSection
                label="Prompt (sent to LLM)"
                defaultOpen={isLLMCall}
                accent="text-yellow-600"
              >
                <pre className="text-xs font-mono bg-gray-900 text-yellow-300 p-3 rounded overflow-x-auto leading-relaxed max-h-48 whitespace-pre-wrap">
                  {step.prompt}
                </pre>
              </CollapsibleSection>
            )}

            {/* Reasoning / LLM Response */}
            {step.reasoning !== null && (
              <CollapsibleSection
                label={isLLMCall ? 'LLM Response' : 'Reasoning'}
                defaultOpen={true}
                accent={isLLMCall ? 'text-blue-600' : 'text-indigo-600'}
              >
                <p className="text-sm text-gray-700 leading-relaxed">{step.reasoning}</p>
              </CollapsibleSection>
            )}

            {/* Output */}
            {step.output && Object.keys(step.output).length > 0 && (
              <CollapsibleSection label="Output" defaultOpen={true}>
                <JsonViewer data={step.output} />
              </CollapsibleSection>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Empty state ──────────────────────────────────────────────────────────────

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-24 text-center">
      <div className="relative mb-4">
        <div className="h-16 w-16 rounded-full bg-gray-100 flex items-center justify-center">
          <svg className="h-8 w-8 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
              d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
          </svg>
        </div>
        <span className="absolute -top-1 -right-1 h-4 w-4 rounded-full bg-gray-300 animate-pulse" />
      </div>
      <p className="text-gray-500 text-sm">Waiting for agent activity&hellip;</p>
      <p className="text-gray-400 text-xs mt-1">Switch a scenario to start a trace.</p>
    </div>
  );
}

// ─── Main page ────────────────────────────────────────────────────────────────

export function ConsolePage() {
  const { running, meta, steps, connected } = useAgentTrace();
  const bottomRef = useRef<HTMLDivElement | null>(null);

  // Auto-scroll as new steps arrive
  useEffect(() => {
    if (steps.length > 0) {
      bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  }, [steps.length]);

  return (
    <div className="max-w-5xl mx-auto">
      {/* Page header */}
      <div className="mb-6 flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2">
          {/* Terminal icon */}
          <svg className="h-6 w-6 text-indigo-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
          </svg>
          <h1 className="text-2xl font-bold text-gray-900">Agent Console</h1>
        </div>

        {/* Connection badge */}
        <span
          className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold ${
            connected ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
          }`}
        >
          <span className={`h-2 w-2 rounded-full ${connected ? 'bg-green-500' : 'bg-red-500'}`} />
          {connected ? 'Live' : 'Disconnected'}
        </span>

        {/* Running indicator */}
        {running && (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-100 text-amber-700 animate-pulse">
            ⚡ Running&hellip;
          </span>
        )}

        <p className="w-full text-sm text-gray-500 -mt-1">
          Live agent execution trace — steps appear as they complete
        </p>
      </div>

      {/* Run info bar */}
      {meta && (meta.scenario || meta.started_at) && (
        <div className="mb-6 flex flex-wrap items-center gap-3 p-3 bg-gray-50 border border-gray-200 rounded-lg">
          {meta.scenario && <ScenarioBadge scenario={meta.scenario} />}
          {meta.started_at && (
            <span className="text-xs text-gray-500">
              Started: {relativeTime(meta.started_at)}
            </span>
          )}
          <span className="text-xs text-gray-400 ml-auto">
            {steps.length} step{steps.length !== 1 ? 's' : ''}
          </span>
        </div>
      )}

      {/* Steps timeline */}
      {steps.length === 0 ? (
        <EmptyState />
      ) : (
        <div>
          {steps.map((step, idx) => (
            <StepCard key={step.step_num} step={step} isLast={idx === steps.length - 1} />
          ))}
          <div ref={bottomRef} />
        </div>
      )}
    </div>
  );
}
