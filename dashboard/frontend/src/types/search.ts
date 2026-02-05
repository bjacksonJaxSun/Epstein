export interface SearchResult {
  documentId: number;
  eftaNumber: string;
  documentTitle?: string;
  snippet?: string;
  relevanceScore: number;
  documentDate?: string;
  documentType?: string;
}

export interface EntitySearchResult {
  id: number;
  name: string;
  entityType: 'person' | 'organization' | 'location' | 'event' | 'document';
  subtitle?: string;
}
