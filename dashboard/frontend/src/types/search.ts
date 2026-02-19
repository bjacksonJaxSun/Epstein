export interface SearchResult {
  documentId: number;
  eftaNumber: string;
  title?: string;
  snippet?: string;
  relevanceScore: number;
  documentDate?: string;
  documentType?: string;
  pageCount?: number;
  isRedacted?: boolean;
}

export interface EntitySearchResult {
  id: number;
  name: string;
  entityType: 'person' | 'organization' | 'location' | 'event' | 'document';
  subtitle?: string;
}

export interface ChunkSearchResult {
  chunkId: string;
  documentId: number;
  eftaNumber?: string;
  chunkIndex: number;
  chunkText?: string;
  snippet?: string;
  pageNumber?: number;
  hasRedaction: boolean;
  precedingContext?: string;
  followingContext?: string;
  relevanceScore: number;
  // Parent document info
  documentTitle?: string;
  documentDate?: string;
  documentType?: string;
  filePath?: string;
}

export interface ChunkSearchStats {
  totalDocuments: number;
  documentsWithChunks: number;
  totalChunks: number;
  chunksWithEmbeddings: number;
  averageChunksPerDocument: number;
  ftsAvailable: boolean;
  vectorSearchAvailable: boolean;
}
