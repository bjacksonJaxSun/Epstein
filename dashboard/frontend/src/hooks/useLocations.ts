import { useQuery } from '@tanstack/react-query';
import { locationsApi } from '@/api/endpoints/locations';
import type { PaginatedResponse } from '@/types';
import type { Location, LocationDocument, LocationPlacementSummary } from '@/api/endpoints/locations';

export type { Location, LocationDocument, LocationPlacement, LocationPlacementSummary } from '@/api/endpoints/locations';

export function useLocations(params?: {
  page?: number;
  pageSize?: number;
  search?: string;
  locationType?: string;
  country?: string;
  sortBy?: string;
  sortDirection?: string;
}) {
  return useQuery<PaginatedResponse<Location>>({
    queryKey: ['locations', params],
    queryFn: () =>
      locationsApi.list({ ...params, pageSize: params?.pageSize ?? 500 }),
  });
}

export function useLocationDetail(id: number) {
  return useQuery<Location>({
    queryKey: ['locations', id],
    queryFn: () => locationsApi.getById(id),
    enabled: id > 0,
  });
}

export function useLocationCountries() {
  return useQuery<string[]>({
    queryKey: ['locations', 'countries'],
    queryFn: () => locationsApi.getCountries(),
  });
}

export function useLocationTypesList() {
  return useQuery<string[]>({
    queryKey: ['locations', 'types'],
    queryFn: () => locationsApi.getTypes(),
  });
}

export function useLocationDocuments(id: number) {
  return useQuery<LocationDocument[]>({
    queryKey: ['locations', id, 'documents'],
    queryFn: () => locationsApi.getDocuments(id),
    enabled: id > 0,
  });
}

export function useLocationPlacements(id: number, limit?: number) {
  return useQuery<LocationPlacementSummary>({
    queryKey: ['locations', id, 'placements', limit],
    queryFn: () => locationsApi.getPlacements(id, limit),
    enabled: id > 0,
  });
}

export function useLocationTypes(locations: Location[]): string[] {
  const types = new Set<string>();
  for (const loc of locations) {
    if (loc.locationType) {
      types.add(loc.locationType);
    }
  }
  return Array.from(types).sort();
}

export function useGeoLocatedCount(locations: Location[]): {
  total: number;
  geoLocated: number;
  countries: number;
  totalEvents: number;
  totalMedia: number;
  totalPlacements: number;
} {
  const countries = new Set<string>();
  let geoLocated = 0;
  let totalEvents = 0;
  let totalMedia = 0;
  let totalPlacements = 0;

  for (const loc of locations) {
    if (loc.gpsLatitude != null && loc.gpsLongitude != null) {
      geoLocated++;
    }
    if (loc.country) {
      countries.add(loc.country);
    }
    totalEvents += loc.eventCount ?? 0;
    totalMedia += loc.mediaCount ?? 0;
    totalPlacements += loc.placementCount ?? 0;
  }

  return {
    total: locations.length,
    geoLocated,
    countries: countries.size,
    totalEvents,
    totalMedia,
    totalPlacements,
  };
}
