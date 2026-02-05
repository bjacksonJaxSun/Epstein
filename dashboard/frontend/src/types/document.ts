export interface Document {
  documentId: number;
  eftaNumber: string;
  filePath: string;
  documentType?: string;
  documentDate?: string;
  documentTitle?: string;
  author?: string;
  recipient?: string;
  subject?: string;
  fullText?: string;
  pageCount?: number;
  fileSizeBytes?: number;
  classificationLevel?: string;
  isRedacted: boolean;
  redactionLevel?: string;
  sourceAgency?: string;
  extractionStatus?: string;
  extractionConfidence?: number;
  createdAt: string;
  updatedAt?: string;
}
