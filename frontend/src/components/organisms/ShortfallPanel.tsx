
import { Shield } from 'lucide-react';
import { Card, CardHeader, CardTitle } from '../atoms/Card';
import { TierBadge } from '../atoms/TierBadge';
import { Spinner } from '../atoms/Spinner';
import { ProductCard } from '../molecules/ProductCard';
import { ConfirmationCard } from '../molecules/ConfirmationCard';
import { useShortfall } from '../../hooks/useShortfall';
import { useRecommendation } from '../../hooks/useRecommendation';
import { usePendingActions, useConfirmPendingAction, useDismissPendingAction } from '../../hooks/usePendingActions';
import { formatTHB } from '../../utils/currency';
import { formatDate } from '../../utils/dates';
import type { TriggerContext } from '../../types/recommendation';

function useToast() {
  const show = (msg: string) => {
    // Simple alert for PoC
    console.info('[Toast]', msg);
  };
  return { show };
}

export function ShortfallPanel() {
  const { data: shortfall, isLoading: shortfallLoading, isError: shortfallError } = useShortfall();
  const { data: pendingActionsData } = usePendingActions();
  const confirmMutation = useConfirmPendingAction();
  const dismissMutation = useDismissPendingAction();
  const toast = useToast();

  // Determine trigger context from shortfall tier
  const triggerContext: TriggerContext | null =
    shortfall?.tier === 'yellow'
      ? 'shortfall_yellow'
      : shortfall?.tier === 'red'
        ? 'shortfall_red'
        : shortfall?.tier === 'green'
          ? 'opportunity'
          : null;

  const { data: recData, isLoading: recLoading } = useRecommendation(
    triggerContext ?? 'opportunity',
    triggerContext !== null,
  );

  const pendingAction = pendingActionsData?.pending_actions[0] ?? null;

  const handleConfirm = async (id: string) => {
    await confirmMutation.mutateAsync(id);
    toast.show('Transfer confirmed successfully.');
  };

  const handleDismiss = async (id: string) => {
    await dismissMutation.mutateAsync(id);
    toast.show('Action dismissed.');
  };

  return (
    <div className="space-y-4">
      {/* Shortfall Status Card */}
      <Card>
        <CardHeader>
          <CardTitle>Cash Position</CardTitle>
          <Shield className="h-5 w-5 text-gray-400" aria-hidden="true" />
        </CardHeader>

        {shortfallLoading && (
          <div className="flex items-center justify-center h-24">
            <Spinner size="sm" label="Analysing position..." />
          </div>
        )}

        {shortfallError && (
          <p className="text-sm text-red-600">Failed to load cash position status.</p>
        )}

        {shortfall && (
          <>
            {/* Tier badge — green is silent */}
            {shortfall.tier !== 'green' && (
              <div className="mb-4">
                <TierBadge tier={shortfall.tier} />
              </div>
            )}

            {/* Green tier: positive message */}
            {shortfall.tier === 'green' && (
              <div className="flex items-center gap-3 py-2">
                <div className="h-3 w-3 rounded-full bg-green-500" />
                <p className="text-sm text-green-700 font-medium">
                  Cash position looks healthy. No action needed.
                </p>
              </div>
            )}

            {/* Yellow / Red: shortfall detail */}
            {(shortfall.tier === 'yellow' || shortfall.tier === 'red') &&
              shortfall.shortfall_amount_thb &&
              shortfall.shortfall_date && (
                <div className="mt-3 p-4 rounded-lg bg-amber-50 border border-amber-100">
                  <p className="text-sm text-gray-800">
                    A projected cash gap of{' '}
                    <span className="font-semibold text-amber-700">
                      {formatTHB(shortfall.shortfall_amount_thb)}
                    </span>{' '}
                    is expected around{' '}
                    <span className="font-semibold">
                      {formatDate(shortfall.shortfall_date)}
                    </span>
                    .
                  </p>
                </div>
              )}

            {/* Red: recovery plan */}
            {shortfall.tier === 'red' && shortfall.recovery_plan && (
              <div className="mt-3 p-4 rounded-lg bg-red-50 border border-red-100">
                <p className="text-xs font-semibold text-red-700 uppercase tracking-wide mb-1">
                  Recovery Plan
                </p>
                <p className="text-sm text-gray-700">{shortfall.recovery_plan}</p>
              </div>
            )}
          </>
        )}
      </Card>

      {/* Pending Action Confirmation Card */}
      {pendingAction && (
        <ConfirmationCard
          action={pendingAction}
          onConfirm={handleConfirm}
          onDismiss={handleDismiss}
        />
      )}

      {/* Product Recommendation Card */}
      {recLoading && triggerContext !== null && (
        <div className="flex items-center justify-center h-24">
          <Spinner size="sm" label="Finding best product..." />
        </div>
      )}

      {recData?.recommendation && (
        <ProductCard recommendation={recData.recommendation} />
      )}
    </div>
  );
}
