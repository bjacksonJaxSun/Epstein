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
  eventCount?: number;
  mediaCount?: number;
  evidenceCount?: number;
  totalActivity?: number;
}

export interface LocationDocument {
  documentId: number;
  eftaNumber?: string;
  documentType?: string;
  documentDate?: string;
  documentTitle?: string;
  author?: string;
  subject?: string;
  pageCount?: number;
}

export const locationsApi = {
  list: (params?: {
    page?: number;
    pageSize?: number;
    search?: string;
    locationType?: string;
    country?: string;
    sortBy?: string;
    sortDirection?: string;
  }) => apiGet<PaginatedResponse<Location>>('/locations', {
    ...params,
    page: params?.page != null ? params.page - 1 : undefined,
  }),
  getById: (id: number) => apiGet<Location>(`/locations/${id}`),
  getCountries: () => apiGet<string[]>('/locations/countries'),
  getTypes: () => apiGet<string[]>('/locations/types'),
  getDocuments: (id: number) => apiGet<LocationDocument[]>(`/locations/${id}/documents`),
};
