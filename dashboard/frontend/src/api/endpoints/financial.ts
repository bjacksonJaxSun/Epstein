import { apiGet } from '../client';
import type {
  FinancialTransaction,
  PaginatedResponse,
  SankeyData,
} from '@/types';

export const financialApi = {
  list: (params?: {
    page?: number;
    pageSize?: number;
    fromName?: string;
    toName?: string;
  }) =>
    apiGet<PaginatedResponse<FinancialTransaction>>('/financial/transactions', {
      ...params,
      page: params?.page != null ? params.page - 1 : undefined,
    }),
  getSankeyData: (params?: { minAmount?: number }) =>
    apiGet<SankeyData>('/financial/sankey', params),
};
