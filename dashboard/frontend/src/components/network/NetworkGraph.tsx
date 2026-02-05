import { useEffect, useRef, useCallback } from 'react';
import cytoscape, { type Core, type ElementDefinition } from 'cytoscape';
import type { NetworkGraph as NetworkGraphData } from '@/types';
import { useSelectionStore } from '@/stores/useSelectionStore';
import { LoadingSpinner } from '@/components/shared';

interface NetworkGraphProps {
  data: NetworkGraphData | undefined;
  isLoading: boolean;
  layoutName: string;
  onDoubleClickNode: (nodeId: string, nodeType: string, label: string) => void;
}

const NODE_COLORS: Record<string, string> = {
  person: '#4A9EFF',
  organization: '#A855F7',
  location: '#22C55E',
  event: '#FFB020',
};

const NODE_SHAPES: Record<string, string> = {
  person: 'ellipse',
  organization: 'diamond',
  location: 'rectangle',
  event: 'triangle',
};

const EDGE_COLORS: Record<string, string> = {
  associate: '#4A9EFF',
  employer: '#A855F7',
  family: '#22C55E',
  legal: '#FF4757',
  financial: '#00D4AA',
  travel: '#FFB020',
  social: '#EC4899',
  default: '#6B6B80',
};

function getEdgeColor(relationshipType: string): string {
  const normalized = relationshipType.toLowerCase();
  for (const [key, color] of Object.entries(EDGE_COLORS)) {
    if (normalized.includes(key)) return color;
  }
  return EDGE_COLORS.default;
}

function getConfidenceOpacity(level: string): number {
  switch (level.toLowerCase()) {
    case 'high':
      return 1.0;
    case 'medium':
      return 0.6;
    case 'low':
      return 0.3;
    default:
      return 0.5;
  }
}

function getConfidenceLineStyle(level: string): string {
  return level.toLowerCase() === 'low' ? 'dashed' : 'solid';
}

function transformToElements(graph: NetworkGraphData): ElementDefinition[] {
  const connectionCounts = new Map<string, number>();
  for (const edge of graph.edges) {
    connectionCounts.set(edge.source, (connectionCounts.get(edge.source) ?? 0) + 1);
    connectionCounts.set(edge.target, (connectionCounts.get(edge.target) ?? 0) + 1);
  }

  const nodes: ElementDefinition[] = graph.nodes.map((n) => {
    // Handle both 'type' and 'nodeType' from API, normalize to lowercase
    const nodeType = ((n as any).nodeType ?? n.type ?? 'person').toLowerCase();
    return {
      data: {
        id: n.id,
        label: n.label,
        type: nodeType,
        size: Math.max(30, Math.min(80, 30 + (connectionCounts.get(n.id) ?? 0) * 5)),
        color: NODE_COLORS[nodeType] ?? '#6B6B80',
      },
    };
  });

  const edges: ElementDefinition[] = graph.edges.map((e, i) => ({
    data: {
      id: `edge-${e.source}-${e.target}-${i}`,
      source: e.source,
      target: e.target,
      label: e.relationshipType,
      confidence: e.confidenceLevel,
      weight: e.weight,
      edgeColor: getEdgeColor(e.relationshipType),
      edgeOpacity: getConfidenceOpacity(e.confidenceLevel),
      lineStyle: getConfidenceLineStyle(e.confidenceLevel),
    },
  }));

  return [...nodes, ...edges];
}

function buildStylesheet(): cytoscape.StylesheetStyle[] {
  return [
    {
      selector: 'node',
      style: {
        label: 'data(label)',
        color: '#E8E8F0',
        'text-valign': 'bottom',
        'text-margin-y': 8,
        'font-size': 11,
        'font-family': 'Inter, system-ui, sans-serif',
        width: 'data(size)',
        height: 'data(size)',
        'background-color': 'data(color)',
        'border-width': 0,
        'text-outline-color': '#12121A',
        'text-outline-width': 2,
        'overlay-padding': 6,
      },
    },
    {
      selector: 'node[type="person"]',
      style: {
        shape: 'ellipse' as cytoscape.Css.NodeShape,
      },
    },
    {
      selector: 'node[type="organization"]',
      style: {
        shape: 'diamond' as cytoscape.Css.NodeShape,
      },
    },
    {
      selector: 'node[type="location"]',
      style: {
        shape: 'rectangle' as cytoscape.Css.NodeShape,
      },
    },
    {
      selector: 'node[type="event"]',
      style: {
        shape: 'triangle' as cytoscape.Css.NodeShape,
      },
    },
    {
      selector: 'node:selected',
      style: {
        'border-width': 3,
        'border-color': '#FFFFFF',
        width: 'mapData(size, 30, 80, 40, 90)',
        height: 'mapData(size, 30, 80, 40, 90)',
      },
    },
    {
      selector: 'node.highlighted',
      style: {
        'border-width': 2,
        'border-color': '#4A9EFF',
      },
    },
    {
      selector: 'node.dimmed',
      style: {
        opacity: 0.2,
      },
    },
    {
      selector: 'edge',
      style: {
        width: 'mapData(weight, 0, 10, 1, 5)' as unknown as number,
        'line-color': 'data(edgeColor)',
        'target-arrow-color': 'data(edgeColor)',
        'target-arrow-shape': 'triangle',
        'arrow-scale': 0.8,
        'curve-style': 'bezier',
        opacity: 'data(edgeOpacity)' as unknown as number,
        'line-style': 'solid' as const,
        'font-size': 9,
        color: '#A0A0B8',
        'text-outline-color': '#12121A',
        'text-outline-width': 1.5,
      },
    },
    {
      selector: 'edge[lineStyle="dashed"]',
      style: {
        'line-style': 'dashed' as const,
        'line-dash-pattern': [6, 3],
      },
    },
    {
      selector: 'edge.highlighted',
      style: {
        label: 'data(label)',
        'font-size': 10,
        opacity: 1,
        width: 'mapData(weight, 0, 10, 2, 6)' as unknown as number,
      },
    },
    {
      selector: 'edge.dimmed',
      style: {
        opacity: 0.08,
      },
    },
  ];
}

function getLayoutConfig(name: string): cytoscape.LayoutOptions {
  switch (name) {
    case 'cose':
      return {
        name: 'cose',
        animate: true,
        animationDuration: 800,
        nodeRepulsion: () => 8000,
        idealEdgeLength: () => 120,
        gravity: 0.3,
        padding: 50,
      } as cytoscape.LayoutOptions;
    case 'circle':
      return {
        name: 'circle',
        animate: true,
        animationDuration: 600,
        padding: 50,
      };
    case 'grid':
      return {
        name: 'grid',
        animate: true,
        animationDuration: 600,
        padding: 50,
      };
    case 'breadthfirst':
      return {
        name: 'breadthfirst',
        animate: true,
        animationDuration: 600,
        directed: true,
        padding: 50,
        spacingFactor: 1.5,
      } as cytoscape.LayoutOptions;
    default:
      return {
        name: 'cose',
        animate: true,
        animationDuration: 800,
        padding: 50,
      } as cytoscape.LayoutOptions;
  }
}

export function NetworkGraph({
  data,
  isLoading,
  layoutName,
  onDoubleClickNode,
}: NetworkGraphProps) {
  const cyRef = useRef<Core | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const selectEntity = useSelectionStore((s) => s.selectEntity);

  const initCytoscape = useCallback(() => {
    if (!containerRef.current) return;

    if (cyRef.current) {
      cyRef.current.destroy();
    }

    cyRef.current = cytoscape({
      container: containerRef.current,
      style: buildStylesheet(),
      layout: { name: 'preset' },
      minZoom: 0.2,
      maxZoom: 5,
      wheelSensitivity: 0.3,
    });

    const cy = cyRef.current;

    cy.on('tap', 'node', (evt) => {
      const node = evt.target;
      const nodeId = node.data('id') as string;
      const nodeType = node.data('type') as string;
      // Extract numeric ID from format like "person-3" or "organization-42"
      const numericId = nodeId.includes('-') ? nodeId.split('-')[1] : nodeId;
      selectEntity(numericId, nodeType);
    });

    cy.on('dbltap', 'node', (evt) => {
      const node = evt.target;
      const nodeId = node.data('id') as string;
      const nodeType = node.data('type') as string;
      const nodeLabel = node.data('label') as string;
      // Extract numeric ID from format like "person-3"
      const numericId = nodeId.includes('-') ? nodeId.split('-')[1] : nodeId;
      onDoubleClickNode(numericId, nodeType, nodeLabel);
    });

    cy.on('mouseover', 'node', (evt) => {
      const node = evt.target;
      const connectedEdges = node.connectedEdges();
      const connectedNodes = connectedEdges.connectedNodes();

      cy.elements().addClass('dimmed');
      node.removeClass('dimmed').addClass('highlighted');
      connectedEdges.removeClass('dimmed').addClass('highlighted');
      connectedNodes.removeClass('dimmed').addClass('highlighted');

      containerRef.current!.style.cursor = 'pointer';
    });

    cy.on('mouseout', 'node', () => {
      cy.elements().removeClass('dimmed').removeClass('highlighted');
      containerRef.current!.style.cursor = 'default';
    });

    cy.on('tap', (evt) => {
      if (evt.target === cy) {
        cy.elements().removeClass('dimmed').removeClass('highlighted');
      }
    });
  }, [selectEntity, onDoubleClickNode]);

  useEffect(() => {
    initCytoscape();
    return () => {
      cyRef.current?.destroy();
      cyRef.current = null;
    };
  }, [initCytoscape]);

  useEffect(() => {
    if (!cyRef.current || !data) return;

    const cy = cyRef.current;
    cy.elements().remove();

    const elements = transformToElements(data);
    cy.add(elements);

    const layout = cy.layout(getLayoutConfig(layoutName));
    layout.run();
  }, [data, layoutName]);

  const fitToViewport = useCallback(() => {
    cyRef.current?.fit(undefined, 50);
  }, []);

  const resetGraph = useCallback(() => {
    if (!cyRef.current || !data) return;
    cyRef.current.elements().remove();
    const elements = transformToElements(data);
    cyRef.current.add(elements);
    cyRef.current.layout(getLayoutConfig(layoutName)).run();
    cyRef.current.fit(undefined, 50);
  }, [data, layoutName]);

  useEffect(() => {
    const handleFit = () => fitToViewport();
    const handleReset = () => resetGraph();

    window.addEventListener('network-fit', handleFit);
    window.addEventListener('network-reset', handleReset);

    return () => {
      window.removeEventListener('network-fit', handleFit);
      window.removeEventListener('network-reset', handleReset);
    };
  }, [fitToViewport, resetGraph]);

  return (
    <div className="relative flex-1 rounded-lg border border-border-subtle bg-surface-sunken overflow-hidden">
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
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M7.5 14.25v2.25m3-4.5v4.5m3-6.75v6.75m3-9v9M6 20.25h12A2.25 2.25 0 0020.25 18V6A2.25 2.25 0 0018 3.75H6A2.25 2.25 0 003.75 6v12A2.25 2.25 0 006 20.25z"
            />
          </svg>
          <p className="text-sm text-text-disabled">
            Search for a person to explore their network
          </p>
        </div>
      )}
      <div
        ref={containerRef}
        className="h-full w-full"
        style={{ minHeight: '500px' }}
      />
    </div>
  );
}

export { NODE_COLORS, NODE_SHAPES };
