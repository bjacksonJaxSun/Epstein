import { apiGet } from '../client';
import type { MediaFile, PaginatedResponse } from '@/types';

export interface MediaPosition {
  mediaFileId: number;
  page: number;
  indexOnPage: number;
  globalIndex: number;
  totalCount: number;
  totalPages: number;
}

export interface NearestMediaResult {
  nearestId: number;
  isExactMatch: boolean;
}

export const mediaApi = {
  list: (params?: {
    page?: number;
    pageSize?: number;
    mediaType?: string;
    excludeDocumentScans?: boolean;
  }) => apiGet<PaginatedResponse<MediaFile>>('/media', {
    ...params,
    page: params?.page != null ? params.page - 1 : undefined,
  }),
  getById: (id: number) => apiGet<MediaFile>(`/media/${id}`),
  getPosition: (id: number, pageSize: number, mediaType?: string, excludeDocumentScans?: boolean) =>
    apiGet<MediaPosition>(`/media/${id}/position`, { pageSize, mediaType, excludeDocumentScans }),
  findNearest: (id: number, mediaType?: string, excludeDocumentScans?: boolean) =>
    apiGet<NearestMediaResult>(`/media/${id}/nearest`, { mediaType, excludeDocumentScans }),
};
