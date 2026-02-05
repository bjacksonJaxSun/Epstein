import { useQuery } from '@tanstack/react-query';
import { peopleApi } from '@/api/endpoints/people';
import { searchApi } from '@/api/endpoints/search';
import type { NetworkGraph, EntitySearchResult } from '@/types';

export function useNetworkGraph(personId: number | null, depth: number) {
  return useQuery<NetworkGraph>({
    queryKey: ['network', personId, depth],
    queryFn: () => peopleApi.getNetwork(personId!, depth),
    enabled: personId !== null && personId > 0,
  });
}

export function useEntitySearch(query: string) {
  return useQuery<EntitySearchResult[]>({
    queryKey: ['entity-search', query],
    queryFn: () => searchApi.entities({ query, types: 'person' }),
    enabled: query.length >= 2,
    staleTime: 30_000,
  });
}
