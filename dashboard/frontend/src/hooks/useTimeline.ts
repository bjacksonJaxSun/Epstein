import { useQuery } from '@tanstack/react-query';
import { eventsApi } from '@/api/endpoints/events';
import type { TimelineEvent, PaginatedResponse } from '@/types';

export function useTimelineEvents(params: {
  dateFrom?: string;
  dateTo?: string;
  eventTypes?: string[];
  page?: number;
  pageSize?: number;
}) {
  return useQuery<PaginatedResponse<TimelineEvent>>({
    queryKey: ['timeline', params],
    queryFn: () =>
      eventsApi.list({
        dateFrom: params.dateFrom,
        dateTo: params.dateTo,
        eventType:
          params.eventTypes && params.eventTypes.length === 1
            ? params.eventTypes[0]
            : undefined,
        page: params.page ?? 1,
        pageSize: params.pageSize ?? 500,
      }),
  });
}
