import { useState } from 'react';
import { ArrowRight, CheckCircle, X } from 'lucide-react';
import { Card } from '../atoms/Card';
import { Button } from '../atoms/Button';
import { formatTHB } from '../../utils/currency';
import type { PendingAction } from '../../types/shortfall';

interface ConfirmationCardProps {
  action: PendingAction;
  onConfirm: (id: string) => Promise<void>;
  onDismiss: (id: string) => Promise<void>;
}

export function ConfirmationCard({ action, onConfirm, onDismiss }: ConfirmationCardProps) {
  const [confirming, setConfirming] = useState(false);
  const [dismissing, setDismissing] = useState(false);

  const handleConfirm = async () => {
    setConfirming(true);
    try {
      await onConfirm(action.id);
    } finally {
      setConfirming(false);
    }
  };

  const handleDismiss = async () => {
    setDismissing(true);
    try {
      await onDismiss(action.id);
    } finally {
      setDismissing(false);
    }
  };

  return (
    <Card className="border-blue-200 bg-blue-50">
      <div className="flex items-start justify-between mb-3">
        <div>
          <p className="text-xs font-medium text-blue-600 uppercase tracking-wide mb-1">
            Awaiting Your Confirmation
          </p>
          <p className="text-lg font-bold text-gray-900">{formatTHB(action.amount)}</p>
        </div>
        <div className="text-2xl font-bold text-blue-600">?</div>
      </div>

      <div className="space-y-2 mb-4">
        <div className="flex items-center gap-2 text-sm text-gray-700">
          <span className="font-medium min-w-20">From</span>
          <span className="text-gray-900">{action.source_account}</span>
        </div>
        <div className="flex items-center gap-2 text-sm text-gray-700">
          <ArrowRight className="h-4 w-4 text-gray-400" aria-hidden="true" />
        </div>
        <div className="flex items-center gap-2 text-sm text-gray-700">
          <span className="font-medium min-w-20">To</span>
          <span className="text-gray-900">{action.dest_account}</span>
        </div>
        <div className="flex items-center gap-2 text-sm text-gray-700">
          <span className="font-medium min-w-20">Purpose</span>
          <span className="text-gray-900">{action.memo}</span>
        </div>
      </div>

      <div className="flex gap-2">
        <Button
          variant="primary"
          size="sm"
          loading={confirming}
          disabled={dismissing}
          onClick={handleConfirm}
          className="flex-1"
        >
          <CheckCircle className="h-4 w-4" aria-hidden="true" />
          Confirm
        </Button>
        <Button
          variant="secondary"
          size="sm"
          loading={dismissing}
          disabled={confirming}
          onClick={handleDismiss}
          className="flex-1"
        >
          <X className="h-4 w-4" aria-hidden="true" />
          Dismiss
        </Button>
      </div>
    </Card>
  );
}
