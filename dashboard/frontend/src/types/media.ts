export interface MediaFile {
  mediaFileId: number;
  filePath: string;
  fileName: string;
  mediaType: 'image' | 'video' | 'audio' | 'document';
  fileFormat?: string;
  fileSizeBytes?: number;
  dateTaken?: string;
  gpsLatitude?: number;
  gpsLongitude?: number;
  widthPixels?: number;
  heightPixels?: number;
  durationSeconds?: number;
  caption?: string;
  isExplicit: boolean;
  isSensitive: boolean;
}
