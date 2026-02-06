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
  entities: async (params: { query: string; types?: string }): Promise<EntitySearchResult[]> => {
    // Backend returns PagedResult<PersonListDto>, map to EntitySearchResult[]
    const response = await apiGet<PaginatedResponse<{
      personId: number;
      fullName: string;
      primaryRole?: string;
    }>>('/search/entities', params);
    return response.items.map((p) => ({
      id: p.personId,
      name: p.fullName,
      entityType: 'person' as const,
      subtitle: p.primaryRole,
    }));
  },
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
