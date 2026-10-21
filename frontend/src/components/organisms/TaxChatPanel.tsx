import { useState } from 'react';
import { Calculator, ChevronDown, ChevronUp, AlertCircle, Bell, PiggyBank } from 'lucide-react';
import { Card, CardHeader, CardTitle } from '../atoms/Card';
import { Button } from '../atoms/Button';
import { Badge } from '../atoms/Badge';
import { Spinner } from '../atoms/Spinner';
import { ProductCard } from '../molecules/ProductCard';
import { useRecommendation } from '../../hooks/useRecommendation';
import { calculateTax } from '../../api/tax';
import { formatTHB } from '../../utils/currency';
import type { TaxpayerType, TaxSessionInput, TaxSessionResponse } from '../../types/tax';

const CURRENT_TAX_YEAR = 2025;

interface TaxFormState {
  taxpayer_type: TaxpayerType;
  annual_income: string;
  annual_expenses: string;
  allowances: string;
  wht_suffered: string;
  annual_turnover: string;
}

const DEFAULT_FORM: TaxFormState = {
  taxpayer_type: 'PIT',
  annual_income: '1200000',
  annual_expenses: '600000',
  allowances: '150000',
  wht_suffered: '12000',
  annual_turnover: '1200000',
};

function parseTHB(val: string): number {
  return parseFloat(val.replace(/,/g, '')) || 0;
}

export function TaxChatPanel() {
  const [form, setForm] = useState<TaxFormState>(DEFAULT_FORM);
  const [calculating, setCalculating] = useState(false);
  const [result, setResult] = useState<TaxSessionResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [bandsOpen, setBandsOpen] = useState(false);
  const [setAsideLoading, setSetAsideLoading] = useState(false);

  const triggerEnabled =
    result?.recommendation_trigger?.trigger_context === 'tax_advisory';
  const { data: recData } = useRecommendation('tax_advisory', triggerEnabled);

  const handleChange = (key: keyof TaxFormState, value: string) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const handleCalculate = async () => {
    setCalculating(true);
    setError(null);
    try {
      const input: TaxSessionInput = {
        taxpayer_type: form.taxpayer_type,
        tax_year: CURRENT_TAX_YEAR,
        annual_income: parseTHB(form.annual_income),
        annual_expenses: parseTHB(form.annual_expenses),
        allowances: parseTHB(form.allowances),
        wht_suffered: parseTHB(form.wht_suffered),
        annual_turnover: parseTHB(form.annual_turnover),
      };
      const data = await calculateTax(input);
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Calculation failed. Please try again.');
    } finally {
      setCalculating(false);
    }
  };

  const handleSetAside = async () => {
    if (!result) return;
    setSetAsideLoading(true);
    try {
      // PoC: show a confirmation toast
      alert(`Tax set-aside of ${formatTHB(result.result.net_tax_payable)} queued as a pending action. Review it on the Dashboard.`);
    } finally {
      setSetAsideLoading(false);
    }
  };

  const handleSetReminder = () => {
    alert(`Filing reminder set for ${result?.result.applicable_deadlines[0] ?? 'the applicable deadline'}.`);
  };

  return (
    <div className="space-y-6">
      {/* Input Form */}
      <Card>
        <CardHeader>
          <CardTitle>Tax Position Calculator</CardTitle>
          <Badge variant="info">Tax Year {CURRENT_TAX_YEAR}</Badge>
        </CardHeader>

        <div className="mb-4 p-3 bg-blue-50 rounded-lg border border-blue-100">
          <p className="text-xs text-blue-700">
            <span className="font-medium">Taxpayer type</span> detected from your linked KTB account.
            You may override below if needed.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {/* Taxpayer type */}
          <div className="sm:col-span-2">
            <label className="block text-xs font-medium text-gray-700 mb-1" htmlFor="taxpayer_type">
              Taxpayer Type
            </label>
            <select
              id="taxpayer_type"
              value={form.taxpayer_type}
              onChange={(e) => handleChange('taxpayer_type', e.target.value as TaxpayerType)}
              className="w-full sm:w-48 border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-400"
            >
              <option value="PIT">PIT — Individual (Personal Income Tax)</option>
              <option value="CIT">CIT — Juristic (Corporate Income Tax)</option>
            </select>
          </div>

          {/* Income */}
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1" htmlFor="annual_income">
              Annual Income (฿)
            </label>
            <input
              id="annual_income"
              type="number"
              value={form.annual_income}
              onChange={(e) => handleChange('annual_income', e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-400"
              placeholder="1200000"
            />
          </div>

          {/* Expenses */}
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1" htmlFor="annual_expenses">
              Deductible Expenses (฿)
            </label>
            <input
              id="annual_expenses"
              type="number"
              value={form.annual_expenses}
              onChange={(e) => handleChange('annual_expenses', e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-400"
              placeholder="600000"
            />
          </div>

          {/* Allowances */}
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1" htmlFor="allowances">
              Allowances &amp; Deductions (฿)
            </label>
            <input
              id="allowances"
              type="number"
              value={form.allowances}
              onChange={(e) => handleChange('allowances', e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-400"
              placeholder="150000"
            />
          </div>

          {/* WHT */}
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1" htmlFor="wht_suffered">
              WHT Already Withheld (฿)
            </label>
            <input
              id="wht_suffered"
              type="number"
              value={form.wht_suffered}
              onChange={(e) => handleChange('wht_suffered', e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-400"
              placeholder="12000"
            />
          </div>

          {/* Annual turnover for VAT check */}
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1" htmlFor="annual_turnover">
              Annual Turnover (฿) — for VAT assessment
            </label>
            <input
              id="annual_turnover"
              type="number"
              value={form.annual_turnover}
              onChange={(e) => handleChange('annual_turnover', e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-400"
              placeholder="1200000"
            />
          </div>
        </div>

        {error && (
          <div className="mt-4 flex items-start gap-2 text-sm text-red-700 bg-red-50 p-3 rounded-lg border border-red-100">
            <AlertCircle className="h-4 w-4 flex-shrink-0 mt-0.5" aria-hidden="true" />
            {error}
          </div>
        )}

        <Button
          variant="primary"
          className="w-full mt-5"
          onClick={handleCalculate}
          loading={calculating}
        >
          <Calculator className="h-4 w-4" aria-hidden="true" />
          Review &amp; Calculate
        </Button>
      </Card>

      {/* Spinner while calculating */}
      {calculating && (
        <div className="flex items-center justify-center py-8">
          <Spinner label="Calculating your tax position..." />
        </div>
      )}

      {/* Result Card */}
      {result && !calculating && (
        <>
          <Card>
            <div className="mb-6">
              <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">
                Net Income Tax Payable
              </p>
              <p className="text-4xl font-bold text-gray-900">
                {formatTHB(result.result.net_tax_payable)}
              </p>
              <p className="text-xs text-gray-400 mt-1">Tax Year {CURRENT_TAX_YEAR}</p>
            </div>

            {/* Disclaimer */}
            <div className="mb-4 p-3 bg-amber-50 rounded-lg border border-amber-100">
              <p className="text-xs text-amber-700">
                <span className="font-semibold">Guidance only — not a tax filing.</span>{' '}
                {result.result.guidance_disclaimer}
              </p>
            </div>

            {/* Key figures */}
            <div className="grid grid-cols-2 gap-3 mb-4 text-sm">
              <div className="bg-gray-50 rounded-lg p-3">
                <p className="text-xs text-gray-500 mb-0.5">Net Taxable Income</p>
                <p className="font-semibold text-gray-900">
                  {formatTHB(result.result.net_taxable_income)}
                </p>
              </div>
              <div className="bg-gray-50 rounded-lg p-3">
                <p className="text-xs text-gray-500 mb-0.5">WHT Credit Applied</p>
                <p className="font-semibold text-gray-900">
                  {formatTHB(result.result.wht_credit_applied)}
                </p>
              </div>
              {result.result.indicative_vat_monthly !== undefined && (
                <div className="bg-gray-50 rounded-lg p-3 sm:col-span-2">
                  <p className="text-xs text-gray-500 mb-0.5">
                    Indicative Monthly VAT Position
                    <span className="ml-1 text-gray-400">(monthly obligation, not year-end)</span>
                  </p>
                  <p className="font-semibold text-gray-900">
                    {formatTHB(result.result.indicative_vat_monthly)}
                  </p>
                </div>
              )}
            </div>

            {/* Tax bands — collapsible */}
            <div className="mb-4">
              <button
                onClick={() => setBandsOpen((o) => !o)}
                className="flex items-center gap-1 text-sm font-medium text-gray-700 hover:text-gray-900 transition-colors"
                aria-expanded={bandsOpen}
              >
                {bandsOpen ? (
                  <ChevronUp className="h-4 w-4" aria-hidden="true" />
                ) : (
                  <ChevronDown className="h-4 w-4" aria-hidden="true" />
                )}
                Tax by Band
              </button>
              {bandsOpen && (
                <div className="mt-2 overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b border-gray-100">
                        <th className="text-left py-1.5 text-gray-500 font-medium">Band</th>
                        <th className="text-right py-1.5 text-gray-500 font-medium">Rate</th>
                        <th className="text-right py-1.5 text-gray-500 font-medium">Tax</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-50">
                      {result.result.tax_by_band.map((band, i) => (
                        <tr key={i}>
                          <td className="py-1.5 text-gray-700">{band.range}</td>
                          <td className="py-1.5 text-right text-gray-700">{band.rate}%</td>
                          <td className="py-1.5 text-right font-medium text-gray-900">
                            {formatTHB(band.tax_amount)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            {/* Deadlines */}
            {result.result.applicable_deadlines.length > 0 && (
              <div className="mb-4">
                <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">
                  Applicable Deadlines
                </p>
                <ul className="space-y-1">
                  {result.result.applicable_deadlines.map((d, i) => (
                    <li key={i} className="text-sm text-gray-700 flex items-start gap-2">
                      <span className="text-gray-400">•</span>
                      {d}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Flags */}
            {result.result.flags.length > 0 && (
              <div className="mb-4 space-y-1">
                {result.result.flags.map((f, i) => (
                  <div key={i} className="flex items-start gap-2 text-xs text-blue-700 bg-blue-50 p-2 rounded-lg">
                    <AlertCircle className="h-3.5 w-3.5 flex-shrink-0 mt-0.5" aria-hidden="true" />
                    {f}
                  </div>
                ))}
              </div>
            )}

            {/* Suggested Actions */}
            <div className="border-t border-gray-100 pt-4">
              <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-3">
                Suggested Actions
              </p>
              <div className="flex flex-col sm:flex-row gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={handleSetAside}
                  loading={setAsideLoading}
                  className="flex-1"
                >
                  <PiggyBank className="h-4 w-4" aria-hidden="true" />
                  Create Tax Set-Aside
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={handleSetReminder}
                  className="flex-1"
                >
                  <Bell className="h-4 w-4" aria-hidden="true" />
                  Set Filing Reminder
                </Button>
              </div>
            </div>
          </Card>

          {/* Product recommendation from tax handoff */}
          {recData?.recommendation && (
            <ProductCard recommendation={recData.recommendation} />
          )}
        </>
      )}
    </div>
  );
}
