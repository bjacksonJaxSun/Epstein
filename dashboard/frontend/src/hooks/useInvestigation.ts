import { useQuery } from '@tanstack/react-query';
import { investigationApi } from '@/api/endpoints/investigation';
import type {
  GeoTimelineEntry,
  PersonConnections,
  SharedPresence,
  ConnectedFinancial,
  PersonSearchResult,
} from '@/api/endpoints/investigation';

export type {
  GeoTimelineEntry,
  PersonConnections,
  SharedPresence,
  ConnectedFinancial,
  ConnectedLocation,
  ConnectedEvent,
  ConnectedPerson,
  CoPresence,
  PersonSearchResult,
} from '@/api/endpoints/investigation';

export function usePersonSearch(q: string, limit = 20) {
  return useQuery<PersonSearchResult[]>({
    queryKey: ['investigation', 'people', 'search', q],
    queryFn: () => investigationApi.searchPeople(q, limit),
    enabled: q.trim().length >= 2,
    staleTime: 60_000,
  });
}

export function useGeoTimeline(params?: {
  dateFrom?: string;
  dateTo?: string;
  personName?: string;
  locationId?: number;
  limit?: number;
}) {
  return useQuery<GeoTimelineEntry[]>({
    queryKey: ['investigation', 'geo-timeline', params],
    queryFn: () => investigationApi.getGeoTimeline(params),
    staleTime: 30_000,
  });
}

export function usePersonConnections(
  personId: number | null,
  params?: { dateFrom?: string; dateTo?: string }
) {
  return useQuery<PersonConnections>({
    queryKey: ['investigation', 'person', personId, 'connections', params],
    queryFn: () => investigationApi.getPersonConnections(personId!, params),
    enabled: personId != null && personId > 0,
    staleTime: 30_000,
  });
}

export function useSharedPresence(
  personIds: number[],
  params?: { dateFrom?: string; dateTo?: string }
) {
  return useQuery<SharedPresence[]>({
    queryKey: ['investigation', 'shared-presence', personIds, params],
    queryFn: () => investigationApi.getSharedPresence(personIds, params),
    enabled: personIds.length >= 2,
    staleTime: 30_000,
  });
}

export function useFinancialNetwork(
  personIds: number[],
  params?: { dateFrom?: string; dateTo?: string }
) {
  return useQuery<ConnectedFinancial[]>({
    queryKey: ['investigation', 'financial-network', personIds, params],
    queryFn: () => investigationApi.getFinancialNetwork(personIds, params),
    enabled: personIds.length >= 1,
    staleTime: 30_000,
  });
}
