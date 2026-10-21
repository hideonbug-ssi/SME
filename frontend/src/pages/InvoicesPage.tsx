
import { InvoiceUpload } from '../components/organisms/InvoiceUpload';
import { OverdueTable } from '../components/organisms/OverdueTable';

export function InvoicesPage() {
  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Invoices</h1>
        <p className="text-sm text-gray-500 mt-1">
          Upload and manage invoices. Track overdue receivables and send reminders.
        </p>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6 mb-6">
        {/* Invoice Upload */}
        <InvoiceUpload />

        {/* Demo tip */}
        <div className="bg-blue-50 border border-blue-100 rounded-xl p-6 flex flex-col gap-3">
          <h3 className="font-semibold text-blue-900 text-sm">Demo: Invoice OCR Flow</h3>
          <p className="text-xs text-blue-700 leading-relaxed">
            Upload a PDF or image invoice. The AI vision model will extract: direction
            (payable/receivable), counterparty, amount, due date, and invoice number.
          </p>
          <div className="space-y-2">
            <div className="flex items-start gap-2">
              <span className="text-blue-500 font-bold text-xs mt-0.5">A</span>
              <p className="text-xs text-blue-700">
                High-confidence extraction (&ge;85%) → auto-recorded with green badge.
              </p>
            </div>
            <div className="flex items-start gap-2">
              <span className="text-blue-500 font-bold text-xs mt-0.5">B</span>
              <p className="text-xs text-blue-700">
                Low-confidence fields are highlighted in amber for your review before saving.
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Overdue Invoices Table */}
      <OverdueTable />
    </div>
  );
}
