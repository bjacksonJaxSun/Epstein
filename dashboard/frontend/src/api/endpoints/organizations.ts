import { apiGet } from '../client';
import type { PaginatedResponse } from '@/types';

export interface Organization {
  organizationId: number;
  organizationName: string;
  organizationType?: string;
  headquartersLocation?: string;
  parentOrganization?: string;
  website?: string;
  description?: string;
}

export const organizationsApi = {
  list: (params?: { page?: number; pageSize?: number; search?: string }) =>
    apiGet<PaginatedResponse<Organization>>('/organizations', {
      ...params,
      page: params?.page != null ? params.page - 1 : undefined,
    }),
  getById: (id: number) => apiGet<Organization>(`/organizations/${id}`),
};
