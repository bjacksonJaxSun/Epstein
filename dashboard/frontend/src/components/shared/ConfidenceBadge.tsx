import { cn } from '@/lib/utils';

interface ConfidenceBadgeProps {
  level: string;
  className?: string;
}

const levelStyles: Record<string, string> = {
  high: 'bg-confidence-high/15 text-confidence-high border-confidence-high/30',
  medium:
    'bg-confidence-medium/15 text-confidence-medium border-confidence-medium/30',
  low: 'bg-confidence-low/15 text-confidence-low border-confidence-low/30',
};

export function ConfidenceBadge({ level, className }: ConfidenceBadgeProps) {
  const normalized = level.toLowerCase();
  const style =
    levelStyles[normalized] ??
    'bg-border-subtle text-text-secondary border-border-default';

  return (
    <span
      className={cn(
        'inline-flex items-center rounded-sm border px-1.5 py-0.5 text-xs font-medium uppercase tracking-wider',
        style,
        className
      )}
    >
      {level}
    </span>
  );
}
