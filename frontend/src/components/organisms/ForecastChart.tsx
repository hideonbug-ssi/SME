
import {
  ComposedChart,
  Area,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
  Legend,
  type TooltipProps,
} from 'recharts';
import type { ForecastDataPoint, ForecastSummary, HistoricalDataPoint, WithProductDataPoint } from '../../types/forecast';
import { formatTHB } from '../../utils/currency';
import { formatDate } from '../../utils/dates';

interface ForecastChartProps {
  dataPoints: ForecastDataPoint[];
  summary: ForecastSummary;
  rollingAvgMonthlyOutflow: number;
  historicalDataPoints?: HistoricalDataPoint[];
  withProductDataPoints?: WithProductDataPoint[];
}

// Unified row type for the composed chart — all optional since not every date has all series
interface ChartRow {
  date: string;
  actual_balance?: number;
  projected_balance?: number;
  with_product?: number;
}

function CustomTooltip({ active, payload, label }: TooltipProps<number, string>) {
  if (!active || !payload || payload.length === 0) return null;
  return (
    <div className="bg-white border border-gray-200 rounded-lg shadow-lg p-3 text-sm min-w-[180px]">
      <p className="text-gray-500 mb-2 font-medium">{formatDate(label as string)}</p>
      {payload.map((entry) => {
        if (entry.value == null) return null;
        const label =
          entry.dataKey === 'actual_balance'
            ? 'Actual balance'
            : entry.dataKey === 'projected_balance'
              ? 'Projected balance'
              : 'If you take the recommendation';
        return (
          <p key={entry.dataKey as string} className="flex justify-between gap-4">
            <span style={{ color: entry.color }} className="text-xs">
              {label}
            </span>
            <span className="font-semibold text-gray-900">{formatTHB(entry.value)}</span>
          </p>
        );
      })}
    </div>
  );
}

function formatXAxis(dateStr: string): string {
  const d = new Date(dateStr + 'T00:00:00');
  return d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short' });
}

function formatYAxis(value: number): string {
  if (value >= 1_000_000) return `฿${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `฿${(value / 1_000).toFixed(0)}k`;
  if (value <= -1_000) return `-฿${(Math.abs(value) / 1_000).toFixed(0)}k`;
  return `฿${value}`;
}

export const FORECAST_AMBER = '#d97706';

const LEGEND_ITEMS = [
  { key: 'actual_balance', label: 'Actual balance', color: '#16a34a', dashed: false, isArea: true },
  { key: 'projected_balance', label: 'Projected (predicted)', color: FORECAST_AMBER, dashed: true, isArea: true },
  { key: 'with_product', label: 'If you take the recommendation', color: '#2563eb', dashed: true, isArea: false },
];

function CustomLegend({ hasWithProduct }: { hasWithProduct: boolean }) {
  return (
    <div className="flex flex-wrap gap-x-5 gap-y-1.5 mt-2 mb-1 px-1">
      {LEGEND_ITEMS.filter((item) => item.key !== 'with_product' || hasWithProduct).map((item) => (
        <div key={item.key} className="flex items-center gap-1.5">
          <span
            className="inline-block h-2.5 rounded-sm"
            style={{
              width: item.isArea ? 14 : 20,
              backgroundColor: item.isArea ? item.color : 'transparent',
              borderBottom: item.isArea ? 'none' : `2px ${item.dashed ? 'dashed' : 'solid'} ${item.color}`,
              opacity: item.isArea ? (item.dashed ? 0.45 : 0.8) : 1,
            }}
          />
          <span className="text-xs text-gray-600">{item.label}</span>
        </div>
      ))}
    </div>
  );
}

export function ForecastChart({
  dataPoints,
  summary,
  rollingAvgMonthlyOutflow,
  historicalDataPoints = [],
  withProductDataPoints = [],
}: ForecastChartProps) {
  const todayStr = '2026-07-14';
  const shortfallThreshold = rollingAvgMonthlyOutflow * 0.5;

  const hasWithProduct = withProductDataPoints.length > 0;

  // Build a unified date-keyed map so all three series share the same X axis
  const rowMap = new Map<string, ChartRow>();

  for (const pt of historicalDataPoints) {
    const existing = rowMap.get(pt.date) ?? { date: pt.date };
    rowMap.set(pt.date, { ...existing, actual_balance: pt.actual_balance });
  }

  for (const pt of dataPoints) {
    const dateStr = typeof pt.date === 'string' ? pt.date : String(pt.date);
    const existing = rowMap.get(dateStr) ?? { date: dateStr };
    rowMap.set(dateStr, { ...existing, projected_balance: pt.projected_balance });
  }

  for (const pt of withProductDataPoints) {
    const existing = rowMap.get(pt.date) ?? { date: pt.date };
    rowMap.set(pt.date, { ...existing, with_product: pt.projected_balance });
  }

  // Sort by date
  const chartData: ChartRow[] = Array.from(rowMap.values()).sort((a, b) =>
    a.date.localeCompare(b.date),
  );

  // Interval: show ~8 ticks across the span
  const tickInterval = Math.max(1, Math.floor(chartData.length / 8));

  return (
    <div className="w-full">
      <CustomLegend hasWithProduct={hasWithProduct} />
      <div className="w-full h-64">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={chartData} margin={{ top: 8, right: 16, bottom: 0, left: 16 }}>
            <defs>
              <linearGradient id="historicalGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#16a34a" stopOpacity={0.4} />
                <stop offset="95%" stopColor="#16a34a" stopOpacity={0.05} />
              </linearGradient>
              <linearGradient id="forecastGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={FORECAST_AMBER} stopOpacity={0.18} />
                <stop offset="95%" stopColor={FORECAST_AMBER} stopOpacity={0.01} />
              </linearGradient>
            </defs>

            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />

            <XAxis
              dataKey="date"
              tickFormatter={formatXAxis}
              tick={{ fontSize: 11, fill: '#6b7280' }}
              interval={tickInterval}
              tickLine={false}
            />
            <YAxis
              tickFormatter={formatYAxis}
              tick={{ fontSize: 11, fill: '#6b7280' }}
              tickLine={false}
              axisLine={false}
              width={64}
            />

            <Tooltip content={<CustomTooltip />} />

            {/* Shortfall threshold — dashed red */}
            <ReferenceLine
              y={shortfallThreshold}
              stroke="#ef4444"
              strokeDasharray="4 4"
              label={{ value: 'Shortfall threshold', position: 'insideTopLeft', fontSize: 10, fill: '#ef4444' }}
            />

            {/* Today vertical reference line */}
            <ReferenceLine
              x={todayStr}
              stroke="#6366f1"
              strokeWidth={2}
              strokeDasharray="4 4"
              label={{ value: 'Today', position: 'top', fontSize: 11, fill: '#6366f1' }}
            />

            {/* Min point annotation */}
            <ReferenceLine
              x={summary.min_date}
              stroke="#ef4444"
              strokeDasharray="2 4"
              strokeWidth={1}
            />

            {/* Historical series — solid dark-green area */}
            <Area
              type="monotone"
              dataKey="actual_balance"
              stroke="#16a34a"
              strokeWidth={2.5}
              fill="url(#historicalGradient)"
              fillOpacity={1}
              dot={false}
              activeDot={{ r: 4, fill: '#16a34a' }}
              connectNulls={false}
              name="Actual balance"
            />

            {/* Forecast series — dashed amber translucent area (LLM-predicted) */}
            <Area
              type="monotone"
              dataKey="projected_balance"
              stroke={FORECAST_AMBER}
              strokeWidth={2}
              strokeDasharray="5 3"
              fill="url(#forecastGradient)"
              fillOpacity={1}
              dot={false}
              activeDot={{ r: 4, fill: FORECAST_AMBER }}
              connectNulls={false}
              name="Projected (predicted)"
            />

            {/* With-product series — solid blue line, no fill */}
            {hasWithProduct && (
              <Line
                type="monotone"
                dataKey="with_product"
                stroke="#2563eb"
                strokeWidth={2}
                strokeDasharray="8 3"
                dot={false}
                activeDot={{ r: 4, fill: '#2563eb' }}
                connectNulls={false}
                name="If you take the recommendation"
              />
            )}
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
