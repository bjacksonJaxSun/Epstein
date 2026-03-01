import { apiGet } from '../client';

export interface GeoTimelineEntry {
  placementId: number;
  locationId: number;
  locationName: string;
  latitude?: number;
  longitude?: number;
  city?: string;
  country?: string;
  locationType?: string;
  personName: string;
  personId?: number;
  placementDate?: string;
  dateEnd?: string;
  activityType?: string;
  description?: string;
  confidence?: number;
}

export interface ConnectedLocation {
  locationId: number;
  locationName: string;
  city?: string;
  country?: string;
  latitude?: number;
  longitude?: number;
  visitCount: number;
  firstVisit?: string;
  lastVisit?: string;
  mostRecentActivityType?: string;
}

export interface ConnectedEvent {
  eventId: number;
  eventType?: string;
  title?: string;
  eventDate?: string;
  locationName?: string;
  locationId?: number;
  participationRole?: string;
}

export interface ConnectedFinancial {
  transactionId: number;
  direction: string; // 'sent' | 'received'
  amount?: number;
  currency?: string;
  counterpartyName?: string;
  transactionDate?: string;
  purpose?: string;
}

export interface ConnectedPerson {
  personId: number;
  personName: string;
  relationshipType?: string;
  primaryRole?: string;
  source?: string;
  sharedCount: number;
}

export interface CoPresence {
  otherPersonName: string;
  otherPersonId?: number;
  locationId: number;
  locationName: string;
  subjectDate?: string;
  otherDate?: string;
  activityType?: string;
  overlapDays: number;
}

export interface PersonConnections {
  personId: number;
  personName: string;
  primaryRole?: string;
  epsteinRelationship?: string;
  locations: ConnectedLocation[];
  events: ConnectedEvent[];
  financialTransactions: ConnectedFinancial[];
  relatedPeople: ConnectedPerson[];
  coPresences: CoPresence[];
}

export interface SharedPresence {
  locationId: number;
  locationName: string;
  city?: string;
  country?: string;
  latitude?: number;
  longitude?: number;
  personCount: number;
  personNames: string[];
  earliestDate?: string;
  latestDate?: string;
}

export interface PersonSearchResult {
  personId: number;
  personName: string;
  primaryRole?: string;
  epsteinRelationship?: string;
  placementCount: number;
  eventCount: number;
}

export const investigationApi = {
  searchPeople: (q: string, limit = 20) =>
    apiGet<PersonSearchResult[]>('/investigation/people/search', { q, limit }),

  getGeoTimeline: (params?: {
    dateFrom?: string;
    dateTo?: string;
    personName?: string;
    locationId?: number;
    limit?: number;
  }) => apiGet<GeoTimelineEntry[]>('/investigation/geo-timeline', params),

  getPersonConnections: (personId: number, params?: { dateFrom?: string; dateTo?: string }) =>
    apiGet<PersonConnections>(`/investigation/person/${personId}/connections`, params),

  getSharedPresence: (personIds: number[], params?: { dateFrom?: string; dateTo?: string }) =>
    apiGet<SharedPresence[]>('/investigation/shared-presence', {
      personIds: personIds.join(','),
      ...params,
    }),

  getFinancialNetwork: (personIds: number[], params?: { dateFrom?: string; dateTo?: string }) =>
    apiGet<ConnectedFinancial[]>('/investigation/financial-network', {
      personIds: personIds.join(','),
      ...params,
    }),
};
