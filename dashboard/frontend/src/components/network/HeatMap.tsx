import { useMemo, useState, useRef, useEffect } from 'react';
import { useSelectionStore } from '@/stores/useSelectionStore';
import { LoadingSpinner } from '@/components/shared';

export type FrequencyMetric = 'documents' | 'events' | 'relationships' | 'financialCount' | 'financialTotal' | 'media' | 'total';

export interface EntityFrequency {
  id: number;
  name: string;
  entityType: string;
  primaryRole?: string;
  documentCount: number;
  eventCount: number;
  relationshipCount: number;
  financialCount: number;
  financialTotal: number;
  mediaCount: number;
  totalMentions: number;
}

interface HeatMapProps {
  data: EntityFrequency[] | undefined;
  isLoading: boolean;
  metric: FrequencyMetric;
  onNodeClick?: (id: number, name: string) => void;
}

const METRIC_LABELS: Record<FrequencyMetric, string> = {
  documents: 'Document References',
  events: 'Event Participation',
  relationships: 'Relationships',
  financialCount: 'Financial Transactions',
  financialTotal: 'Financial Amount ($)',
  media: 'Media Appearances',
  total: 'Total Mentions',
};

function getMetricValue(entity: EntityFrequency, metric: FrequencyMetric): number {
  switch (metric) {
    case 'documents':
      return entity.documentCount;
    case 'events':
      return entity.eventCount;
    case 'relationships':
      return entity.relationshipCount;
    case 'financialCount':
      return entity.financialCount;
    case 'financialTotal':
      return entity.financialTotal;
    case 'media':
      return entity.mediaCount;
    case 'total':
      return entity.totalMentions;
    default:
      return entity.totalMentions;
  }
}

function getHeatColor(value: number, maxValue: number): string {
  if (maxValue === 0) return 'rgba(74, 158, 255, 0.3)';
  const intensity = Math.min(value / maxValue, 1);

  // Color gradient from blue (low) to purple to red (high)
  if (intensity < 0.33) {
    const t = intensity / 0.33;
    return `rgba(${Math.round(74 + t * (168 - 74))}, ${Math.round(158 - t * 73)}, ${Math.round(255 - t * 8)}, ${0.4 + intensity * 0.4})`;
  } else if (intensity < 0.66) {
    const t = (intensity - 0.33) / 0.33;
    return `rgba(${Math.round(168 + t * (239 - 168))}, ${Math.round(85 - t * 14)}, ${Math.round(247 - t * 160)}, ${0.5 + intensity * 0.3})`;
  } else {
    const t = (intensity - 0.66) / 0.34;
    return `rgba(${Math.round(239 + t * (16))}, ${Math.round(71 - t * 20)}, ${Math.round(87 - t * 47)}, ${0.6 + intensity * 0.3})`;
  }
}

function formatValue(value: number, metric: FrequencyMetric): string {
  if (metric === 'financialTotal') {
    if (value >= 1e9) return `$${(value / 1e9).toFixed(1)}B`;
    if (value >= 1e6) return `$${(value / 1e6).toFixed(1)}M`;
    if (value >= 1e3) return `$${(value / 1e3).toFixed(1)}K`;
    return `$${value.toLocaleString()}`;
  }
  return value.toLocaleString();
}

interface PackedCircle {
  entity: EntityFrequency;
  x: number;
  y: number;
  radius: number;
  value: number;
}

function packCircles(
  entities: EntityFrequency[],
  metric: FrequencyMetric,
  width: number,
  height: number
): PackedCircle[] {
  const filtered = entities.filter(e => getMetricValue(e, metric) > 0);
  if (filtered.length === 0) return [];

  const values = filtered.map(e => getMetricValue(e, metric));
  const maxValue = Math.max(...values);
  const minRadius = 20;
  const maxRadius = Math.min(width, height) / 6;

  // Sort by value descending for better packing
  const sorted = [...filtered].sort((a, b) => getMetricValue(b, metric) - getMetricValue(a, metric));

  const circles: PackedCircle[] = [];
  const centerX = width / 2;
  const centerY = height / 2;

  for (const entity of sorted) {
    const value = getMetricValue(entity, metric);
    const normalizedValue = maxValue > 0 ? value / maxValue : 0;
    const radius = minRadius + normalizedValue * (maxRadius - minRadius);

    // Find position using spiral placement
    let placed = false;
    let angle = 0;
    let distance = 0;
    const step = 5;
    const angleStep = 0.5;

    while (!placed && distance < Math.max(width, height)) {
      const x = centerX + Math.cos(angle) * distance;
      const y = centerY + Math.sin(angle) * distance;

      // Check if this position collides with existing circles
      let collision = false;
      for (const existing of circles) {
        const dx = x - existing.x;
        const dy = y - existing.y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < radius + existing.radius + 4) {
          collision = true;
          break;
        }
      }

      // Check bounds (allow circles to overflow edges by up to half their radius)
      const overflow = radius * 0.5;
      if (!collision && x - radius >= -overflow && x + radius <= width + overflow && y - radius >= -overflow && y + radius <= height + overflow) {
        circles.push({ entity, x, y, radius, value });
        placed = true;
      }

      angle += angleStep;
      if (angle >= Math.PI * 2) {
        angle = 0;
        distance += step;
      }
    }

    // Skip circles that can't be placed rather than stacking at center
    if (!placed) {
      continue;
    }
  }

  return circles;
}

export function HeatMap({ data, isLoading, metric, onNodeClick }: HeatMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 });
  const [hoveredNode, setHoveredNode] = useState<PackedCircle | null>(null);
  const [tooltipPos, setTooltipPos] = useState({ x: 0, y: 0 });
  const selectEntity = useSelectionStore((s) => s.selectEntity);

  useEffect(() => {
    const updateDimensions = () => {
      if (containerRef.current) {
        const rect = containerRef.current.getBoundingClientRect();
        setDimensions({ width: rect.width, height: rect.height });
      }
    };

    updateDimensions();
    const resizeObserver = new ResizeObserver(updateDimensions);
    if (containerRef.current) {
      resizeObserver.observe(containerRef.current);
    }

    return () => resizeObserver.disconnect();
  }, []);

  const circles = useMemo(() => {
    if (!data) return [];
    return packCircles(data, metric, dimensions.width, dimensions.height);
  }, [data, metric, dimensions]);

  const maxValue = useMemo(() => {
    if (circles.length === 0) return 0;
    return Math.max(...circles.map(c => c.value));
  }, [circles]);

  const handleMouseMove = (e: React.MouseEvent) => {
    const rect = containerRef.current?.getBoundingClientRect();
    if (rect) {
      setTooltipPos({
        x: e.clientX - rect.left,
        y: e.clientY - rect.top,
      });
    }
  };

  const handleClick = (circle: PackedCircle) => {
    selectEntity(String(circle.entity.id), circle.entity.entityType);
    onNodeClick?.(circle.entity.id, circle.entity.name);
  };

  return (
    <div
      ref={containerRef}
      className="relative flex-1 rounded-lg border border-border-subtle bg-surface-sunken overflow-hidden"
      style={{ minHeight: '500px' }}
    >
      {isLoading && (
        <div className="absolute inset-0 z-10 flex items-center justify-center bg-surface-base/60 backdrop-blur-sm">
          <LoadingSpinner size="lg" />
        </div>
      )}

      {!data && !isLoading && (
        <div className="absolute inset-0 z-10 flex flex-col items-center justify-center gap-3">
          <svg
            className="h-12 w-12 text-text-disabled"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={1.5}
          >
            <circle cx="12" cy="12" r="9" />
            <circle cx="12" cy="12" r="5" />
            <circle cx="12" cy="12" r="1" />
          </svg>
          <p className="text-sm text-text-disabled">No frequency data available</p>
        </div>
      )}

      {circles.length === 0 && data && !isLoading && (
        <div className="absolute inset-0 z-10 flex flex-col items-center justify-center gap-3">
          <svg
            className="h-12 w-12 text-text-disabled"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={1.5}
          >
            <circle cx="12" cy="12" r="9" />
          </svg>
          <p className="text-sm text-text-disabled">
            No entities with {METRIC_LABELS[metric].toLowerCase()}
          </p>
        </div>
      )}

      <svg width={dimensions.width} height={dimensions.height} className="absolute inset-0">
        {circles.map((circle) => (
          <g
            key={circle.entity.id}
            transform={`translate(${circle.x}, ${circle.y})`}
            className="cursor-pointer transition-transform hover:scale-105"
            onClick={() => handleClick(circle)}
            onMouseEnter={() => setHoveredNode(circle)}
            onMouseLeave={() => setHoveredNode(null)}
            onMouseMove={handleMouseMove}
          >
            <circle
              r={circle.radius}
              fill={getHeatColor(circle.value, maxValue)}
              stroke={hoveredNode?.entity.id === circle.entity.id ? '#fff' : 'rgba(255,255,255,0.2)'}
              strokeWidth={hoveredNode?.entity.id === circle.entity.id ? 2 : 1}
              className="transition-all duration-150"
            />
            {circle.radius > 25 && (
              <text
                textAnchor="middle"
                dy="0.35em"
                className="fill-white text-[10px] font-medium pointer-events-none"
                style={{ textShadow: '0 1px 2px rgba(0,0,0,0.5)' }}
              >
                {circle.entity.name.length > 12
                  ? circle.entity.name.slice(0, 10) + '...'
                  : circle.entity.name}
              </text>
            )}
          </g>
        ))}
      </svg>

      {/* Tooltip */}
      {hoveredNode && (
        <div
          className="absolute z-20 pointer-events-none px-3 py-2 rounded-lg bg-surface-overlay border border-border-subtle shadow-lg"
          style={{
            left: tooltipPos.x + 10,
            top: tooltipPos.y - 10,
            transform: tooltipPos.x > dimensions.width / 2 ? 'translateX(-100%)' : undefined,
          }}
        >
          <div className="text-sm font-semibold text-text-primary">{hoveredNode.entity.name}</div>
          {hoveredNode.entity.primaryRole && (
            <div className="text-xs text-text-tertiary">{hoveredNode.entity.primaryRole}</div>
          )}
          <div className="mt-1 text-xs text-accent-blue font-medium">
            {METRIC_LABELS[metric]}: {formatValue(hoveredNode.value, metric)}
          </div>
        </div>
      )}

      {/* Legend */}
      <div className="absolute bottom-4 right-4 flex items-center gap-2 rounded-lg bg-surface-overlay/90 border border-border-subtle px-3 py-2">
        <span className="text-xs text-text-tertiary">Low</span>
        <div className="flex gap-0.5">
          {[0.1, 0.33, 0.5, 0.66, 0.9].map((intensity, i) => (
            <div
              key={i}
              className="w-4 h-4 rounded-full"
              style={{ backgroundColor: getHeatColor(intensity * maxValue, maxValue) }}
            />
          ))}
        </div>
        <span className="text-xs text-text-tertiary">High</span>
      </div>
    </div>
  );
}
