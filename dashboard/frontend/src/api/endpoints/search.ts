import { apiGet } from '../client';
import type { SearchResult, EntitySearchResult, PaginatedResponse } from '@/types';

export const searchApi = {
  fullText: (params: { query: string; page?: number; pageSize?: number }) =>
    apiGet<PaginatedResponse<SearchResult>>('/search', {
      ...params,
      page: params?.page != null ? params.page - 1 : undefined,
    }),
  entities: (params: { query: string; types?: string }) =>
    apiGet<EntitySearchResult[]>('/search/entities', params),
};
