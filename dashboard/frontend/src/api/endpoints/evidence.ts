import { apiGet } from '../client';
import type { PaginatedResponse } from '@/types';

export interface EvidenceItem {
  evidenceId: number;
  evidenceNumber?: string;
  evidenceType?: string;
  description?: string;
  seizedFrom?: string;
  seizureDate?: string;
  status?: string;
  currentLocation?: string;
  chainOfCustody?: CustodyRecord[];
  sourceDocumentId?: number;
  sourceDocumentEfta?: string;
}

export interface CustodyRecord {
  date: string;
  action: string;
  handler: string;
  notes?: string;
}

export const evidenceApi = {
  list: (params?: {
    page?: number;
    pageSize?: number;
    evidenceType?: string;
    status?: string;
    search?: string;
  }) => apiGet<PaginatedResponse<EvidenceItem>>('/evidence', {
    ...params,
    page: params?.page != null ? params.page - 1 : undefined,
  }),
  getById: (id: number) => apiGet<EvidenceItem>(`/evidence/${id}`),
};
