
import { AlertTriangle, Edit3 } from 'lucide-react';

interface InvoiceFieldRowProps {
  label: string;
  value: string;
  fieldKey: string;
  confidence?: number;
  editable?: boolean;
  onChange?: (key: string, value: string) => void;
}

const CONFIDENCE_THRESHOLD = 0.85;

export function InvoiceFieldRow({
  label,
  value,
  fieldKey,
  confidence,
  editable = false,
  onChange,
}: InvoiceFieldRowProps) {
  const isLowConfidence =
    confidence !== undefined && confidence < CONFIDENCE_THRESHOLD;

  return (
    <div
      className={`flex items-start gap-3 p-3 rounded-lg ${
        isLowConfidence ? 'bg-amber-50 border border-amber-200' : 'bg-gray-50'
      }`}
    >
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-xs font-medium text-gray-500">{label}</span>
          {isLowConfidence && (
            <div className="flex items-center gap-1 text-amber-600">
              <AlertTriangle className="h-3.5 w-3.5" aria-hidden="true" />
              <span className="text-xs">Low confidence</span>
            </div>
          )}
        </div>
        {editable && isLowConfidence && onChange ? (
          <input
            type="text"
            defaultValue={value}
            onChange={(e) => onChange(fieldKey, e.target.value)}
            className="w-full text-sm text-gray-900 bg-white border border-amber-300 rounded px-2 py-1 focus:outline-none focus:ring-2 focus:ring-amber-400"
            aria-label={`Edit ${label}`}
          />
        ) : (
          <p className="text-sm font-medium text-gray-900 truncate">{value || '—'}</p>
        )}
      </div>
      {isLowConfidence && editable && (
        <Edit3 className="h-4 w-4 text-amber-500 flex-shrink-0 mt-1" aria-hidden="true" />
      )}
      {confidence !== undefined && (
        <span className="text-xs text-gray-400 flex-shrink-0 mt-1">
          {Math.round(confidence * 100)}%
        </span>
      )}
    </div>
  );
}
