import { apiGet } from '../client';
import type { PaginatedResponse } from '@/types';

export interface Location {
  locationId: number;
  locationName: string;
  locationType?: string;
  address?: string;
  city?: string;
  stateProvince?: string;
  country?: string;
  gpsLatitude?: number;
  gpsLongitude?: number;
  owner?: string;
  description?: string;
}

export const locationsApi = {
  list: (params?: {
    page?: number;
    pageSize?: number;
    search?: string;
    locationType?: string;
  }) => apiGet<PaginatedResponse<Location>>('/locations', {
    ...params,
    page: params?.page != null ? params.page - 1 : undefined,
  }),
  getById: (id: number) => apiGet<Location>(`/locations/${id}`),
};
