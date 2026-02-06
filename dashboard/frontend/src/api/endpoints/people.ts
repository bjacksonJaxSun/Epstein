import { apiGet, apiPost } from '../client';
import type {
  Person,
  PersonDetail,
  PaginatedResponse,
  Relationship,
  NetworkGraph,
  EntityFrequency,
  DuplicateGroup,
} from '@/types';

// Helper to safely parse JSON strings from the backend
function parseJsonStringField(value: unknown): string[] {
  if (Array.isArray(value)) return value;
  if (typeof value === 'string' && value.trim()) {
    try {
      const parsed = JSON.parse(value);
      return Array.isArray(parsed) ? parsed : [];
    } catch {
      return [];
    }
  }
  return [];
}

// Transform backend response to proper typed arrays
function transformPersonDetail(data: Record<string, unknown>): PersonDetail {
  return {
    ...data,
    nameVariations: parseJsonStringField(data.nameVariations),
    roles: parseJsonStringField(data.roles),
    emailAddresses: parseJsonStringField(data.emailAddresses),
    phoneNumbers: parseJsonStringField(data.phoneNumbers),
    addresses: parseJsonStringField(data.addresses),
    isRedacted: data.isRedacted ?? false,
  } as PersonDetail;
}

export const peopleApi = {
  list: (params?: { page?: number; pageSize?: number; search?: string; sortBy?: string; sortDirection?: string }) =>
    apiGet<PaginatedResponse<Person>>('/people', {
      ...params,
      page: params?.page != null ? params.page - 1 : undefined,
    }),
  getById: async (id: number) => {
    const data = await apiGet<Record<string, unknown>>(`/people/${id}`);
    return transformPersonDetail(data);
  },
  getRelationships: (id: number) =>
    apiGet<Relationship[]>(`/people/${id}/relationships`),
  getNetwork: (id: number, depth = 2) =>
    apiGet<NetworkGraph>(`/people/${id}/network`, { depth }),
  getFrequencies: (limit = 500) =>
    apiGet<EntityFrequency[]>('/people/frequencies', { limit }),
  getDuplicates: () =>
    apiGet<DuplicateGroup[]>('/people/duplicates'),
  mergePersons: (primaryPersonId: number, mergePersonIds: number[]) =>
    apiPost<{ message: string }>('/people/merge', { primaryPersonId, mergePersonIds }),
};
