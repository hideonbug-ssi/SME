
import type { ConfidenceLevel } from '../../types/forecast';
import { getConfidenceStyle } from '../../utils/confidence';

interface ConfidencePillProps {
  level: ConfidenceLevel;
  className?: string;
}

export function ConfidencePill({ level, className = '' }: ConfidencePillProps) {
  const style = getConfidenceStyle(level);
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium ${style.bgClass} ${style.textClass} ${className}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${style.dotClass}`} aria-hidden="true" />
      {style.label}
    </span>
  );
}
