export interface NetworkGraph {
  nodes: NetworkNode[];
  edges: NetworkEdge[];
  centerNodeId: string;
}

export interface NetworkNode {
  id: string;
  label: string;
  type: 'person' | 'organization' | 'location' | 'event';
  properties?: Record<string, unknown>;
}

export interface NetworkEdge {
  source: string;
  target: string;
  relationshipType: string;
  confidenceLevel: string;
  weight: number;
}
