import { apiGet } from '../client';
import type { PaginatedResponse } from '@/types';

export interface Communication {
  communicationId: number;
  communicationType: string;
  subject?: string;
  fromName?: string;
  toName?: string;
  ccNames?: string[];
  communicationDate?: string;
  communicationTime?: string;
  bodyText?: string;
  attachmentCount: number;
  sourceDocumentId?: number;
  sourceDocumentEfta?: string;
  confidenceLevel?: string;
}

export const communicationsApi = {
  list: (params?: {
    page?: number;
    pageSize?: number;
    communicationType?: string;
    dateFrom?: string;
    dateTo?: string;
    search?: string;
  }) => apiGet<PaginatedResponse<Communication>>('/communications', {
    ...params,
    page: params?.page != null ? params.page - 1 : undefined,
  }),
  getById: (id: number) => apiGet<Communication>(`/communications/${id}`),
};
