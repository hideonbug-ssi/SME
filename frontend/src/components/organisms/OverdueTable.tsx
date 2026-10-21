import { useState } from 'react';
import { Eye, X, Send, Clock } from 'lucide-react';
import { Card, CardHeader, CardTitle } from '../atoms/Card';
import { Badge, type BadgeVariant } from '../atoms/Badge';
import { Button } from '../atoms/Button';
import { Spinner } from '../atoms/Spinner';
import { useOverdueInvoices } from '../../hooks/useOverdueInvoices';
import { approveReminder, rejectReminder } from '../../api/invoices';
import { useQueryClient } from '@tanstack/react-query';
import { OVERDUE_INVOICES_QUERY_KEY } from '../../hooks/useOverdueInvoices';
import { formatTHB } from '../../utils/currency';
import { formatDate, isToday } from '../../utils/dates';
import type { OverdueInvoice, OverdueStage } from '../../types/invoice';

const stageConfig: Record<OverdueStage, { label: string; variant: BadgeVariant }> = {
  stage1: { label: 'Stage 1', variant: 'blue' },
  stage2: { label: 'Stage 2', variant: 'amber' },
  final: { label: 'Final', variant: 'red' },
};

interface DraftModalProps {
  invoice: OverdueInvoice;
  onClose: () => void;
  onApprove: (id: string) => Promise<void>;
  onReject: (id: string) => Promise<void>;
}

function DraftModal({ invoice, onClose, onApprove, onReject }: DraftModalProps) {
  const [approving, setApproving] = useState(false);
  const [rejecting, setRejecting] = useState(false);
  const contactedToday = isToday(invoice.last_reminder_sent ?? '');

  const handleApprove = async () => {
    setApproving(true);
    try {
      await onApprove(invoice.id);
      onClose();
    } finally {
      setApproving(false);
    }
  };

  const handleReject = async () => {
    setRejecting(true);
    try {
      await onReject(invoice.id);
      onClose();
    } finally {
      setRejecting(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="modal-title"
    >
      <div className="bg-white rounded-xl shadow-xl w-full max-w-lg mx-4">
        <div className="flex items-center justify-between p-6 border-b border-gray-100">
          <h2 id="modal-title" className="font-semibold text-gray-900">
            Draft Reminder — {invoice.invoice_no}
          </h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 transition-colors"
            aria-label="Close modal"
          >
            <X className="h-5 w-5" aria-hidden="true" />
          </button>
        </div>

        <div className="p-6">
          <div className="bg-gray-50 rounded-lg p-4 mb-4 text-sm text-gray-700 whitespace-pre-wrap leading-relaxed">
            {invoice.reminder_draft ??
              `Dear ${invoice.customer_name},\n\nThis is a reminder regarding invoice ${invoice.invoice_no} for ${formatTHB(invoice.amount_thb - invoice.amount_paid_thb)}, which was due on ${formatDate(invoice.due_date)} and is now ${invoice.days_overdue} days overdue.\n\nPlease arrange payment at your earliest convenience.\n\nBest regards,\nYour SME CFO Agent`}
          </div>

          {contactedToday && (
            <div className="flex items-center gap-2 text-amber-700 bg-amber-50 px-3 py-2 rounded-lg text-sm mb-4 border border-amber-200">
              <Clock className="h-4 w-4" aria-hidden="true" />
              <span>Already contacted today — send is blocked by the 1/day rule.</span>
            </div>
          )}

          <div className="flex gap-3">
            <Button
              variant="primary"
              onClick={handleApprove}
              loading={approving}
              disabled={rejecting || contactedToday}
              className="flex-1"
              title={contactedToday ? 'Blocked: already contacted today' : undefined}
            >
              <Send className="h-4 w-4" aria-hidden="true" />
              Approve & Send
            </Button>
            <Button
              variant="secondary"
              onClick={handleReject}
              loading={rejecting}
              disabled={approving}
              className="flex-1"
            >
              Reject
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

export function OverdueTable() {
  const { data, isLoading, isError } = useOverdueInvoices();
  const queryClient = useQueryClient();
  const [selectedInvoice, setSelectedInvoice] = useState<OverdueInvoice | null>(null);

  const handleApprove = async (id: string) => {
    await approveReminder(id);
    await queryClient.invalidateQueries({ queryKey: OVERDUE_INVOICES_QUERY_KEY });
  };

  const handleReject = async (id: string) => {
    await rejectReminder(id);
    await queryClient.invalidateQueries({ queryKey: OVERDUE_INVOICES_QUERY_KEY });
  };

  const invoices = data?.invoices ?? [];

  return (
    <>
      <Card padding="none">
        <div className="p-6 pb-4">
          <CardHeader>
            <CardTitle>Overdue Invoices</CardTitle>
            {invoices.length > 0 && (
              <Badge variant="danger">{invoices.length} overdue</Badge>
            )}
          </CardHeader>
        </div>

        {isLoading && (
          <div className="flex items-center justify-center py-12">
            <Spinner label="Loading overdue invoices..." />
          </div>
        )}

        {isError && (
          <div className="px-6 pb-6">
            <p className="text-sm text-red-600">Failed to load overdue invoices.</p>
          </div>
        )}

        {!isLoading && invoices.length === 0 && (
          <div className="flex flex-col items-center justify-center py-12 gap-2 text-center px-6">
            <div className="h-12 w-12 rounded-full bg-green-100 flex items-center justify-center mb-1">
              <span className="text-green-600 text-xl">✓</span>
            </div>
            <p className="text-sm font-medium text-gray-600">No overdue invoices</p>
            <p className="text-xs text-gray-400">All receivables are up to date.</p>
          </div>
        )}

        {invoices.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100 bg-gray-50">
                  <th className="text-left px-6 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide">
                    Invoice No.
                  </th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide">
                    Customer
                  </th>
                  <th className="text-right px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide">
                    Amount
                  </th>
                  <th className="text-right px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide">
                    Remaining
                  </th>
                  <th className="text-right px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide">
                    Days Overdue
                  </th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide">
                    Stage
                  </th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide">
                    Last Contacted
                  </th>
                  <th className="text-right px-6 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {invoices.map((inv) => {
                  const stage = stageConfig[inv.stage];
                  const remaining = inv.amount_thb - inv.amount_paid_thb;
                  const contactedToday = isToday(inv.last_reminder_sent ?? '');

                  return (
                    <tr key={inv.id} className="hover:bg-gray-50 transition-colors">
                      <td className="px-6 py-4 font-medium text-gray-900">{inv.invoice_no}</td>
                      <td className="px-4 py-4 text-gray-700">{inv.customer_name}</td>
                      <td className="px-4 py-4 text-right text-gray-900">
                        {formatTHB(inv.amount_thb)}
                      </td>
                      <td className="px-4 py-4 text-right font-semibold text-red-600">
                        {formatTHB(remaining)}
                      </td>
                      <td className="px-4 py-4 text-right">
                        <span
                          className={`font-medium ${
                            inv.days_overdue > 90
                              ? 'text-red-600'
                              : inv.days_overdue > 30
                                ? 'text-amber-600'
                                : 'text-gray-700'
                          }`}
                        >
                          {inv.days_overdue}d
                        </span>
                      </td>
                      <td className="px-4 py-4">
                        <Badge variant={stage.variant}>{stage.label}</Badge>
                      </td>
                      <td className="px-4 py-4 text-gray-500 text-xs">
                        {inv.last_contacted ? (
                          <div>
                            <span>{formatDate(inv.last_contacted)}</span>
                            {contactedToday && (
                              <div className="mt-0.5">
                                <Badge variant="gray">Today</Badge>
                              </div>
                            )}
                          </div>
                        ) : (
                          <span className="text-gray-400">Never</span>
                        )}
                      </td>
                      <td className="px-6 py-4 text-right">
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={() => setSelectedInvoice(inv)}
                        >
                          <Eye className="h-3.5 w-3.5" aria-hidden="true" />
                          View Draft
                        </Button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {selectedInvoice && (
        <DraftModal
          invoice={selectedInvoice}
          onClose={() => setSelectedInvoice(null)}
          onApprove={handleApprove}
          onReject={handleReject}
        />
      )}
    </>
  );
}
