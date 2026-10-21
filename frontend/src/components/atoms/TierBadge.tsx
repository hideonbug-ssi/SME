
import type { ShortfallTier } from '../../types/shortfall';

interface TierBadgeProps {
  tier: ShortfallTier;
  className?: string;
}

const tierConfig: Record<
  ShortfallTier,
  { label: string; className: string; dotClass: string } | null
> = {
  green: null, // Green tier is silent — render nothing
  yellow: {
    label: 'Potential Shortfall',
    className: 'bg-amber-100 text-amber-800 border border-amber-200',
    dotClass: 'bg-amber-500',
  },
  red: {
    label: 'Cash Gap Detected',
    className: 'bg-red-100 text-red-800 border border-red-200',
    dotClass: 'bg-red-500',
  },
};

export function TierBadge({ tier, className = '' }: TierBadgeProps) {
  const config = tierConfig[tier];
  if (!config) return null;

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-semibold ${config.className} ${className}`}
      role="status"
    >
      <span className={`h-2 w-2 rounded-full ${config.dotClass} animate-pulse`} aria-hidden="true" />
      {config.label}
    </span>
  );
}
