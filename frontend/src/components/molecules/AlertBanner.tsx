
import { AlertTriangle, Info, CheckCircle, XCircle } from 'lucide-react';

export type AlertBannerVariant = 'info' | 'warning' | 'success' | 'danger';

interface AlertBannerProps {
  variant: AlertBannerVariant;
  title?: string;
  message: string;
  className?: string;
}

const variantConfig = {
  info: {
    containerClass: 'bg-blue-50 border-blue-200 text-blue-800',
    Icon: Info,
    iconClass: 'text-blue-500',
  },
  warning: {
    containerClass: 'bg-amber-50 border-amber-200 text-amber-800',
    Icon: AlertTriangle,
    iconClass: 'text-amber-500',
  },
  success: {
    containerClass: 'bg-green-50 border-green-200 text-green-800',
    Icon: CheckCircle,
    iconClass: 'text-green-500',
  },
  danger: {
    containerClass: 'bg-red-50 border-red-200 text-red-800',
    Icon: XCircle,
    iconClass: 'text-red-500',
  },
};

export function AlertBanner({ variant, title, message, className = '' }: AlertBannerProps) {
  const { containerClass, Icon, iconClass } = variantConfig[variant];
  return (
    <div
      className={`flex gap-3 p-4 rounded-lg border ${containerClass} ${className}`}
      role="alert"
    >
      <Icon className={`h-5 w-5 flex-shrink-0 mt-0.5 ${iconClass}`} aria-hidden="true" />
      <div>
        {title && <p className="font-semibold text-sm">{title}</p>}
        <p className="text-sm">{message}</p>
      </div>
    </div>
  );
}
