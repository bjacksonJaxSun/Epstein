import { apiGet } from '../client';
import type { SearchResult, EntitySearchResult, ChunkSearchResult, ChunkSearchStats, PaginatedResponse } from '@/types';

export interface FullTextSearchParams {
  query: string;
  page?: number;
  pageSize?: number;
  dateFrom?: string;
  dateTo?: string;
  documentTypes?: string;
  highlight?: boolean;
}

export interface ChunkSearchParams {
  query: string;
  page?: number;
  pageSize?: number;
  includeContext?: boolean;
  dateFrom?: string;
  dateTo?: string;
  documentTypes?: string;
}

export const searchApi = {
  fullText: (params: FullTextSearchParams) =>
    apiGet<PaginatedResponse<SearchResult>>('/search', {
      ...params,
      page: params?.page != null ? params.page - 1 : undefined,
    }),
  entities: (params: { query: string; types?: string }) =>
    apiGet<EntitySearchResult[]>('/search/entities', params),
  suggestions: (params: { query: string; limit?: number }) =>
    apiGet<string[]>('/search/suggestions', params),
  // Chunk-level search for RAG applications
  chunks: (params: ChunkSearchParams) =>
    apiGet<PaginatedResponse<ChunkSearchResult>>('/search/chunks', {
      ...params,
      page: params?.page != null ? params.page - 1 : undefined,
    }),
  documentChunks: (documentId: number) =>
    apiGet<ChunkSearchResult[]>(`/search/chunks/document/${documentId}`),
  chunkStats: () =>
    apiGet<ChunkSearchStats>('/search/chunks/stats'),
};
