import { useQuery } from '@tanstack/react-query';
import { eventsApi } from '@/api/endpoints/events';

export function useRecentEvents(limit = 10) {
  return useQuery({
    queryKey: ['events', 'recent', limit],
    queryFn: () =>
      eventsApi.list({
        pageSize: limit,
        page: 1,
      }),
    staleTime: 60_000,
  });
}
