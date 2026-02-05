import { useQuery } from '@tanstack/react-query';
import { peopleApi } from '@/api/endpoints/people';
import { apiGet } from '@/api/client';
import type {
  Person,
  PaginatedResponse,
  TimelineEvent,
  Document,
  FinancialTransaction,
  MediaFile,
} from '@/types';

export function usePeopleList(params: {
  page?: number;
  pageSize?: number;
  search?: string;
}) {
  return useQuery({
    queryKey: ['people', 'list', params],
    queryFn: () => peopleApi.list(params),
  });
}

export function useTopPeople(limit = 10) {
  return useQuery({
    queryKey: ['people', 'top', limit],
    queryFn: () =>
      apiGet<PaginatedResponse<Person>>('/people', {
        pageSize: limit,
        sortBy: 'relationshipCount',
        sortDirection: 'desc',
      }),
  });
}

export function usePersonDetail(id: number) {
  return useQuery({
    queryKey: ['people', id],
    queryFn: () => peopleApi.getById(id),
    enabled: id > 0,
  });
}

export function usePersonRelationships(id: number) {
  return useQuery({
    queryKey: ['people', id, 'relationships'],
    queryFn: () => peopleApi.getRelationships(id),
    enabled: id > 0,
  });
}

export function usePersonEvents(id: number) {
  return useQuery({
    queryKey: ['people', id, 'events'],
    queryFn: () => apiGet<TimelineEvent[]>(`/people/${id}/events`),
    enabled: id > 0,
  });
}

export function usePersonDocuments(id: number) {
  return useQuery({
    queryKey: ['people', id, 'documents'],
    queryFn: () => apiGet<Document[]>(`/people/${id}/documents`),
    enabled: id > 0,
  });
}

export function usePersonFinancials(id: number) {
  return useQuery({
    queryKey: ['people', id, 'financials'],
    queryFn: () => apiGet<FinancialTransaction[]>(`/people/${id}/financials`),
    enabled: id > 0,
  });
}

export function usePersonMedia(id: number) {
  return useQuery({
    queryKey: ['people', id, 'media'],
    queryFn: () => apiGet<MediaFile[]>(`/people/${id}/media`),
    enabled: id > 0,
  });
}
