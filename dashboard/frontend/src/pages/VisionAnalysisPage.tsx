import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Eye,
  Users,
  FileText,
  Camera,
  PenTool,
  Stamp,
  FileSignature,
  Loader2,
  AlertCircle,
  ChevronRight,
  ChevronLeft,
  User,
  Database,
  HardDrive,
  Clock,
} from 'lucide-react';
import { LoadingSpinner } from '@/components/shared';
import { cn } from '@/lib/utils';

interface VisionStats {
  totalImages: number;
  totalFaceDetections: number;
  totalFaceClusters: number;
  totalClassifications: number;
  documentCount: number;
  photoCount: number;
  withHandwriting: number;
  withSignatures: number;
  documentTypeCounts: { documentType: string; count: number }[];
}

interface FaceDetection {
  faceId: number;
  mediaFileId: number;
  mediaFilePath: string | null;
  faceIndex: number;
  boundingBox: string | null;
  clusterId: number | null;
  clusterName: string | null;
  confidence: number | null;
  createdAt: string;
}

interface FaceCluster {
  clusterId: number;
  personName: string | null;
  personId: number | null;
  faceCount: number;
  representativeFaceId: number | null;
  createdAt: string;
}

interface PagedResponse<T> {
  items: T[];
  totalCount: number;
  page: number;
  pageSize: number;
}

interface ImportStatus {
  totalDocuments: number;
  expectedDocuments: number;
  totalMediaFiles: number;
  totalPages: number;
  totalSizeBytes: number;
  lastEftaNumber: string | null;
  lastFilePath: string | null;
  lastUpdated: string | null;
  extractionStats: Record<string, number>;
  documentsWithText: number;
  documentsNeedingOcr: number;
  totalDocsWithImages: number;
}

const API_BASE = '/api/vision';

async function fetchStats(): Promise<VisionStats> {
  const res = await fetch(`${API_BASE}/stats`);
  if (!res.ok) throw new Error('Failed to fetch stats');
  return res.json();
}

async function fetchClusters(page: number, pageSize: number): Promise<PagedResponse<FaceCluster>> {
  const res = await fetch(`${API_BASE}/clusters?page=${page}&pageSize=${pageSize}`);
  if (!res.ok) throw new Error('Failed to fetch clusters');
  return res.json();
}

async function fetchFaces(page: number, pageSize: number): Promise<PagedResponse<FaceDetection>> {
  const res = await fetch(`${API_BASE}/faces?page=${page}&pageSize=${pageSize}`);
  if (!res.ok) throw new Error('Failed to fetch faces');
  return res.json();
}

async function fetchImportStatus(): Promise<ImportStatus> {
  const res = await fetch(`${API_BASE}/import-status`);
  if (!res.ok) throw new Error('Failed to fetch import status');
  return res.json();
}

function StatCard({
  label,
  value,
  icon: Icon,
  color = 'blue',
}: {
  label: string;
  value: number | string;
  icon: typeof Eye;
  color?: 'blue' | 'green' | 'amber' | 'purple' | 'red';
}) {
  const colors = {
    blue: 'bg-accent-blue/10 text-accent-blue border-accent-blue/30',
    green: 'bg-accent-green/10 text-accent-green border-accent-green/30',
    amber: 'bg-accent-amber/10 text-accent-amber border-accent-amber/30',
    purple: 'bg-accent-purple/10 text-accent-purple border-accent-purple/30',
    red: 'bg-accent-red/10 text-accent-red border-accent-red/30',
  };

  return (
    <div className={cn('rounded-lg border p-4', colors[color])}>
      <div className="flex items-center gap-3">
        <Icon className="h-8 w-8" />
        <div>
          <p className="text-2xl font-bold">{typeof value === 'number' ? value.toLocaleString() : value}</p>
          <p className="text-sm opacity-80">{label}</p>
        </div>
      </div>
    </div>
  );
}

export function VisionAnalysisPage() {
  const [activeTab, setActiveTab] = useState<'overview' | 'faces' | 'clusters' | 'classifications'>('overview');
  const [facesPage, setFacesPage] = useState(0);

  const { data: stats, isLoading: statsLoading, isError: statsError } = useQuery({
    queryKey: ['vision-stats'],
    queryFn: fetchStats,
    refetchInterval: 10000, // Refresh every 10 seconds
  });

  const { data: clusters, isLoading: clustersLoading } = useQuery({
    queryKey: ['vision-clusters'],
    queryFn: () => fetchClusters(0, 50),
  });

  const { data: faces, isLoading: facesLoading } = useQuery({
    queryKey: ['vision-faces', facesPage],
    queryFn: () => fetchFaces(facesPage, 24),
  });

  const { data: importStatus } = useQuery({
    queryKey: ['import-status'],
    queryFn: fetchImportStatus,
    refetchInterval: 5000, // Refresh every 5 seconds
  });

  const importProgress = importStatus
    ? (importStatus.totalDocuments / importStatus.expectedDocuments) * 100
    : 0;
  const isImportComplete = importProgress >= 100;

  // OCR progress: documents with text vs total single-image docs needing OCR
  const ocrProgress = importStatus && importStatus.totalDocsWithImages > 0
    ? (importStatus.documentsWithText / importStatus.totalDocsWithImages) * 100
    : 0;

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-text-primary flex items-center gap-2">
            <Eye className="h-6 w-6 text-accent-purple" />
            Vision Analysis
          </h2>
          <p className="mt-1 text-sm text-text-secondary">
            Face detection, clustering, and document classification results
          </p>
        </div>
        {statsLoading && (
          <div className="flex items-center gap-2 text-text-tertiary">
            <Loader2 className="h-4 w-4 animate-spin" />
            <span className="text-sm">Updating...</span>
          </div>
        )}
      </div>

      {/* Import Status */}
      {importStatus && (
        <div className={cn(
          'rounded-lg border p-4',
          isImportComplete
            ? 'border-accent-green/30 bg-accent-green/5'
            : 'border-accent-blue/30 bg-accent-blue/5'
        )}>
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Database className={cn('h-5 w-5', isImportComplete ? 'text-accent-green' : 'text-accent-blue')} />
              <span className="font-medium text-text-primary">
                {isImportComplete ? 'Import Complete' : 'Dataset 10 Import in Progress'}
              </span>
            </div>
            <div className="flex items-center gap-4 text-sm text-text-secondary">
              <span className="flex items-center gap-1">
                <Clock className="h-4 w-4" />
                {importStatus.lastUpdated
                  ? new Date(importStatus.lastUpdated).toLocaleTimeString()
                  : 'N/A'}
              </span>
            </div>
          </div>

          {/* Progress bar */}
          <div className="mb-3">
            <div className="flex justify-between text-sm mb-1">
              <span className="text-text-secondary">
                {importStatus.totalDocuments.toLocaleString()} / {importStatus.expectedDocuments.toLocaleString()} documents
              </span>
              <span className={cn('font-medium', isImportComplete ? 'text-accent-green' : 'text-accent-blue')}>
                {importProgress.toFixed(1)}%
              </span>
            </div>
            <div className="h-2 rounded-full bg-surface-sunken overflow-hidden">
              <div
                className={cn(
                  'h-full transition-all duration-500',
                  isImportComplete ? 'bg-accent-green' : 'bg-accent-blue'
                )}
                style={{ width: `${Math.min(100, importProgress)}%` }}
              />
            </div>
          </div>

          {/* Stats grid */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div className="flex items-center gap-2">
              <Camera className="h-4 w-4 text-text-tertiary" />
              <span className="text-text-secondary">Media:</span>
              <span className="text-text-primary font-medium">{importStatus.totalMediaFiles.toLocaleString()}</span>
            </div>
            <div className="flex items-center gap-2">
              <FileText className="h-4 w-4 text-text-tertiary" />
              <span className="text-text-secondary">Pages:</span>
              <span className="text-text-primary font-medium">{importStatus.totalPages.toLocaleString()}</span>
            </div>
            <div className="flex items-center gap-2">
              <HardDrive className="h-4 w-4 text-text-tertiary" />
              <span className="text-text-secondary">Size:</span>
              <span className="text-text-primary font-medium">
                {(importStatus.totalSizeBytes / 1024 / 1024 / 1024).toFixed(1)} GB
              </span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-text-secondary">Last:</span>
              <span className="text-text-primary font-medium font-mono text-xs">
                {importStatus.lastEftaNumber || 'N/A'}
              </span>
            </div>
          </div>

          {/* Extraction status breakdown */}
          {Object.keys(importStatus.extractionStats).length > 0 && (
            <div className="mt-3 pt-3 border-t border-border-subtle">
              <div className="flex flex-wrap gap-3 text-xs">
                {Object.entries(importStatus.extractionStats).map(([status, count]) => (
                  <span key={status} className="flex items-center gap-1">
                    <span className={cn(
                      'w-2 h-2 rounded-full',
                      status === 'completed' ? 'bg-accent-green' :
                      status === 'partial' ? 'bg-accent-amber' :
                      'bg-accent-blue'
                    )} />
                    <span className="text-text-secondary capitalize">{status}:</span>
                    <span className="text-text-primary">{count.toLocaleString()}</span>
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* OCR Progress */}
      {importStatus && importStatus.totalDocsWithImages > 0 && (
        <div className="rounded-lg border p-4 border-accent-amber/30 bg-accent-amber/5">
          <div className="flex items-center gap-2 mb-3">
            <FileText className="h-5 w-5 text-accent-amber" />
            <span className="font-medium text-text-primary">OCR Text Extraction</span>
          </div>

          <div className="mb-3">
            <div className="flex justify-between text-sm mb-1">
              <span className="text-text-secondary">
                Documents with text: {importStatus.documentsWithText.toLocaleString()} / {importStatus.totalDocsWithImages.toLocaleString()}
              </span>
              <span className="font-medium text-accent-amber">
                {ocrProgress.toFixed(1)}%
              </span>
            </div>
            <div className="h-2 rounded-full bg-surface-sunken overflow-hidden">
              <div
                className="h-full bg-accent-amber transition-all duration-500"
                style={{ width: `${Math.min(100, ocrProgress)}%` }}
              />
            </div>
          </div>

          <div className="text-sm text-text-secondary">
            Remaining: {importStatus.documentsNeedingOcr.toLocaleString()} documents need OCR
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="flex items-center gap-2 border-b border-border-subtle pb-2">
        {(['overview', 'faces', 'clusters', 'classifications'] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={cn(
              'px-4 py-2 text-sm font-medium rounded-t-lg transition-colors',
              activeTab === tab
                ? 'bg-surface-overlay text-accent-blue border-b-2 border-accent-blue'
                : 'text-text-secondary hover:text-text-primary hover:bg-surface-overlay/50'
            )}
          >
            {tab.charAt(0).toUpperCase() + tab.slice(1)}
          </button>
        ))}
      </div>

      {statsError && (
        <div className="flex items-center gap-3 rounded-lg border border-accent-red/30 bg-accent-red/5 p-4">
          <AlertCircle className="h-5 w-5 text-accent-red" />
          <p className="text-sm text-accent-red">Failed to load vision analysis data</p>
        </div>
      )}

      {/* Overview Tab */}
      {activeTab === 'overview' && stats && (
        <div className="space-y-6">
          {/* Main Stats */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <StatCard label="Total Images" value={stats.totalImages} icon={Camera} color="blue" />
            <StatCard label="Face Detections" value={stats.totalFaceDetections} icon={Users} color="purple" />
            <StatCard label="Face Clusters" value={stats.totalFaceClusters} icon={Users} color="green" />
            <StatCard label="Classifications" value={stats.totalClassifications} icon={FileText} color="amber" />
          </div>

          {/* Classification Stats */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <StatCard label="Documents" value={stats.documentCount} icon={FileText} color="blue" />
            <StatCard label="Photos" value={stats.photoCount} icon={Camera} color="green" />
            <StatCard label="With Handwriting" value={stats.withHandwriting} icon={PenTool} color="amber" />
            <StatCard label="With Signatures" value={stats.withSignatures} icon={FileSignature} color="purple" />
          </div>

          {/* Document Types */}
          {stats.documentTypeCounts.length > 0 && (
            <div className="rounded-lg border border-border-subtle bg-surface-raised p-4">
              <h3 className="text-sm font-semibold text-text-primary mb-4">Document Types</h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {stats.documentTypeCounts.map(({ documentType, count }) => (
                  <div
                    key={documentType}
                    className="flex items-center justify-between rounded-md bg-surface-overlay p-3"
                  >
                    <span className="text-sm text-text-secondary capitalize">{documentType}</span>
                    <span className="text-sm font-medium text-text-primary">{count.toLocaleString()}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Processing Status */}
          <div className="rounded-lg border border-border-subtle bg-surface-raised p-4">
            <h3 className="text-sm font-semibold text-text-primary mb-2">Processing Status</h3>
            <div className="space-y-2">
              <div className="flex items-center justify-between text-sm">
                <span className="text-text-secondary">Face Detection Progress</span>
                <span className="text-text-primary">
                  {stats.totalFaceDetections > 0 ? 'In Progress' : 'Not Started'}
                </span>
              </div>
              <div className="h-2 rounded-full bg-surface-sunken overflow-hidden">
                <div
                  className="h-full bg-accent-purple transition-all duration-500"
                  style={{
                    width: stats.totalImages > 0
                      ? `${Math.min(100, (stats.totalFaceDetections / stats.totalImages) * 100 * 50)}%`
                      : '0%',
                  }}
                />
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-text-secondary">Document Classification Progress</span>
                <span className="text-text-primary">
                  {stats.totalClassifications > 0 ? 'In Progress' : 'Pending'}
                </span>
              </div>
              <div className="h-2 rounded-full bg-surface-sunken overflow-hidden">
                <div
                  className="h-full bg-accent-amber transition-all duration-500"
                  style={{
                    width: stats.totalImages > 0
                      ? `${Math.min(100, (stats.totalClassifications / stats.totalImages) * 100)}%`
                      : '0%',
                  }}
                />
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Faces Tab */}
      {activeTab === 'faces' && (
        <div className="space-y-4">
          {facesLoading ? (
            <LoadingSpinner className="py-12" />
          ) : faces && faces.items.length > 0 ? (
            <>
              <div className="flex items-center justify-between">
                <p className="text-sm text-text-secondary">
                  Showing {faces.items.length} of {faces.totalCount} detected faces
                </p>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setFacesPage((p) => Math.max(0, p - 1))}
                    disabled={facesPage <= 0}
                    className="p-2 rounded-md bg-surface-overlay hover:bg-surface-sunken disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <ChevronLeft className="h-4 w-4" />
                  </button>
                  <span className="text-sm text-text-secondary">
                    Page {facesPage + 1} of {Math.ceil(faces.totalCount / 24)}
                  </span>
                  <button
                    onClick={() => setFacesPage((p) => p + 1)}
                    disabled={facesPage >= Math.ceil(faces.totalCount / 24) - 1}
                    className="p-2 rounded-md bg-surface-overlay hover:bg-surface-sunken disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <ChevronRight className="h-4 w-4" />
                  </button>
                </div>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-4">
                {faces.items.map((face) => (
                  <div
                    key={face.faceId}
                    className="rounded-lg border border-border-subtle bg-surface-raised overflow-hidden hover:border-accent-purple/50 transition-colors"
                  >
                    <div className="aspect-square relative bg-surface-sunken">
                      {face.mediaFilePath ? (
                        <img
                          src={`/api/media/${face.mediaFileId}/file`}
                          alt={`Face ${face.faceIndex + 1}`}
                          className="w-full h-full object-cover"
                          onError={(e) => {
                            (e.target as HTMLImageElement).style.display = 'none';
                          }}
                        />
                      ) : (
                        <div className="flex items-center justify-center h-full">
                          <User className="h-8 w-8 text-text-disabled" />
                        </div>
                      )}
                    </div>
                    <div className="p-2">
                      <p className="text-xs text-text-secondary truncate">
                        {face.clusterName || (face.clusterId ? `Cluster #${face.clusterId}` : 'Unclustered')}
                      </p>
                      {face.confidence && (
                        <p className="text-xs text-text-tertiary">
                          {(face.confidence * 100).toFixed(0)}% confidence
                        </p>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <div className="flex flex-col items-center justify-center py-12 text-text-disabled">
              <User className="h-12 w-12 mb-4" />
              <p>No faces detected yet</p>
              <p className="text-sm">Face detection is processing images</p>
            </div>
          )}
        </div>
      )}

      {/* Clusters Tab */}
      {activeTab === 'clusters' && (
        <div className="space-y-4">
          {clustersLoading ? (
            <LoadingSpinner className="py-12" />
          ) : clusters && clusters.items.length > 0 ? (
            <>
              <p className="text-sm text-text-secondary">
                {clusters.totalCount} face clusters found
              </p>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {clusters.items.map((cluster) => (
                  <div
                    key={cluster.clusterId}
                    className="rounded-lg border border-border-subtle bg-surface-raised p-4 hover:border-accent-blue/50 transition-colors"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div className="flex h-12 w-12 items-center justify-center rounded-full bg-accent-purple/20">
                          <Users className="h-6 w-6 text-accent-purple" />
                        </div>
                        <div>
                          <p className="font-medium text-text-primary">
                            {cluster.personName || `Cluster #${cluster.clusterId}`}
                          </p>
                          <p className="text-sm text-text-secondary">
                            {cluster.faceCount} appearances
                          </p>
                        </div>
                      </div>
                      <ChevronRight className="h-5 w-5 text-text-tertiary" />
                    </div>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <div className="flex flex-col items-center justify-center py-12 text-text-disabled">
              <Users className="h-12 w-12 mb-4" />
              <p>No face clusters found yet</p>
              <p className="text-sm">Face clustering runs after detection completes</p>
            </div>
          )}
        </div>
      )}

      {/* Classifications Tab */}
      {activeTab === 'classifications' && (
        <div className="space-y-4">
          {stats && stats.totalClassifications > 0 ? (
            <>
              <p className="text-sm text-text-secondary">
                {stats.totalClassifications.toLocaleString()} images classified
              </p>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <StatCard label="Documents" value={stats.documentCount} icon={FileText} color="blue" />
                <StatCard label="Photos" value={stats.photoCount} icon={Camera} color="green" />
                <StatCard label="Handwriting" value={stats.withHandwriting} icon={PenTool} color="amber" />
                <StatCard label="Signatures" value={stats.withSignatures} icon={FileSignature} color="purple" />
              </div>
              {stats.documentTypeCounts.length > 0 && (
                <div className="rounded-lg border border-border-subtle bg-surface-raised p-4">
                  <h3 className="text-sm font-semibold text-text-primary mb-4">By Document Type</h3>
                  <div className="space-y-2">
                    {stats.documentTypeCounts.map(({ documentType, count }) => (
                      <div
                        key={documentType}
                        className="flex items-center justify-between py-2 border-b border-border-subtle last:border-0"
                      >
                        <span className="text-sm text-text-secondary capitalize">{documentType}</span>
                        <span className="text-sm font-medium text-text-primary">{count.toLocaleString()}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          ) : (
            <div className="flex flex-col items-center justify-center py-12 text-text-disabled">
              <FileText className="h-12 w-12 mb-4" />
              <p>No classifications yet</p>
              <p className="text-sm">Document classification runs after face detection</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
