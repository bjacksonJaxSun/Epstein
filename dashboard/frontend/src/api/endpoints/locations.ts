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
  placementCount?: number;
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

export interface LocationPlacement {
  placementId: number;
  personId?: number;
  personName: string;
  placementDate?: string;
  dateEnd?: string;
  datePrecision?: string;
  activityType?: string;
  description?: string;
  sourceDocumentIds: number[];
  sourceEftaNumbers: string[];
  evidenceExcerpts: string[];
  confidence?: number;
  extractionMethod?: string;
}

export interface LocationPlacementSummary {
  locationId: number;
  locationName: string;
  totalPlacements: number;
  uniquePeopleCount: number;
  documentCount: number;
  earliestDate?: string;
  latestDate?: string;
  placements: LocationPlacement[];
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
  getPlacements: (id: number, limit?: number) =>
    apiGet<LocationPlacementSummary>(`/locations/${id}/placements`, { limit }),
};
