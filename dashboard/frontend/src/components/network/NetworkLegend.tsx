import { cn } from '@/lib/utils';

interface NetworkLegendProps {
  visible: boolean;
}

const NODE_TYPES = [
  { type: 'Person', color: '#4A9EFF', shape: 'circle' },
  { type: 'Organization', color: '#A855F7', shape: 'diamond' },
  { type: 'Location', color: '#22C55E', shape: 'square' },
  { type: 'Event', color: '#FFB020', shape: 'triangle' },
];

const CONFIDENCE_LEVELS = [
  { level: 'High', opacity: 1.0 },
  { level: 'Medium', opacity: 0.6 },
  { level: 'Low', opacity: 0.3 },
];

function ShapeIcon({
  shape,
  color,
  size = 14,
}: {
  shape: string;
  color: string;
  size?: number;
}) {
  const half = size / 2;

  switch (shape) {
    case 'circle':
      return (
        <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
          <circle cx={half} cy={half} r={half - 1} fill={color} />
        </svg>
      );
    case 'diamond':
      return (
        <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
          <polygon
            points={`${half},1 ${size - 1},${half} ${half},${size - 1} 1,${half}`}
            fill={color}
          />
        </svg>
      );
    case 'square':
      return (
        <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
          <rect x={1} y={1} width={size - 2} height={size - 2} fill={color} />
        </svg>
      );
    case 'triangle':
      return (
        <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
          <polygon
            points={`${half},1 ${size - 1},${size - 1} 1,${size - 1}`}
            fill={color}
          />
        </svg>
      );
    default:
      return null;
  }
}

export function NetworkLegend({ visible }: NetworkLegendProps) {
  if (!visible) return null;

  return (
    <div
      className={cn(
        'absolute right-3 top-3 z-20 rounded-lg border border-border-subtle',
        'bg-surface-raised/95 p-3 backdrop-blur-sm shadow-lg',
        'min-w-[180px]'
      )}
    >
      <h4 className="mb-2.5 text-xs font-semibold uppercase tracking-wider text-text-tertiary">
        Node Types
      </h4>
      <div className="flex flex-col gap-1.5">
        {NODE_TYPES.map((item) => (
          <div key={item.type} className="flex items-center gap-2">
            <ShapeIcon shape={item.shape} color={item.color} />
            <span className="text-xs text-text-secondary">{item.type}</span>
          </div>
        ))}
      </div>

      <div className="my-2.5 border-t border-border-subtle" />

      <h4 className="mb-2.5 text-xs font-semibold uppercase tracking-wider text-text-tertiary">
        Edge Confidence
      </h4>
      <div className="flex flex-col gap-1.5">
        {CONFIDENCE_LEVELS.map((item) => (
          <div key={item.level} className="flex items-center gap-2">
            <div className="flex h-[14px] w-[20px] items-center">
              <div
                className="h-[2px] w-full rounded-full"
                style={{
                  backgroundColor: '#4A9EFF',
                  opacity: item.opacity,
                }}
              />
            </div>
            <span className="text-xs text-text-secondary">
              {item.level} ({Math.round(item.opacity * 100)}%)
            </span>
          </div>
        ))}
      </div>

      <div className="my-2.5 border-t border-border-subtle" />

      <h4 className="mb-2.5 text-xs font-semibold uppercase tracking-wider text-text-tertiary">
        Line Style
      </h4>
      <div className="flex flex-col gap-1.5">
        <div className="flex items-center gap-2">
          <div className="flex h-[14px] w-[20px] items-center">
            <div className="h-[2px] w-full rounded-full bg-text-secondary" />
          </div>
          <span className="text-xs text-text-secondary">Confirmed</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex h-[14px] w-[20px] items-center">
            <svg width="20" height="2" viewBox="0 0 20 2">
              <line
                x1="0"
                y1="1"
                x2="20"
                y2="1"
                stroke="#A0A0B8"
                strokeWidth="2"
                strokeDasharray="4 2"
              />
            </svg>
          </div>
          <span className="text-xs text-text-secondary">Suggested</span>
        </div>
      </div>
    </div>
  );
}
