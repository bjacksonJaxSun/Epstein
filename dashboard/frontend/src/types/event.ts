export interface TimelineEvent {
  eventId: number;
  eventType: string;
  title?: string;
  description?: string;
  eventDate: string;
  eventTime?: string;
  endDate?: string;
  endTime?: string;
  durationMinutes?: number;
  locationName?: string;
  confidenceLevel?: string;
  verificationStatus?: string;
  participantNames?: string[];
}
