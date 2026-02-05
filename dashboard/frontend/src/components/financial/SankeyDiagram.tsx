import { useEffect, useRef, useState, useCallback } from 'react';
import {
  sankey as d3Sankey,
  sankeyLinkHorizontal,
  type SankeyNode as D3SankeyNode,
  type SankeyLink as D3SankeyLink,
} from 'd3-sankey';
import { select } from 'd3-selection';
import type { SankeyData } from '@/types';

/**
 * Extra user-defined properties on nodes, beyond what d3-sankey requires.
 */
interface NodeExtra {
  id: string;
  label: string;
  type: 'person' | 'organization';
}

/**
 * Extra user-defined properties on links, beyond what d3-sankey requires.
 * (Note: `value` is already on the d3-sankey minimal link interface.)
 */
interface LinkExtra {
  transactionCount: number;
}

/** After d3-sankey layout: node with computed positions. */
type LayoutNode = D3SankeyNode<NodeExtra, LinkExtra>;
/** After d3-sankey layout: link with source/target resolved to node objects. */
type LayoutLink = D3SankeyLink<NodeExtra, LinkExtra>;

interface TooltipData {
  x: number;
  y: number;
  sourceLabel: string;
  targetLabel: string;
  value: number;
  transactionCount: number;
}

interface SankeyDiagramProps {
  data: SankeyData;
  height?: number;
}

function getNodeType(node: LayoutNode): 'person' | 'organization' {
  return (node as NodeExtra).type ?? 'person';
}

function getNodeLabel(node: LayoutNode): string {
  return (node as NodeExtra).label ?? '';
}

function nodeColor(node: LayoutNode): string {
  return getNodeType(node) === 'person' ? '#4A9EFF' : '#A855F7';
}

function sourceNodeColor(link: LayoutLink): string {
  const source = link.source;
  if (typeof source === 'object' && source !== null) {
    return nodeColor(source as LayoutNode);
  }
  return '#4A9EFF';
}

function formatCurrencyShort(amount: number): string {
  if (amount >= 1_000_000) return `$${(amount / 1_000_000).toFixed(1)}M`;
  if (amount >= 1_000) return `$${(amount / 1_000).toFixed(1)}K`;
  return `$${amount.toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

function resolveLabel(
  nodeOrId: string | number | LayoutNode
): string {
  if (typeof nodeOrId === 'string') return nodeOrId;
  if (typeof nodeOrId === 'number') return String(nodeOrId);
  return getNodeLabel(nodeOrId);
}

export function SankeyDiagram({ data, height = 500 }: SankeyDiagramProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [tooltip, setTooltip] = useState<TooltipData | null>(null);
  const [containerWidth, setContainerWidth] = useState(0);

  // Track container width with ResizeObserver
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

    return () => {
      observer.disconnect();
    };
  }, []);

  const handleLinkMouseEnter = useCallback(
    (event: MouseEvent, d: LayoutLink) => {
      const svgEl = svgRef.current;
      if (!svgEl) return;
      const rect = svgEl.getBoundingClientRect();
      setTooltip({
        x: event.clientX - rect.left,
        y: event.clientY - rect.top,
        sourceLabel: resolveLabel(d.source),
        targetLabel: resolveLabel(d.target),
        value: d.value,
        transactionCount: (d as LinkExtra).transactionCount ?? 0,
      });
    },
    []
  );

  const handleLinkMouseLeave = useCallback(() => {
    setTooltip(null);
  }, []);

  // Render the Sankey diagram with d3
  useEffect(() => {
    if (!svgRef.current || !data.nodes.length || containerWidth === 0) return;

    const svg = select(svgRef.current);
    svg.selectAll('*').remove();

    const width = containerWidth;
    const margin = { top: 10, right: 10, bottom: 10, left: 10 };
    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;

    const g = svg
      .attr('width', width)
      .attr('height', height)
      .append('g')
      .attr('transform', `translate(${margin.left},${margin.top})`);

    const sankeyGenerator = d3Sankey<NodeExtra, LinkExtra>()
      .nodeId((d) => (d as NodeExtra).id)
      .nodeWidth(20)
      .nodePadding(12)
      .extent([
        [0, 0],
        [innerWidth, innerHeight],
      ]);

    const graph = sankeyGenerator({
      nodes: data.nodes.map((d) => ({ ...d })) as Array<D3SankeyNode<NodeExtra, LinkExtra>>,
      links: data.links.map((d) => ({ ...d })) as Array<D3SankeyLink<NodeExtra, LinkExtra>>,
    });

    // Draw links
    const linkPaths = g
      .append('g')
      .attr('fill', 'none')
      .selectAll('path')
      .data(graph.links)
      .join('path')
      .attr('d', sankeyLinkHorizontal<NodeExtra, LinkExtra>())
      .attr('stroke', (d) => sourceNodeColor(d))
      .attr('stroke-opacity', 0.3)
      .attr('stroke-width', (d) => Math.max(1, d.width ?? 0))
      .style('cursor', 'pointer');

    // Link hover events
    linkPaths.on('mouseenter', function (event: MouseEvent) {
      const d = select(this).datum() as LayoutLink;
      select(this).attr('stroke-opacity', 0.6);
      handleLinkMouseEnter(event, d);
    });

    linkPaths.on('mousemove', function (event: MouseEvent) {
      const d = select(this).datum() as LayoutLink;
      handleLinkMouseEnter(event, d);
    });

    linkPaths.on('mouseleave', function () {
      select(this).attr('stroke-opacity', 0.3);
      handleLinkMouseLeave();
    });

    // Draw nodes
    g.append('g')
      .selectAll('rect')
      .data(graph.nodes)
      .join('rect')
      .attr('x', (d) => d.x0 ?? 0)
      .attr('y', (d) => d.y0 ?? 0)
      .attr('width', (d) => (d.x1 ?? 0) - (d.x0 ?? 0))
      .attr('height', (d) => Math.max(1, (d.y1 ?? 0) - (d.y0 ?? 0)))
      .attr('fill', (d) => nodeColor(d))
      .attr('rx', 2)
      .attr('opacity', 0.9);

    // Draw labels
    g.append('g')
      .selectAll('text')
      .data(graph.nodes)
      .join('text')
      .attr('x', (d) =>
        (d.x0 ?? 0) < innerWidth / 2 ? (d.x1 ?? 0) + 8 : (d.x0 ?? 0) - 8
      )
      .attr('y', (d) => ((d.y0 ?? 0) + (d.y1 ?? 0)) / 2)
      .attr('dy', '0.35em')
      .attr('text-anchor', (d) =>
        (d.x0 ?? 0) < innerWidth / 2 ? 'start' : 'end'
      )
      .attr('fill', '#E8E8F0')
      .attr('font-size', 11)
      .attr('font-family', "'Inter', system-ui, sans-serif")
      .text((d) => getNodeLabel(d));

    return () => {
      svg.selectAll('*').remove();
    };
  }, [data, height, containerWidth, handleLinkMouseEnter, handleLinkMouseLeave]);

  return (
    <div ref={containerRef} className="relative w-full">
      <svg
        ref={svgRef}
        className="w-full"
        style={{ height: `${height}px` }}
      />
      {tooltip && (
        <div
          className="absolute z-10 pointer-events-none rounded-lg border border-border-subtle bg-surface-raised px-3 py-2 shadow-lg"
          style={{
            left: tooltip.x + 12,
            top: tooltip.y - 10,
            transform: 'translateY(-100%)',
          }}
        >
          <div className="flex items-center gap-2 text-xs text-text-primary font-medium">
            <span>{tooltip.sourceLabel}</span>
            <span className="text-text-disabled">&rarr;</span>
            <span>{tooltip.targetLabel}</span>
          </div>
          <div className="mt-1 text-xs text-text-secondary">
            <span className="text-accent-green font-mono">
              {formatCurrencyShort(tooltip.value)}
            </span>
            <span className="mx-1 text-text-disabled">&middot;</span>
            <span>
              {tooltip.transactionCount}{' '}
              {tooltip.transactionCount === 1 ? 'transaction' : 'transactions'}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
