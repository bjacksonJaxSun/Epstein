import { apiGet } from '../client';
import type { TimelineEvent, PaginatedResponse } from '@/types';

export const eventsApi = {
  list: (params?: {
    page?: number;
    pageSize?: number;
    dateFrom?: string;
    dateTo?: string;
    eventType?: string;
  }) => apiGet<PaginatedResponse<TimelineEvent>>('/events', {
    ...params,
    page: params?.page != null ? params.page - 1 : undefined,
  }),
  getById: (id: number) => apiGet<TimelineEvent>(`/events/${id}`),
};
