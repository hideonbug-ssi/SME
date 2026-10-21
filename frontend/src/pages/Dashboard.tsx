
import { ForecastPanel } from '../components/organisms/ForecastPanel';
import { ShortfallPanel } from '../components/organisms/ShortfallPanel';

export function Dashboard() {
  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <p className="text-sm text-gray-500 mt-1">
          Your 90-day cash position and recommendations — as of today.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        {/* Forecast Panel — wider column */}
        <div className="lg:col-span-3">
          <ForecastPanel />
        </div>

        {/* Shortfall + Actions Panel */}
        <div className="lg:col-span-2">
          <ShortfallPanel />
        </div>
      </div>
    </div>
  );
}
