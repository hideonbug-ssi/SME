import type { ConfidenceLevel } from '../types/forecast';

export interface ConfidenceStyle {
  label: string;
  colorClass: string;
  bgClass: string;
  textClass: string;
  dotClass: string;
}

export function getConfidenceStyle(level: ConfidenceLevel): ConfidenceStyle {
  if (level === 'high') {
    return {
      label: 'High confidence',
      colorClass: 'green',
      bgClass: 'bg-green-100',
      textClass: 'text-green-800',
      dotClass: 'bg-green-500',
    };
  }
  return {
    label: 'Low confidence — limited history',
    colorClass: 'amber',
    bgClass: 'bg-amber-100',
    textClass: 'text-amber-800',
    dotClass: 'bg-amber-500',
  };
}

/**
 * Returns a color for a balance value relative to the shortfall threshold.
 */
export function getBalanceColor(
  balance: number,
  rollingAvgMonthlyOutflow: number,
): 'green' | 'amber' | 'red' {
  const shortfallThreshold = rollingAvgMonthlyOutflow * 0.5;
  const cautionThreshold = rollingAvgMonthlyOutflow * 0.75;

  if (balance < shortfallThreshold) return 'red';
  if (balance < cautionThreshold) return 'amber';
  return 'green';
}
