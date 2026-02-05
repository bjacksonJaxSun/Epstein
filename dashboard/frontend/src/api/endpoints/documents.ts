import { apiGet } from '../client';
import type { Document, PaginatedResponse } from '@/types';

export const documentsApi = {
  list: (params?: {
    page?: number;
    pageSize?: number;
    search?: string;
    documentType?: string;
  }) => apiGet<PaginatedResponse<Document>>('/documents', {
    ...params,
    page: params?.page != null ? params.page - 1 : undefined,
  }),
  getById: (id: number) => apiGet<Document>(`/documents/${id}`),
};
