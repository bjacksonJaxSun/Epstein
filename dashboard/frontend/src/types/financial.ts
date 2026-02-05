export interface FinancialTransaction {
  transactionId: number;
  transactionType?: string;
  amount: number;
  currency?: string;
  fromName?: string;
  toName?: string;
  transactionDate: string;
  purpose?: string;
  referenceNumber?: string;
  bankName?: string;
}

export interface SankeyData {
  nodes: SankeyNode[];
  links: SankeyLink[];
  totalVolume: number;
}

export interface SankeyNode {
  id: string;
  label: string;
  type: 'person' | 'organization';
}

export interface SankeyLink {
  source: string;
  target: string;
  value: number;
  transactionCount: number;
}
