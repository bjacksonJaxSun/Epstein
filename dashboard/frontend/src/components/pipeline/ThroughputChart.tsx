import { useEffect, useRef, useState, useCallback } from 'react';
import { select } from 'd3-selection';
import { scaleTime, scaleLinear } from 'd3-scale';
import { axisBottom, axisLeft } from 'd3-axis';
import { line, curveMonotoneX } from 'd3-shape';

export interface ThroughputBucket {
  timestamp: string;
  hostname: string;
  completed: number;
}

interface TooltipData {
  x: number;
  y: number;
  time: Date;
  values: { hostname: string; completed: number; color: string }[];
}

const NODE_COLORS = ['#4A9EFF', '#A855F7', '#22C55E', '#FFB020'];
const TOTAL_COLOR = '#E8E8F0';

interface ThroughputChartProps {
  data: ThroughputBucket[] | undefined;
  height?: number;
}

export function ThroughputChart({ data, height = 280 }: ThroughputChartProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [containerWidth, setContainerWidth] = useState(0);
  const [tooltip, setTooltip] = useState<TooltipData | null>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        setContainerWidth(entry.contentRect.width);
      }
    });

    observer.observe(container);
    setContainerWidth(container.clientWidth);

    return () => observer.disconnect();
  }, []);

  const handleMouseMove = useCallback(
    (
      event: MouseEvent,
      xScale: d3.ScaleTime<number, number>,
      allTimestamps: Date[],
      seriesMap: Map<string, Map<number, number>>,
      hostnames: string[],
      totalMap: Map<number, number>,
      margin: { left: number; top: number },
    ) => {
      const svgEl = svgRef.current;
      if (!svgEl) return;
      const rect = svgEl.getBoundingClientRect();
      const mouseX = event.clientX - rect.left - margin.left;

      // Find nearest timestamp
      let nearestIdx = 0;
      let nearestDist = Infinity;
      for (let i = 0; i < allTimestamps.length; i++) {
        const dist = Math.abs(xScale(allTimestamps[i]) - mouseX);
        if (dist < nearestDist) {
          nearestDist = dist;
          nearestIdx = i;
        }
      }

      const time = allTimestamps[nearestIdx];
      const timeKey = time.getTime();

      const values: TooltipData['values'] = hostnames.map((h, i) => ({
        hostname: h,
        completed: seriesMap.get(h)?.get(timeKey) ?? 0,
        color: NODE_COLORS[i % NODE_COLORS.length],
      }));

      values.push({
        hostname: 'Total',
        completed: totalMap.get(timeKey) ?? 0,
        color: TOTAL_COLOR,
      });

      setTooltip({
        x: xScale(time) + margin.left,
        y: event.clientY - rect.top,
        time,
        values,
      });
    },
    [],
  );

  useEffect(() => {
    if (!svgRef.current || !data || data.length === 0 || containerWidth === 0) return;

    const svg = select(svgRef.current);
    svg.selectAll('*').remove();

    const margin = { top: 16, right: 120, bottom: 32, left: 48 };
    const width = containerWidth;
    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;

    // Build series data
    const hostnames = [...new Set(data.map((d) => d.hostname))].sort();
    const seriesMap = new Map<string, Map<number, number>>();
    const timestampSet = new Set<number>();

    for (const h of hostnames) {
      seriesMap.set(h, new Map());
    }

    for (const d of data) {
      const t = new Date(d.timestamp).getTime();
      timestampSet.add(t);
      seriesMap.get(d.hostname)!.set(t, d.completed);
    }

    const allTimestamps = [...timestampSet].sort((a, b) => a - b).map((t) => new Date(t));

    // Compute totals per timestamp
    const totalMap = new Map<number, number>();
    for (const t of allTimestamps) {
      const tKey = t.getTime();
      let sum = 0;
      for (const h of hostnames) {
        sum += seriesMap.get(h)?.get(tKey) ?? 0;
      }
      totalMap.set(tKey, sum);
    }

    // Scales
    const xScale = scaleTime()
      .domain([allTimestamps[0], allTimestamps[allTimestamps.length - 1]])
      .range([0, innerWidth]);

    const maxVal = Math.max(
      ...allTimestamps.map((t) => totalMap.get(t.getTime()) ?? 0),
      1,
    );

    const yScale = scaleLinear()
      .domain([0, maxVal * 1.1])
      .nice()
      .range([innerHeight, 0]);

    svg.attr('width', width).attr('height', height);

    const g = svg.append('g').attr('transform', `translate(${margin.left},${margin.top})`);

    // Grid lines
    const yTicks = yScale.ticks(5);
    g.append('g')
      .attr('class', 'grid')
      .selectAll('line')
      .data(yTicks)
      .join('line')
      .attr('x1', 0)
      .attr('x2', innerWidth)
      .attr('y1', (d) => yScale(d))
      .attr('y2', (d) => yScale(d))
      .attr('stroke', '#2A2A3A')
      .attr('stroke-dasharray', '3,3');

    // Axes
    const xAxis = axisBottom(xScale)
      .ticks(6)
      .tickFormat((d) => {
        const date = d as Date;
        return `${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}`;
      });

    g.append('g')
      .attr('transform', `translate(0,${innerHeight})`)
      .call(xAxis)
      .selectAll('text')
      .attr('fill', '#8888A0')
      .attr('font-size', 10);
    g.selectAll('.domain, .tick line').attr('stroke', '#2A2A3A');

    const yAxis = axisLeft(yScale).ticks(5);
    g.append('g').call(yAxis).selectAll('text').attr('fill', '#8888A0').attr('font-size', 10);
    g.selectAll('.domain').attr('stroke', '#2A2A3A');
    g.selectAll('.tick line').attr('stroke', '#2A2A3A');

    // Line generator
    const lineGen = line<Date>().curve(curveMonotoneX);

    // Per-hostname lines
    hostnames.forEach((hostname, i) => {
      const series = seriesMap.get(hostname)!;
      const color = NODE_COLORS[i % NODE_COLORS.length];

      lineGen
        .x((d) => xScale(d))
        .y((d) => yScale(series.get(d.getTime()) ?? 0));

      g.append('path')
        .datum(allTimestamps)
        .attr('fill', 'none')
        .attr('stroke', color)
        .attr('stroke-width', 1.5)
        .attr('stroke-opacity', 0.8)
        .attr('d', lineGen);
    });

    // Total line
    lineGen
      .x((d) => xScale(d))
      .y((d) => yScale(totalMap.get(d.getTime()) ?? 0));

    g.append('path')
      .datum(allTimestamps)
      .attr('fill', 'none')
      .attr('stroke', TOTAL_COLOR)
      .attr('stroke-width', 2.5)
      .attr('d', lineGen);

    // Legend
    const legend = svg
      .append('g')
      .attr('transform', `translate(${margin.left + innerWidth + 12},${margin.top + 4})`);

    const allSeries = [...hostnames.map((h, i) => ({ label: h, color: NODE_COLORS[i % NODE_COLORS.length] })),
      { label: 'Total', color: TOTAL_COLOR }];

    allSeries.forEach((s, i) => {
      const row = legend.append('g').attr('transform', `translate(0,${i * 18})`);
      row.append('line').attr('x1', 0).attr('x2', 14).attr('y1', 5).attr('y2', 5)
        .attr('stroke', s.color).attr('stroke-width', s.label === 'Total' ? 2.5 : 1.5);
      row.append('text').attr('x', 18).attr('y', 9).attr('fill', '#8888A0')
        .attr('font-size', 10).text(s.label);
    });

    // Crosshair overlay
    const crosshairLine = g.append('line')
      .attr('y1', 0).attr('y2', innerHeight)
      .attr('stroke', '#5555660')
      .attr('stroke-width', 1)
      .attr('stroke-dasharray', '4,3')
      .style('display', 'none');

    const overlay = g.append('rect')
      .attr('width', innerWidth)
      .attr('height', innerHeight)
      .attr('fill', 'none')
      .attr('pointer-events', 'all');

    overlay.on('mousemove', function (event: MouseEvent) {
      crosshairLine.style('display', null);
      const mouseX = event.clientX - svgRef.current!.getBoundingClientRect().left - margin.left;
      crosshairLine.attr('x1', mouseX).attr('x2', mouseX);
      handleMouseMove(event, xScale, allTimestamps, seriesMap, hostnames, totalMap, margin);
    });

    overlay.on('mouseleave', () => {
      crosshairLine.style('display', 'none');
      setTooltip(null);
    });

    return () => {
      svg.selectAll('*').remove();
    };
  }, [data, height, containerWidth, handleMouseMove]);

  if (!data || data.length === 0) {
    return (
      <div className="bg-surface-raised border border-border-subtle rounded-lg p-4">
        <h3 className="font-medium text-text-primary mb-3">Throughput Over Time</h3>
        <div className="flex items-center justify-center h-48 text-text-tertiary text-sm">
          No throughput data available
        </div>
      </div>
    );
  }

  return (
    <div className="bg-surface-raised border border-border-subtle rounded-lg p-4">
      <h3 className="font-medium text-text-primary mb-3">Throughput Over Time</h3>
      <div ref={containerRef} className="relative w-full">
        <svg ref={svgRef} className="w-full" style={{ height: `${height}px` }} />
        {tooltip && (
          <div
            className="absolute z-10 pointer-events-none rounded-lg border border-border-subtle bg-surface-raised px-3 py-2 shadow-lg"
            style={{
              left: Math.min(tooltip.x + 12, containerWidth - 180),
              top: Math.max(tooltip.y - 10, 0),
              transform: 'translateY(-100%)',
            }}
          >
            <div className="text-xs text-text-tertiary mb-1">
              {tooltip.time.toLocaleTimeString()}
            </div>
            {tooltip.values.map((v) => (
              <div key={v.hostname} className="flex items-center gap-2 text-xs">
                <span
                  className="inline-block w-2 h-2 rounded-full"
                  style={{ backgroundColor: v.color }}
                />
                <span className="text-text-secondary">{v.hostname}</span>
                <span className="text-text-primary font-mono ml-auto">{v.completed}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
