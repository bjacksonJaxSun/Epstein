export interface Relationship {
  relationshipId: number;
  person1Id: number;
  person1Name: string;
  person2Id: number;
  person2Name: string;
  relationshipType: string;
  relationshipDescription?: string;
  startDate?: string;
  endDate?: string;
  isCurrent?: boolean;
  confidenceLevel?: string;
}
