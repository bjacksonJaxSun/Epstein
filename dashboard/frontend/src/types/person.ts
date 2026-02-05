export interface Person {
  personId: number;
  fullName: string;
  nameVariations?: string[];
  primaryRole?: string;
  roles?: string[];
  emailAddresses?: string[];
  phoneNumbers?: string[];
  addresses?: string[];
  isRedacted: boolean;
  victimIdentifier?: string;
  dateOfBirth?: string;
  nationality?: string;
  occupation?: string;
  confidenceLevel: string;
  notes?: string;
  createdAt: string;
  updatedAt?: string;
}

export interface PersonDetail extends Person {
  relationshipCount?: number;
  eventCount?: number;
  documentCount?: number;
  financialTransactionCount?: number;
  mediaCount?: number;
}

export interface EntityFrequency {
  id: number;
  name: string;
  entityType: string;
  primaryRole?: string;
  documentCount: number;
  eventCount: number;
  relationshipCount: number;
  financialCount: number;
  financialTotal: number;
  mediaCount: number;
  totalMentions: number;
}
