import type { LucideIcon } from 'lucide-react';
import { cn } from '@/lib/utils';

interface StatCardProps {
  label: string;
  value: number | string;
  icon: LucideIcon;
  iconColor?: string;
  trend?: string;
  className?: string;
}

export function StatCard({
  label,
  value,
  icon: Icon,
  iconColor = 'text-accent-blue',
  trend,
  className,
}: StatCardProps) {
  return (
    <div
      className={cn(
        'rounded-lg border border-border-subtle bg-surface-raised p-4 transition-colors hover:border-border-default',
        className
      )}
    >
      <div className="flex items-start justify-between">
        <div className="flex flex-col gap-1">
          <span className="text-xs font-medium uppercase tracking-wider text-text-tertiary">
            {label}
          </span>
          <span className="text-2xl font-semibold text-text-primary">
            {typeof value === 'number' ? value.toLocaleString() : value}
          </span>
          {trend && (
            <span className="text-xs text-text-secondary">{trend}</span>
          )}
        </div>
        <div
          className={cn(
            'flex h-10 w-10 items-center justify-center rounded-lg bg-surface-overlay',
            iconColor
          )}
        >
          <Icon className="h-5 w-5" />
        </div>
      </div>
    </div>
  );
}
