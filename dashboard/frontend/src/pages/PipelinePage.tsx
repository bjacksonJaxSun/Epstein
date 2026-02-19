import { useQuery } from '@tanstack/react-query';
import {
  Database,
  FileText,
  Image,
  Download,
  Upload,
  Eye,
  Cpu,
  Server,
  HardDrive,
  CheckCircle,
  XCircle,
  Clock,
  Loader2,
  RefreshCw,
} from 'lucide-react';
import { apiGet } from '@/api/client';
import { cn } from '@/lib/utils';

interface PipelineStatus {
  totalDocuments: number;
  documentsWithText: number;
  documentsNeedingOcr: number;
  totalChunks: number;
  chunksWithEmbeddings: number;
  totalImages: number;
  downloadStatus: ProcessStatus;
  embeddingStatus: ProcessStatus;
  importStatus: ProcessStatus;
  ocrStatus: ProcessStatus;
  imageExtractionStatus: ProcessStatus;
transcriptionStatus?: ProcessStatus;  totalMediaFiles?: number;  mediaFilesTranscribed?: number;
  apiStatus: ServiceStatus;
  databaseStatus: ServiceStatus;
}

interface ProcessStatus {
  status: string;
  percentComplete?: number;
  processedDocuments?: number;
  totalDocuments?: number;
  processedChunks?: number;
  totalChunks?: number;
  currentFile?: number;
  totalFiles?: number;
  filesDownloaded?: number;
  filesErrored?: number;
  successCount?: number;
  failedCount?: number;
  imagesExtracted?: number;
  docsWithImages?: number;
  notInIndex?: number;
  errorCount?: number;
  docsPerMinute?: number;
  chunksPerSecond?: number;
  estimatedSecondsRemaining?: number;
  lastUpdate?: string;
  importedCount?: number;
  skippedCount?: number;
  currentDataset?: string;
}

interface ServiceStatus {
  status: string;
  uptime?: number;
  databaseSizeBytes?: number;
}

const pipelineApi = {
  getStatus: () => apiGet<PipelineStatus>('/pipeline/status'),
};

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`;
}

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
  const hours = Math.floor(seconds / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  return `${hours}h ${mins}m`;
}

function formatUptime(seconds: number): string {
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  if (days > 0) return `${days}d ${hours}h`;
  if (hours > 0) return `${hours}h ${mins}m`;
  return `${mins}m`;
}

function StatusBadge({ status }: { status: string }) {
  const config: Record<string, { color: string; icon: typeof CheckCircle }> = {
    running: { color: 'text-green-400 bg-green-400/10', icon: Loader2 },
    complete: { color: 'text-green-400 bg-green-400/10', icon: CheckCircle },
    idle: { color: 'text-blue-400 bg-blue-400/10', icon: Clock },
    not_started: { color: 'text-gray-400 bg-gray-400/10', icon: Clock },
    error: { color: 'text-red-400 bg-red-400/10', icon: XCircle },
    downloading: { color: 'text-amber-400 bg-amber-400/10', icon: Download },
    scraping: { color: 'text-amber-400 bg-amber-400/10', icon: RefreshCw },
  };

  const { color, icon: Icon } = config[status] || config.idle;
  const isAnimated = status === 'running' || status === 'downloading' || status === 'scraping';

  return (
    <span className={cn('inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium', color)}>
      <Icon className={cn('h-3 w-3', isAnimated && 'animate-spin')} />
      {status.replace('_', ' ')}
    </span>
  );
}

function ProgressBar({ percent, className }: { percent: number; className?: string }) {
  return (
    <div className={cn('h-2 bg-surface-sunken rounded-full overflow-hidden', className)}>
      <div
        className="h-full bg-accent-blue transition-all duration-500"
        style={{ width: `${Math.min(100, percent)}%` }}
      />
    </div>
  );
}

function StatCard({
  icon: Icon,
  label,
  value,
  subValue,
}: {
  icon: typeof Database;
  label: string;
  value: string | number;
  subValue?: string;
}) {
  return (
    <div className="bg-surface-raised border border-border-subtle rounded-lg p-4">
      <div className="flex items-center gap-3">
        <div className="p-2 rounded-lg bg-accent-blue/10">
          <Icon className="h-5 w-5 text-accent-blue" />
        </div>
        <div>
          <p className="text-xs text-text-tertiary uppercase tracking-wider">{label}</p>
          <p className="text-xl font-semibold text-text-primary">{(value ?? 0).toLocaleString()}</p>
          {subValue && <p className="text-xs text-text-tertiary">{subValue}</p>}
        </div>
      </div>
    </div>
  );
}

function ProcessCard({
  icon: Icon,
  title,
  status,
}: {
  icon: typeof Download;
  title: string;
  status: ProcessStatus;
}) {
  if (!status) {
    return null;
  }
  const hasProgress = status.percentComplete !== undefined && status.percentComplete > 0;

  return (
    <div className="bg-surface-raised border border-border-subtle rounded-lg p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Icon className="h-5 w-5 text-text-secondary" />
          <h3 className="font-medium text-text-primary">{title}</h3>
        </div>
        <StatusBadge status={status.status} />
      </div>

      {hasProgress && (
        <div className="mb-3">
          <div className="flex justify-between text-xs text-text-tertiary mb-1">
            <span>{status.percentComplete?.toFixed(1)}%</span>
            {status.estimatedSecondsRemaining && status.estimatedSecondsRemaining > 0 && (
              <span>ETA: {formatDuration(status.estimatedSecondsRemaining)}</span>
            )}
          </div>
          <ProgressBar percent={status.percentComplete || 0} />
        </div>
      )}

      <div className="grid grid-cols-2 gap-2 text-xs">
        {status.processedDocuments !== undefined && (
          <div>
            <span className="text-text-tertiary">Processed:</span>
            <span className="ml-1 text-text-primary">
              {(status.processedDocuments ?? 0).toLocaleString()}
              {status.totalDocuments ? ` / ${(status.totalDocuments ?? 0).toLocaleString()}` : ''}
            </span>
          </div>
        )}
        {status.processedChunks !== undefined && (
          <div>
            <span className="text-text-tertiary">Chunks:</span>
            <span className="ml-1 text-text-primary">
              {(status.processedChunks ?? 0).toLocaleString()}
              {status.totalChunks ? ` / ${(status.totalChunks ?? 0).toLocaleString()}` : ''}
            </span>
          </div>
        )}
        {status.successCount !== undefined && (
          <div>
            <span className="text-text-tertiary">Success:</span>
            <span className="ml-1 text-green-400">{(status.successCount ?? 0).toLocaleString()}</span>
          </div>
        )}
        {status.failedCount !== undefined && status.failedCount > 0 && (
          <div>
            <span className="text-text-tertiary">Failed:</span>
            <span className="ml-1 text-red-400">{(status.failedCount ?? 0).toLocaleString()}</span>
          </div>
        )}
        {status.imagesExtracted !== undefined && (
          <div>
            <span className="text-text-tertiary">Images:</span>
            <span className="ml-1 text-text-primary">{(status.imagesExtracted ?? 0).toLocaleString()}</span>
          </div>
        )}
        {status.docsWithImages !== undefined && (
          <div>
            <span className="text-text-tertiary">Docs w/ images:</span>
            <span className="ml-1 text-text-primary">{(status.docsWithImages ?? 0).toLocaleString()}</span>
          </div>
        )}
        {status.filesDownloaded !== undefined && (
          <div>
            <span className="text-text-tertiary">Downloaded:</span>
            <span className="ml-1 text-text-primary">{(status.filesDownloaded ?? 0).toLocaleString()}</span>
          </div>
        )}
        {status.filesErrored !== undefined && status.filesErrored > 0 && (
          <div>
            <span className="text-text-tertiary">Errors:</span>
            <span className="ml-1 text-red-400">{(status.filesErrored ?? 0).toLocaleString()}</span>
          </div>
        )}
        {status.importedCount !== undefined && (
          <div>
            <span className="text-text-tertiary">Imported:</span>
            <span className="ml-1 text-text-primary">{(status.importedCount ?? 0).toLocaleString()}</span>
          </div>
        )}
        {status.skippedCount !== undefined && (
          <div>
            <span className="text-text-tertiary">Skipped:</span>
            <span className="ml-1 text-text-tertiary">{(status.skippedCount ?? 0).toLocaleString()}</span>
          </div>
        )}
        {status.docsPerMinute !== undefined && status.docsPerMinute > 0 && (
          <div>
            <span className="text-text-tertiary">Speed:</span>
            <span className="ml-1 text-text-primary">{status.docsPerMinute.toFixed(1)}/min</span>
          </div>
        )}
        {status.chunksPerSecond !== undefined && status.chunksPerSecond > 0 && (
          <div>
            <span className="text-text-tertiary">Speed:</span>
            <span className="ml-1 text-text-primary">{status.chunksPerSecond.toFixed(1)}/sec</span>
          </div>
        )}
        {status.lastUpdate && (
          <div className="col-span-2">
            <span className="text-text-tertiary">Updated:</span>
            <span className="ml-1 text-text-primary">
              {new Date(status.lastUpdate).toLocaleTimeString()}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}

export function PipelinePage() {
  const { data: status, isLoading, error, refetch } = useQuery({
    queryKey: ['pipeline-status'],
    queryFn: pipelineApi.getStatus,
    refetchInterval: 5000,
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-96">
        <Loader2 className="h-8 w-8 animate-spin text-accent-blue" />
      </div>
    );
  }

  if (error || !status) {
    return (
      <div className="flex flex-col items-center justify-center h-96 gap-4">
        <XCircle className="h-12 w-12 text-red-400" />
        <p className="text-text-secondary">Failed to load pipeline status</p>
        <button
          onClick={() => refetch()}
          className="px-4 py-2 bg-accent-blue text-white rounded-lg hover:bg-accent-blue/80"
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-text-primary">Pipeline Status</h1>
          <p className="text-sm text-text-tertiary mt-1">
            Monitor document processing and extraction pipelines
          </p>
        </div>
        <button
          onClick={() => refetch()}
          className="flex items-center gap-2 px-3 py-2 text-sm bg-surface-raised border border-border-subtle rounded-lg hover:bg-surface-overlay transition-colors"
        >
          <RefreshCw className="h-4 w-4" />
          Refresh
        </button>
      </div>

      {/* Overview Stats */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        <StatCard icon={FileText} label="Documents" value={status.totalDocuments} />
        <StatCard
          icon={FileText}
          label="With Text"
          value={status.documentsWithText}
          subValue={`${((status.documentsWithText / status.totalDocuments) * 100).toFixed(1)}%`}
        />
        <StatCard icon={Eye} label="Need OCR" value={status.documentsNeedingOcr} />
<StatCard icon={Image} label="Media Files" value={status.totalMediaFiles || 0} />        <StatCard icon={CheckCircle} label="Transcribed" value={status.mediaFilesTranscribed || 0} />
        <StatCard icon={Database} label="Chunks" value={status.totalChunks} />
        <StatCard
          icon={Cpu}
          label="Embeddings"
          value={status.chunksWithEmbeddings}
          subValue={`${((status.chunksWithEmbeddings / status.totalChunks) * 100).toFixed(1)}%`}
        />
        <StatCard icon={Image} label="Images" value={status.totalImages} />
      </div>

      {/* Service Status */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-surface-raised border border-border-subtle rounded-lg p-4">
          <div className="flex items-center gap-2 mb-3">
            <Server className="h-5 w-5 text-text-secondary" />
            <h3 className="font-medium text-text-primary">API Server</h3>
            <StatusBadge status={(status.apiStatus?.status ?? 'unknown')} />
          </div>
          <div className="text-sm text-text-tertiary">
            Uptime: {(status.apiStatus?.uptime ?? 0) ? formatUptime((status.apiStatus?.uptime ?? 0)) : 'N/A'}
          </div>
        </div>

        <div className="bg-surface-raised border border-border-subtle rounded-lg p-4">
          <div className="flex items-center gap-2 mb-3">
            <HardDrive className="h-5 w-5 text-text-secondary" />
            <h3 className="font-medium text-text-primary">Database</h3>
            <StatusBadge status={(status.databaseStatus?.status ?? 'unknown')} />
          </div>
          <div className="text-sm text-text-tertiary">
            Size: {(status.databaseStatus?.databaseSizeBytes ?? 0) ? formatBytes((status.databaseStatus?.databaseSizeBytes ?? 0)) : 'N/A'}
          </div>
        </div>
      </div>

      {/* Process Status Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <ProcessCard icon={Download} title="Download" status={status.downloadStatus} />
        <ProcessCard icon={Upload} title="Import" status={status.importStatus} />
        <ProcessCard icon={Eye} title="OCR" status={status.ocrStatus} />
{status.transcriptionStatus && <ProcessCard icon={Cpu} title="Transcription" status={status.transcriptionStatus} />}
        <ProcessCard icon={Image} title="Image Extraction" status={status.imageExtractionStatus} />
        <ProcessCard icon={Cpu} title="Embeddings" status={status.embeddingStatus} />
      </div>
    </div>
  );
}
