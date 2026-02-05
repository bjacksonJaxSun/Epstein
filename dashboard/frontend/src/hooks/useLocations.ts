import { useQuery } from '@tanstack/react-query';
import { locationsApi } from '@/api/endpoints/locations';
import type { PaginatedResponse } from '@/types';
import type { Location } from '@/api/endpoints/locations';

export type { Location } from '@/api/endpoints/locations';

export function useLocations(params?: {
  page?: number;
  pageSize?: number;
  search?: string;
  locationType?: string;
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
} {
  const countries = new Set<string>();
  let geoLocated = 0;

  for (const loc of locations) {
    if (loc.gpsLatitude != null && loc.gpsLongitude != null) {
      geoLocated++;
    }
    if (loc.country) {
      countries.add(loc.country);
    }
  }

  return {
    total: locations.length,
    geoLocated,
    countries: countries.size,
  };
}
