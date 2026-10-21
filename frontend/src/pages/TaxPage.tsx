
import { TaxChatPanel } from '../components/organisms/TaxChatPanel';

export function TaxPage() {
  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Tax Assistant</h1>
        <p className="text-sm text-gray-500 mt-1">
          Calculate your indicative tax position and explore tax-saving opportunities.
        </p>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        {/* Main tax panel */}
        <div className="xl:col-span-2">
          <TaxChatPanel />
        </div>

        {/* Info sidebar */}
        <div className="space-y-4">
          <div className="bg-amber-50 border border-amber-100 rounded-xl p-5">
            <h3 className="font-semibold text-amber-900 text-sm mb-2">Important Notice</h3>
            <p className="text-xs text-amber-700 leading-relaxed">
              This tool provides <strong>guidance only</strong> and is not a tax filing or
              certified tax advice. Always consult a licensed tax professional before filing.
            </p>
          </div>

          <div className="bg-gray-50 border border-gray-100 rounded-xl p-5">
            <h3 className="font-semibold text-gray-900 text-sm mb-3">How It Works</h3>
            <ol className="space-y-2">
              {[
                'Your taxpayer type is auto-detected from your KTB account.',
                'Review pre-filled income and expense figures.',
                'Click Calculate to get your estimated tax liability.',
                'View band breakdown, WHT credits, and VAT position.',
                'Create a tax set-aside or set a filing reminder.',
              ].map((step, i) => (
                <li key={i} className="flex gap-2.5 text-xs text-gray-600">
                  <span className="h-4 w-4 rounded-full bg-blue-100 text-blue-700 font-semibold flex items-center justify-center flex-shrink-0 text-[10px]">
                    {i + 1}
                  </span>
                  {step}
                </li>
              ))}
            </ol>
          </div>
        </div>
      </div>
    </div>
  );
}
