import { useState } from 'react';
import { RefreshCw, TrendingUp, TrendingDown } from 'lucide-react';
import { Card, CardHeader, CardTitle } from '../atoms/Card';
import { ConfidencePill } from '../atoms/ConfidencePill';
import { Spinner } from '../atoms/Spinner';
import { Button } from '../atoms/Button';
import { ForecastChart, FORECAST_AMBER } from './ForecastChart';
import { useForecast, useRefreshForecast } from '../../hooks/useForecast';
import { formatTHB } from '../../utils/currency';
import { formatDate, formatDateTime, relativeTime } from '../../utils/dates';

type DriverType = 'predicted' | 'payable' | 'receivable' | 'scheduled';

interface ParsedDriver {
  type: DriverType;
  description: string;
  amount: string;
  date: string;
}

function parseDriver(raw: string): ParsedDriver {
  const isPredicted = raw.includes('[predicted recurring]');
  const isReceivable = raw.startsWith('Expected receipt:') || (raw.includes('Receivable:') && !isPredicted);
  const isPayable = !isPredicted && !isReceivable && raw.includes('Payable:');
  const type: DriverType = isPredicted ? 'predicted' : isReceivable ? 'receivable' : isPayable ? 'payable' : 'scheduled';

  const amountMatch = raw.match(/\(฿([\d,]+)\)/);
  const amount = amountMatch ? `฿${amountMatch[1]}` : '';

  const dateMatch = raw.match(/on (\d{4}-\d{2}-\d{2})/);
  const date = dateMatch ? dateMatch[1] : '';

  const desc = raw
    .replace(/\[predicted recurring\]/g, '')
    .replace(/\(predicted — monthly recurring\)/g, '')
    .replace(/^Payment due:\s*Payable:\s*/, '')
    .replace(/^Expected receipt:\s*Receivable:\s*/, '')
    .replace(/^Payment due:\s*/, '')
    .replace(/^Expected receipt:\s*/, '')
    .replace(/\(฿[\d,]+\)/, '')
    .replace(/on \d{4}-\d{2}-\d{2}/, '')
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/[—\-,]+$/, '')
    .trim();

  return { type, description: desc, amount, date };
}

function DriverRow({ driver, color }: { driver: ParsedDriver; color: string }) {
  return (
    <li className="flex items-center justify-between gap-2 py-1">
      <div className="flex items-center gap-2 min-w-0">
        <span className="shrink-0 w-1.5 h-1.5 rounded-full mt-0.5" style={{ backgroundColor: color }} />
        <span className="text-sm text-gray-800 truncate">{driver.description}</span>
      </div>
      <div className="flex items-center gap-2 shrink-0 text-xs text-right">
        <span className="font-semibold text-gray-900">{driver.amount}</span>
        {driver.date && (
          <span className="text-gray-400 whitespace-nowrap">{formatDate(driver.date)}</span>
        )}
      </div>
    </li>
  );
}

function DriversSection({
  label,
  drivers,
  color,
  badge,
}: {
  label: string;
  drivers: ParsedDriver[];
  color: string;
  badge?: string;
}) {
  if (drivers.length === 0) return null;
  return (
    <div className="mb-3">
      <div className="flex items-center gap-2 mb-1">
        <p className="text-xs font-semibold uppercase tracking-wide" style={{ color }}>
          {label}
        </p>
        {badge && (
          <span className="text-[10px] px-1.5 py-0.5 rounded-full font-medium" style={{ backgroundColor: `${color}18`, color }}>
            {badge}
          </span>
        )}
      </div>
      <ul className="divide-y divide-gray-50">
        {drivers.map((d, i) => (
          <DriverRow key={i} driver={d} color={color} />
        ))}
      </ul>
    </div>
  );
}

export function ForecastPanel() {
  const { data, isLoading, isError, error, dataUpdatedAt } = useForecast();
  const refreshForecast = useRefreshForecast();
  const [refreshing, setRefreshing] = useState(false);

  const handleRefresh = async () => {
    setRefreshing(true);
    await refreshForecast();
    setRefreshing(false);
  };

  // Determine staleness: stale if last update > 6 hours ago
  const isStale = dataUpdatedAt
    ? Date.now() - dataUpdatedAt > 6 * 60 * 60 * 1000
    : false;

  return (
    <Card className="h-full">
      <CardHeader>
        <CardTitle>90-Day Cash Forecast</CardTitle>
        <Button
          variant="ghost"
          size="sm"
          onClick={handleRefresh}
          loading={refreshing}
          aria-label="Refresh forecast"
        >
          <RefreshCw className="h-4 w-4" aria-hidden="true" />
          Refresh
        </Button>
      </CardHeader>

      {isLoading && (
        <div className="flex items-center justify-center h-64">
          <Spinner label="Loading forecast..." />
        </div>
      )}

      {isError && (
        <div className="flex flex-col items-center justify-center h-64 gap-3">
          <p className="text-sm text-red-600">
            {error instanceof Error ? error.message : 'Failed to load forecast'}
          </p>
          <Button variant="secondary" size="sm" onClick={handleRefresh}>
            Try Again
          </Button>
        </div>
      )}

      {data && (
        <>
          {/* Confidence indicator */}
          <div className="flex items-center justify-between mb-4">
            <ConfidencePill level={data.confidence_overall} />
            <span
              className={`text-xs ${isStale ? 'text-amber-600' : 'text-gray-400'}`}
              title={formatDateTime(data.updated_at)}
            >
              Updated {relativeTime(data.updated_at)}
              {isStale && ' (stale)'}
            </span>
          </div>

          {/* Empty state check */}
          {(data.data_points ?? []).length === 0 ? (
            <div className="flex flex-col items-center justify-center h-48 gap-2 text-center">
              <TrendingUp className="h-12 w-12 text-gray-300" aria-hidden="true" />
              <p className="text-sm font-medium text-gray-500">Not enough history yet</p>
              <p className="text-xs text-gray-400">
                At least 3 months of transaction data is needed to generate a forecast.
              </p>
            </div>
          ) : (
            <>
              {/* Chart */}
              <ForecastChart
                dataPoints={data.data_points}
                summary={data.summary}
                rollingAvgMonthlyOutflow={data.rolling_avg_monthly_outflow}
                historicalDataPoints={data.historical_data_points}
                withProductDataPoints={data.with_product_data_points}
              />

              {/* Min / Max annotations */}
              <div className="flex gap-4 mt-3 mb-4">
                <div className="flex items-center gap-2 text-xs">
                  <TrendingDown className="h-4 w-4 text-red-500" aria-hidden="true" />
                  <div>
                    <span className="text-gray-500">Tightest: </span>
                    <span className="font-medium text-gray-900">
                      {formatTHB(data.summary.min_point)}
                    </span>
                    <span className="text-gray-400 ml-1">
                      on {formatDate(data.summary.min_date)}
                    </span>
                  </div>
                </div>
                <div className="flex items-center gap-2 text-xs">
                  <TrendingUp className="h-4 w-4 text-green-500" aria-hidden="true" />
                  <div>
                    <span className="text-gray-500">Peak: </span>
                    <span className="font-medium text-gray-900">
                      {formatTHB(data.summary.max_point)}
                    </span>
                    <span className="text-gray-400 ml-1">
                      on {formatDate(data.summary.max_date)}
                    </span>
                  </div>
                </div>
              </div>

              {/* Key drivers */}
              {(data.summary?.key_drivers ?? []).length > 0 && (() => {
                const parsed = data.summary.key_drivers.map(parseDriver);
                const predicted = parsed.filter(d => d.type === 'predicted');
                const scheduled = parsed.filter(d => d.type === 'scheduled');
                const payables  = parsed.filter(d => d.type === 'payable');
                const receivables = parsed.filter(d => d.type === 'receivable');
                return (
                  <div className="mt-1">
                    <p className="text-xs font-medium text-gray-400 uppercase tracking-wide mb-2">
                      Key Drivers
                    </p>
                    <DriversSection
                      label="Predicted Recurring"
                      drivers={predicted}
                      color={FORECAST_AMBER}
                      badge="forecast"
                    />
                    <DriversSection
                      label="Scheduled"
                      drivers={scheduled}
                      color="#374151"
                    />
                    {(payables.length > 0 || receivables.length > 0) && (
                      <div>
                        <p className="text-xs font-medium text-gray-400 uppercase tracking-wide mb-1">
                          Invoices
                        </p>
                        <div className="pl-1 border-l-2 border-gray-100 space-y-1">
                          <DriversSection label="Payables" drivers={payables} color="#dc2626" />
                          <DriversSection label="Receivables" drivers={receivables} color="#16a34a" />
                        </div>
                      </div>
                    )}
                  </div>
                );
              })()}
            </>
          )}
        </>
      )}
    </Card>
  );
}
