import { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Database,
  FileText,
  Image,
  Cpu,
  Server,
  HardDrive,
  CheckCircle,
  XCircle,
  Clock,
  Loader2,
  RefreshCw,
  Activity,
  Users,
  AlertTriangle,
  ChevronDown,
  ChevronRight,
  Square,
  Power,
  RotateCcw,
  Zap,
  Pause,
  Play,
  Trash2,
  Search,
  ArrowUp,
  ArrowDown,
  ArrowUpDown,
} from 'lucide-react';
import { apiGet, apiPost } from '@/api/client';
import { cn } from '@/lib/utils';
import { ThroughputChart, type ThroughputBucket } from '@/components/pipeline/ThroughputChart';

// --- Existing interfaces ---

interface PipelineStatus {
  totalDocuments: number;
  documentsWithText: number;
  documentsNeedingOcr: number;
  totalChunks: number;
  chunksWithEmbeddings: number;
  totalImages: number;
  totalMediaFiles?: number;
  mediaFilesTranscribed?: number;
  apiStatus: ServiceStatus;
  databaseStatus: ServiceStatus;
}

interface ServiceStatus {
  status: string;
  uptime?: number;
  databaseSizeBytes?: number;
}

// --- New interfaces ---

interface NodeInfo {
  hostname: string;
  isOnline: boolean;
  totalWorkers: number;
  activeJobs: number;
  codeVersion: string | null;
  workers: WorkerInfo[];
}

interface WorkerInfo {
  workerId: string;
  status: string;
  activeJobs: number;
  jobTypes: string[];
  lastHeartbeat: string | null;
  secondsSinceHeartbeat: number;
  startedAt: string | null;
  codeVersion: string | null;
  pendingCommand: string | null;
}

interface JobQueueSummary {
  jobType: string;
  pending: number;
  claimed: number;
  running: number;
  completed: number;
  failed: number;
  skipped: number;
  total: number;
  pctComplete: number;
  completed5Min: number;
  paused: number;
  stopped: number;
}

interface PipelineKpis {
  completed1Min: number;
  completed5Min: number;
  completed15Min: number;
  perMachineThroughput: { hostname: string; completed5Min: number }[];
  avgDuration: { jobType: string; avgSec: number; minSec: number; maxSec: number }[];
  queueEta: { jobType: string; pending: number; rate5Min: number; etaMinutes: number | null }[];
}

interface JobError {
  jobId: number;
  jobType: string;
  errorMessage: string;
  completedAt: string | null;
  claimedBy: string | null;
}

interface JobsResponse {
  summary: JobQueueSummary[];
  errors: JobError[];
}

interface LaunchStatus {
  extractionDirFound: boolean;
  scripts: Record<string, boolean>;
}

interface LaunchResult {
  success: boolean;
  message: string;
  jobsSubmitted?: number;
}

// --- API ---

const pipelineApi = {
  getStatus: () => apiGet<PipelineStatus>('/pipeline/status'),
  getNodes: () => apiGet<NodeInfo[]>('/pipeline/nodes'),
  getJobs: () => apiGet<JobsResponse>('/pipeline/jobs'),
  getKpis: () => apiGet<PipelineKpis>('/pipeline/kpis'),
  getThroughputHistory: (minutes = 30, bucketSeconds = 60) =>
    apiGet<ThroughputBucket[]>(`/pipeline/throughput-history?minutes=${minutes}&bucketSeconds=${bucketSeconds}`),
  sendNodeCommand: (hostname: string, command: string) =>
    apiPost<{ success: boolean; message: string }>(`/pipeline/nodes/${encodeURIComponent(hostname)}/command`, { command }),
  sendWorkerCommand: (workerId: string, command: string) =>
    apiPost<{ success: boolean; message: string }>(`/pipeline/workers/${encodeURIComponent(workerId)}/command`, { command }),
  pauseJobType: (jobType: string) =>
    apiPost<{ success: boolean; affected: number }>(`/pipeline/job-types/${encodeURIComponent(jobType)}/pause`, {}),
  resumeJobType: (jobType: string) =>
    apiPost<{ success: boolean; affected: number }>(`/pipeline/job-types/${encodeURIComponent(jobType)}/resume`, {}),
  stopJobType: (jobType: string) =>
    apiPost<{ success: boolean; affected: number }>(`/pipeline/job-types/${encodeURIComponent(jobType)}/stop`, {}),
  clearStoppedJobs: (jobType: string) =>
    apiPost<{ success: boolean; affected: number }>(`/pipeline/job-types/${encodeURIComponent(jobType)}/clear-stopped`, {}),
  retryFailedJobs: (jobType: string) =>
    apiPost<{ success: boolean; affected: number }>(`/pipeline/job-types/${encodeURIComponent(jobType)}/retry-failed`, {}),
  getLaunchStatus: () => apiGet<LaunchStatus>('/pipeline/launch/status'),
  submitExtractText: () => apiPost<LaunchResult>('/pipeline/launch/submit-extract-text', {}),
  submitChunkEmbed: () => apiPost<LaunchResult>('/pipeline/launch/submit-chunk-embed', {}),
  startWorkers: () => apiPost<LaunchResult>('/pipeline/launch/start-workers', {}),
  startEmbeddingServer: () => apiPost<LaunchResult>('/pipeline/launch/start-embedding-server', {}),
};

// --- Utility functions ---

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`;
}

function formatUptime(seconds: number): string {
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  if (days > 0) return `${days}d ${hours}h`;
  if (hours > 0) return `${hours}h ${mins}m`;
  return `${mins}m`;
}

function formatEta(minutes: number | null): string {
  if (minutes === null || minutes <= 0) return '--';
  if (minutes < 60) return `${Math.round(minutes)}m`;
  if (minutes < 1440) return `${Math.round(minutes / 60)}h`;
  return `${(minutes / 1440).toFixed(1)}d`;
}

function formatDurationSec(sec: number): string {
  if (sec < 1) return `${(sec * 1000).toFixed(0)}ms`;
  if (sec < 60) return `${sec.toFixed(1)}s`;
  return `${Math.floor(sec / 60)}m ${Math.round(sec % 60)}s`;
}

function formatTimeAgo(dateStr: string | null): string {
  if (!dateStr) return 'N/A';
  const diff = (Date.now() - new Date(dateStr).getTime()) / 1000;
  if (diff < 60) return `${Math.round(diff)}s ago`;
  if (diff < 3600) return `${Math.round(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.round(diff / 3600)}h ago`;
  return `${Math.round(diff / 86400)}d ago`;
}

// --- Shared components ---

function StatusBadge({ status }: { status: string }) {
  const config: Record<string, { color: string; icon: typeof CheckCircle }> = {
    running: { color: 'text-green-400 bg-green-400/10', icon: Loader2 },
    complete: { color: 'text-green-400 bg-green-400/10', icon: CheckCircle },
    busy: { color: 'text-amber-400 bg-amber-400/10', icon: Activity },
    idle: { color: 'text-blue-400 bg-blue-400/10', icon: Clock },
    not_started: { color: 'text-gray-400 bg-gray-400/10', icon: Clock },
    error: { color: 'text-red-400 bg-red-400/10', icon: XCircle },
    offline: { color: 'text-red-400 bg-red-400/10', icon: XCircle },
    unknown: { color: 'text-gray-400 bg-gray-400/10', icon: Clock },
  };

  const { color, icon: Icon } = config[status] || config.unknown;
  const isAnimated = status === 'running' || status === 'busy';

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
  color,
}: {
  icon: typeof Database;
  label: string;
  value: string | number;
  subValue?: string;
  color?: string;
}) {
  return (
    <div className="bg-surface-raised border border-border-subtle rounded-lg p-4">
      <div className="flex items-center gap-3">
        <div className={cn('p-2 rounded-lg', color || 'bg-accent-blue/10')}>
          <Icon className={cn('h-5 w-5', color ? 'text-current' : 'text-accent-blue')} />
        </div>
        <div>
          <p className="text-xs text-text-tertiary uppercase tracking-wider">{label}</p>
          <p className="text-xl font-semibold text-text-primary">{typeof value === 'number' ? value.toLocaleString() : value}</p>
          {subValue && <p className="text-xs text-text-tertiary">{subValue}</p>}
        </div>
      </div>
    </div>
  );
}

// --- Sort/filter helpers for Job Queues ---

type SortCol = 'jobType' | 'pending' | 'paused' | 'stopped' | 'running' | 'completed' | 'failed' | 'total' | 'rate' | 'eta' | 'pct';

function SortHeader({
  col, label, current, dir, onSort, align = 'right',
}: {
  col: SortCol;
  label: string;
  current: SortCol;
  dir: 'asc' | 'desc';
  onSort: (col: SortCol) => void;
  align?: 'left' | 'right';
}) {
  const active = col === current;
  return (
    <th
      className="px-4 py-3 text-text-tertiary font-medium cursor-pointer select-none hover:text-text-secondary group whitespace-nowrap"
      onClick={() => onSort(col)}
    >
      <div className={cn('flex items-center gap-1', align === 'right' ? 'justify-end' : 'justify-start')}>
        {label}
        {active
          ? (dir === 'asc' ? <ArrowUp className="h-3 w-3 flex-shrink-0" /> : <ArrowDown className="h-3 w-3 flex-shrink-0" />)
          : <ArrowUpDown className="h-3 w-3 flex-shrink-0 opacity-0 group-hover:opacity-40" />}
      </div>
    </th>
  );
}

// --- Tab Navigation ---

type TabKey = 'overview' | 'nodes' | 'jobs' | 'errors' | 'launch';

const tabs: { key: TabKey; label: string; icon: typeof Activity }[] = [
  { key: 'overview', label: 'Overview', icon: Activity },
  { key: 'nodes', label: 'Nodes', icon: Server },
  { key: 'jobs', label: 'Job Queues', icon: Database },
  { key: 'errors', label: 'Errors', icon: AlertTriangle },
  { key: 'launch', label: 'Launch', icon: Zap },
];

// --- Overview Tab ---

function OverviewTab({ status, kpis, jobs, nodes, throughputHistory }: {
  status: PipelineStatus | undefined;
  kpis: PipelineKpis | undefined;
  jobs: JobsResponse | undefined;
  nodes: NodeInfo[] | undefined;
  throughputHistory: ThroughputBucket[] | undefined;
}) {
  const onlineNodes = nodes?.filter(n => n.isOnline).length ?? 0;
  const totalNodes = nodes?.length ?? 0;
  const totalActiveWorkers = nodes?.reduce((sum, n) => sum + n.workers.filter(w => w.secondsSinceHeartbeat < 60).length, 0) ?? 0;
  const totalPending = jobs?.summary.reduce((sum, s) => sum + s.pending, 0) ?? 0;

  return (
    <div className="space-y-6">
      {/* KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
        <StatCard
          icon={Zap}
          label="Throughput"
          value={kpis ? `${kpis.completed1Min}/min` : '--'}
          subValue={kpis ? `5m: ${kpis.completed5Min} | 15m: ${kpis.completed15Min}` : undefined}
        />
        <StatCard
          icon={Server}
          label="Online Nodes"
          value={`${onlineNodes} / ${totalNodes}`}
        />
        <StatCard
          icon={Users}
          label="Active Workers"
          value={totalActiveWorkers}
        />
        <StatCard
          icon={Clock}
          label="Queue Depth"
          value={totalPending}
        />
        {kpis?.queueEta && kpis.queueEta.length > 0 && (
          <div className="bg-surface-raised border border-border-subtle rounded-lg p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-accent-blue/10">
                <Clock className="h-5 w-5 text-accent-blue" />
              </div>
              <div>
                <p className="text-xs text-text-tertiary uppercase tracking-wider">ETA</p>
                <div className="space-y-0.5">
                  {kpis.queueEta.filter(e => e.pending > 0).map(e => (
                    <p key={e.jobType} className="text-sm text-text-primary">
                      <span className="text-text-tertiary">{e.jobType}:</span> {formatEta(e.etaMinutes)}
                    </p>
                  ))}
                  {kpis.queueEta.filter(e => e.pending > 0).length === 0 && (
                    <p className="text-xl font-semibold text-text-primary">--</p>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Throughput Chart */}
      <ThroughputChart data={throughputHistory} />

      {/* Document Stats */}
      {status && (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
          <StatCard icon={FileText} label="Documents" value={status.totalDocuments} />
          <StatCard
            icon={FileText}
            label="With Text"
            value={status.documentsWithText}
            subValue={status.totalDocuments > 0 ? `${((status.documentsWithText / status.totalDocuments) * 100).toFixed(1)}%` : undefined}
          />
          <StatCard icon={Image} label="Media Files" value={status.totalMediaFiles || 0} />
          <StatCard icon={CheckCircle} label="Transcribed" value={status.mediaFilesTranscribed || 0} />
          <StatCard icon={Database} label="Chunks" value={status.totalChunks} />
          <StatCard
            icon={Cpu}
            label="Embeddings"
            value={status.chunksWithEmbeddings}
            subValue={status.totalChunks > 0 ? `${((status.chunksWithEmbeddings / status.totalChunks) * 100).toFixed(1)}%` : undefined}
          />
        </div>
      )}

      {/* Service Status */}
      {status && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="bg-surface-raised border border-border-subtle rounded-lg p-4">
            <div className="flex items-center gap-2 mb-3">
              <Server className="h-5 w-5 text-text-secondary" />
              <h3 className="font-medium text-text-primary">API Server</h3>
              <StatusBadge status={status.apiStatus?.status ?? 'unknown'} />
            </div>
            <div className="text-sm text-text-tertiary">
              Uptime: {status.apiStatus?.uptime ? formatUptime(status.apiStatus.uptime) : 'N/A'}
            </div>
          </div>
          <div className="bg-surface-raised border border-border-subtle rounded-lg p-4">
            <div className="flex items-center gap-2 mb-3">
              <HardDrive className="h-5 w-5 text-text-secondary" />
              <h3 className="font-medium text-text-primary">Database</h3>
              <StatusBadge status={status.databaseStatus?.status ?? 'unknown'} />
            </div>
            <div className="text-sm text-text-tertiary">
              Size: {status.databaseStatus?.databaseSizeBytes ? formatBytes(status.databaseStatus.databaseSizeBytes) : 'N/A'}
            </div>
          </div>
        </div>
      )}

      {/* Per-machine throughput */}
      {kpis && kpis.perMachineThroughput.length > 0 && (
        <div className="bg-surface-raised border border-border-subtle rounded-lg p-4">
          <h3 className="font-medium text-text-primary mb-3">Machine Throughput (5min)</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {kpis.perMachineThroughput.map(m => (
              <div key={m.hostname} className="bg-surface-sunken rounded-lg p-3">
                <p className="text-xs text-text-tertiary">{m.hostname}</p>
                <p className="text-lg font-semibold text-text-primary">{m.completed5Min} <span className="text-xs text-text-tertiary font-normal">jobs</span></p>
                <p className="text-xs text-text-tertiary">{(m.completed5Min / 5).toFixed(1)}/min</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Avg Duration */}
      {kpis && kpis.avgDuration.length > 0 && (
        <div className="bg-surface-raised border border-border-subtle rounded-lg p-4">
          <h3 className="font-medium text-text-primary mb-3">Avg Job Duration (15min)</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {kpis.avgDuration.map(d => (
              <div key={d.jobType} className="bg-surface-sunken rounded-lg p-3">
                <p className="text-xs text-text-tertiary">{d.jobType}</p>
                <p className="text-lg font-semibold text-text-primary">{formatDurationSec(d.avgSec)}</p>
                <p className="text-xs text-text-tertiary">min: {formatDurationSec(d.minSec)} / max: {formatDurationSec(d.maxSec)}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// --- Nodes Tab ---

function NodeCard({ node }: { node: NodeInfo }) {
  const [expanded, setExpanded] = useState(true);
  const queryClient = useQueryClient();

  const sendCommand = useMutation({
    mutationFn: ({ hostname, command }: { hostname: string; command: string }) =>
      pipelineApi.sendNodeCommand(hostname, command),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pipeline-nodes'] });
    },
  });

  const sendWorkerCmd = useMutation({
    mutationFn: ({ workerId, command }: { workerId: string; command: string }) =>
      pipelineApi.sendWorkerCommand(workerId, command),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pipeline-nodes'] });
    },
  });

  const throughput = node.workers.reduce((sum, w) => sum + w.activeJobs, 0);

  return (
    <div className="bg-surface-raised border border-border-subtle rounded-lg overflow-hidden">
      {/* Node header */}
      <div className="p-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button onClick={() => setExpanded(!expanded)} className="text-text-tertiary hover:text-text-primary">
            {expanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
          </button>
          <div className={cn('h-3 w-3 rounded-full', node.isOnline ? 'bg-green-400' : 'bg-red-400')} />
          <h3 className="font-semibold text-text-primary">{node.hostname}</h3>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => { if (confirm(`Restart all workers on ${node.hostname}?`)) sendCommand.mutate({ hostname: node.hostname, command: 'restart' }); }}
            className="p-1.5 rounded hover:bg-surface-overlay text-text-tertiary hover:text-amber-400 transition-colors"
            title="Restart all workers"
          >
            <RotateCcw className="h-4 w-4" />
          </button>
          <button
            onClick={() => { if (confirm(`Shutdown all workers on ${node.hostname}?`)) sendCommand.mutate({ hostname: node.hostname, command: 'shutdown' }); }}
            className="p-1.5 rounded hover:bg-surface-overlay text-text-tertiary hover:text-red-400 transition-colors"
            title="Shutdown all workers"
          >
            <Power className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Node summary bar */}
      <div className="px-4 pb-3 flex items-center gap-4 text-xs text-text-tertiary">
        <span>Code: <span className="text-text-secondary font-mono">{node.codeVersion?.substring(0, 8) ?? 'N/A'}</span></span>
        <span>Workers: <span className="text-text-secondary">{node.totalWorkers}</span></span>
        <span>Active Jobs: <span className="text-text-secondary">{throughput}</span></span>
      </div>

      {/* Worker rows */}
      {expanded && (
        <div className="border-t border-border-subtle divide-y divide-border-subtle">
          {node.workers.map(worker => (
            <div key={worker.workerId} className="px-4 py-2 flex items-center justify-between text-sm">
              <div className="flex items-center gap-3 min-w-0">
                <div className={cn(
                  'h-2 w-2 rounded-full flex-shrink-0',
                  worker.secondsSinceHeartbeat < 60 ? 'bg-green-400' : 'bg-red-400'
                )} />
                <span className="text-text-secondary font-mono text-xs truncate">{worker.workerId}</span>
                <StatusBadge status={worker.status} />
                <span className="text-text-tertiary text-xs">{worker.activeJobs} jobs</span>
                {worker.jobTypes.length > 0 && (
                  <span className="text-text-tertiary text-xs">{worker.jobTypes.join(', ')}</span>
                )}
              </div>
              <div className="flex items-center gap-2 flex-shrink-0">
                {worker.pendingCommand && (
                  <span className="text-xs text-amber-400 bg-amber-400/10 px-1.5 py-0.5 rounded">
                    cmd: {worker.pendingCommand}
                  </span>
                )}
                <span className="text-xs text-text-tertiary">{formatTimeAgo(worker.lastHeartbeat)}</span>
                <button
                  onClick={() => { if (confirm(`Shutdown worker ${worker.workerId}?`)) sendWorkerCmd.mutate({ workerId: worker.workerId, command: 'shutdown' }); }}
                  className="p-1 rounded hover:bg-surface-overlay text-text-tertiary hover:text-red-400 transition-colors"
                  title="Shutdown worker"
                >
                  <Square className="h-3 w-3" />
                </button>
              </div>
            </div>
          ))}
          {node.workers.length === 0 && (
            <div className="px-4 py-3 text-sm text-text-tertiary">No workers registered</div>
          )}
        </div>
      )}
    </div>
  );
}

function NodesTab({ nodes }: { nodes: NodeInfo[] | undefined }) {
  if (!nodes || nodes.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-48 text-text-tertiary">
        <Server className="h-8 w-8 mb-2" />
        <p>No nodes registered</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {nodes.map(node => (
        <NodeCard key={node.hostname} node={node} />
      ))}
    </div>
  );
}

// --- Job Queues Tab ---

function JobQueuesTab({ jobs, kpis }: { jobs: JobsResponse | undefined; kpis: PipelineKpis | undefined }) {
  const queryClient = useQueryClient();
  const [sortCol, setSortCol] = useState<SortCol>('jobType');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc');
  const [filter, setFilter] = useState('');

  const handleSort = (col: SortCol) => {
    if (sortCol === col) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    else { setSortCol(col); setSortDir('asc'); }
  };

  const pauseMutation = useMutation({
    mutationFn: (jobType: string) => pipelineApi.pauseJobType(jobType),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['pipeline-jobs'] }),
  });
  const resumeMutation = useMutation({
    mutationFn: (jobType: string) => pipelineApi.resumeJobType(jobType),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['pipeline-jobs'] }),
  });
  const stopMutation = useMutation({
    mutationFn: (jobType: string) => pipelineApi.stopJobType(jobType),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['pipeline-jobs'] }),
  });
  const deleteMutation = useMutation({
    mutationFn: (jobType: string) => pipelineApi.clearStoppedJobs(jobType),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['pipeline-jobs'] }),
  });
  const retryMutation = useMutation({
    mutationFn: (jobType: string) => pipelineApi.retryFailedJobs(jobType),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['pipeline-jobs'] }),
  });

  const sortedRows = useMemo(() => {
    if (!jobs?.summary) return [];
    let rows = [...jobs.summary];
    if (filter) rows = rows.filter(r => r.jobType.toLowerCase().includes(filter.toLowerCase()));
    return rows.sort((a, b) => {
      const etaVal = (r: JobQueueSummary) => kpis?.queueEta.find(e => e.jobType === r.jobType)?.etaMinutes ?? Infinity;
      const rateVal = (r: JobQueueSummary) => r.completed5Min / 5;
      let cmp = 0;
      switch (sortCol) {
        case 'jobType':   cmp = a.jobType.localeCompare(b.jobType); break;
        case 'pending':   cmp = a.pending - b.pending; break;
        case 'paused':    cmp = (a.paused ?? 0) - (b.paused ?? 0); break;
        case 'stopped':   cmp = (a.stopped ?? 0) - (b.stopped ?? 0); break;
        case 'running':   cmp = (a.running + a.claimed) - (b.running + b.claimed); break;
        case 'completed': cmp = a.completed - b.completed; break;
        case 'failed':    cmp = a.failed - b.failed; break;
        case 'total':     cmp = a.total - b.total; break;
        case 'rate':      cmp = rateVal(a) - rateVal(b); break;
        case 'eta':       cmp = etaVal(a) - etaVal(b); break;
        case 'pct':       cmp = a.pctComplete - b.pctComplete; break;
      }
      return sortDir === 'asc' ? cmp : -cmp;
    });
  }, [jobs?.summary, filter, sortCol, sortDir, kpis]);

  if (!jobs || jobs.summary.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-48 text-text-tertiary">
        <Database className="h-8 w-8 mb-2" />
        <p>No job queues found</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Filter bar */}
      <div className="flex items-center gap-3">
        <div className="relative max-w-xs w-full">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-text-tertiary pointer-events-none" />
          <input
            type="text"
            placeholder="Filter job types…"
            value={filter}
            onChange={e => setFilter(e.target.value)}
            className="w-full pl-9 pr-3 py-2 text-sm bg-surface-raised border border-border-subtle rounded-lg text-text-primary placeholder:text-text-tertiary focus:outline-none focus:border-accent-blue"
          />
        </div>
        {filter && (
          <span className="text-xs text-text-tertiary">
            {sortedRows.length} of {jobs.summary.length} types
          </span>
        )}
      </div>

      {/* Table */}
      <div className="bg-surface-raised border border-border-subtle rounded-lg overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border-subtle">
                <SortHeader col="jobType"   label="Job Type"  current={sortCol} dir={sortDir} onSort={handleSort} align="left" />
                <SortHeader col="pending"   label="Pending"   current={sortCol} dir={sortDir} onSort={handleSort} />
                <SortHeader col="paused"    label="Paused"    current={sortCol} dir={sortDir} onSort={handleSort} />
                <SortHeader col="stopped"   label="Stopped"   current={sortCol} dir={sortDir} onSort={handleSort} />
                <SortHeader col="running"   label="Running"   current={sortCol} dir={sortDir} onSort={handleSort} />
                <SortHeader col="completed" label="Completed" current={sortCol} dir={sortDir} onSort={handleSort} />
                <SortHeader col="failed"    label="Failed"    current={sortCol} dir={sortDir} onSort={handleSort} />
                <SortHeader col="total"     label="Total"     current={sortCol} dir={sortDir} onSort={handleSort} />
                <SortHeader col="rate"      label="Rate/min"  current={sortCol} dir={sortDir} onSort={handleSort} />
                <SortHeader col="eta"       label="ETA"       current={sortCol} dir={sortDir} onSort={handleSort} />
                <SortHeader col="pct"       label="Progress"  current={sortCol} dir={sortDir} onSort={handleSort} />
                <th className="px-4 py-3 text-text-tertiary font-medium text-center whitespace-nowrap">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border-subtle">
              {sortedRows.map(row => {
                const eta = kpis?.queueEta.find(e => e.jobType === row.jobType);
                const rate = row.completed5Min > 0 ? (row.completed5Min / 5).toFixed(1) : '0';
                const hasPending = row.pending > 0;
                const hasPaused  = (row.paused  ?? 0) > 0;
                const hasStopped = (row.stopped ?? 0) > 0;
                const hasFailed  = row.failed > 0;
                const isActive   = hasPending || row.running > 0 || row.claimed > 0;
                const canStop    = isActive || hasPaused;
                const canDelete  = hasStopped || hasPaused;

                return (
                  <tr key={row.jobType} className="hover:bg-surface-overlay/50">
                    <td className="px-4 py-3 text-text-primary font-mono">{row.jobType}</td>
                    <td className="px-4 py-3 text-right text-text-secondary">{row.pending.toLocaleString()}</td>
                    <td className="px-4 py-3 text-right">
                      {hasPaused
                        ? <span className="text-amber-400 font-medium">{(row.paused ?? 0).toLocaleString()}</span>
                        : <span className="text-text-tertiary">—</span>}
                    </td>
                    <td className="px-4 py-3 text-right">
                      {hasStopped
                        ? <span className="text-red-400 font-medium">{(row.stopped ?? 0).toLocaleString()}</span>
                        : <span className="text-text-tertiary">—</span>}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <span className={row.running + row.claimed > 0 ? 'text-amber-400' : 'text-text-secondary'}>
                        {(row.running + row.claimed).toLocaleString()}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right text-green-400">{row.completed.toLocaleString()}</td>
                    <td className="px-4 py-3 text-right">
                      <span className={row.failed > 0 ? 'text-red-400' : 'text-text-secondary'}>
                        {row.failed.toLocaleString()}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right text-text-tertiary">{row.total.toLocaleString()}</td>
                    <td className="px-4 py-3 text-right text-text-secondary">{rate}</td>
                    <td className="px-4 py-3 text-right text-text-secondary">{formatEta(eta?.etaMinutes ?? null)}</td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <ProgressBar percent={row.pctComplete} className="flex-1 min-w-[4rem]" />
                        <span className="text-xs text-text-tertiary w-12 text-right">{row.pctComplete.toFixed(1)}%</span>
                      </div>
                    </td>

                    {/* Actions */}
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-center gap-1">
                        {/* Pause / Resume toggle */}
                        {hasPaused ? (
                          <button
                            onClick={() => resumeMutation.mutate(row.jobType)}
                            disabled={resumeMutation.isPending}
                            className="p-1.5 rounded hover:bg-surface-overlay text-amber-400 hover:text-amber-300 transition-colors"
                            title="Resume paused jobs"
                          >
                            <Play className="h-3.5 w-3.5" />
                          </button>
                        ) : (
                          <button
                            onClick={() => { if (hasPending) pauseMutation.mutate(row.jobType); }}
                            disabled={!hasPending || pauseMutation.isPending}
                            className={cn(
                              'p-1.5 rounded transition-colors',
                              hasPending
                                ? 'hover:bg-surface-overlay text-text-tertiary hover:text-amber-400'
                                : 'text-text-disabled opacity-30 cursor-not-allowed',
                            )}
                            title="Pause pending jobs"
                          >
                            <Pause className="h-3.5 w-3.5" />
                          </button>
                        )}

                        {/* Stop */}
                        <button
                          onClick={() => {
                            if (canStop && confirm(`Stop all pending/running jobs for "${row.jobType}"?`))
                              stopMutation.mutate(row.jobType);
                          }}
                          disabled={!canStop || stopMutation.isPending}
                          className={cn(
                            'p-1.5 rounded transition-colors',
                            canStop
                              ? 'hover:bg-surface-overlay text-text-tertiary hover:text-red-400'
                              : 'text-text-disabled opacity-30 cursor-not-allowed',
                          )}
                          title="Stop all pending/running jobs"
                        >
                          <Square className="h-3.5 w-3.5" />
                        </button>

                        {/* Delete stopped */}
                        <button
                          onClick={() => {
                            if (canDelete && confirm(`Permanently delete all stopped/paused jobs for "${row.jobType}"?`))
                              deleteMutation.mutate(row.jobType);
                          }}
                          disabled={!canDelete || deleteMutation.isPending}
                          className={cn(
                            'p-1.5 rounded transition-colors',
                            canDelete
                              ? 'hover:bg-surface-overlay text-text-tertiary hover:text-red-400'
                              : 'text-text-disabled opacity-30 cursor-not-allowed',
                          )}
                          title="Delete stopped/paused jobs"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>

                        {/* Retry failed */}
                        <button
                          onClick={() => {
                            if (hasFailed && confirm(`Retry all ${row.failed.toLocaleString()} failed jobs for "${row.jobType}"?`))
                              retryMutation.mutate(row.jobType);
                          }}
                          disabled={!hasFailed || retryMutation.isPending}
                          className={cn(
                            'p-1.5 rounded transition-colors',
                            hasFailed
                              ? 'hover:bg-surface-overlay text-text-tertiary hover:text-green-400'
                              : 'text-text-disabled opacity-30 cursor-not-allowed',
                          )}
                          title="Retry all failed jobs"
                        >
                          <RotateCcw className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

// --- Errors Tab ---

function ErrorsTab({ errors }: { errors: JobError[] | undefined }) {
  if (!errors || errors.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-48 text-text-tertiary">
        <CheckCircle className="h-8 w-8 mb-2" />
        <p>No recent errors</p>
      </div>
    );
  }

  return (
    <div className="bg-surface-raised border border-border-subtle rounded-lg overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border-subtle text-left">
              <th className="px-4 py-3 text-text-tertiary font-medium">Job ID</th>
              <th className="px-4 py-3 text-text-tertiary font-medium">Type</th>
              <th className="px-4 py-3 text-text-tertiary font-medium">Error</th>
              <th className="px-4 py-3 text-text-tertiary font-medium">Worker</th>
              <th className="px-4 py-3 text-text-tertiary font-medium">Time</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border-subtle">
            {errors.map(err => (
              <tr key={err.jobId} className="hover:bg-surface-overlay/50">
                <td className="px-4 py-3 text-text-secondary font-mono text-xs">{err.jobId}</td>
                <td className="px-4 py-3 text-text-secondary font-mono text-xs">{err.jobType}</td>
                <td className="px-4 py-3 text-red-400 text-xs max-w-md">
                  <span className="line-clamp-2" title={err.errorMessage}>{err.errorMessage}</span>
                </td>
                <td className="px-4 py-3 text-text-tertiary text-xs font-mono">{err.claimedBy ?? '--'}</td>
                <td className="px-4 py-3 text-text-tertiary text-xs whitespace-nowrap">{formatTimeAgo(err.completedAt)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// --- Launch Tab ---

// All pipeline steps in chronological order
const PIPELINE_STEPS: Array<{
  step: number;
  id: string;
  enabled: boolean;
  title: string;
  description: string;
  actionLabel?: string;
  hint?: string;
  prompt?: string;
}> = [
  {
    step: 1,
    id: 'download',
    enabled: false,
    title: 'Download DOJ Files to Cloudflare R2',
    description: 'Fetch the raw PDF and media files from the DOJ public catalog and upload them to Cloudflare R2 for distributed access by workers.',
    hint: 'A standalone downloader exists but is not integrated into the job pool.',
    prompt: `Integrate DOJ file downloading into the Epstein job pool system.

Create a \`download_r2\` job handler in \`epstein_extraction/services/job_handlers/\` that:
1. Reads a document_id + download_url from the job payload
2. Downloads the PDF/media file from the DOJ URL
3. Uploads it to Cloudflare R2 under the appropriate DataSet_N/EFTA key
4. Updates \`documents.r2_key\` and \`documents.download_status='completed'\`
5. Registers in \`__init__.py\`

Add \`submit_download_jobs.py\` that inserts \`download_r2\` jobs for documents where:
- \`r2_key IS NULL\` AND \`download_url IS NOT NULL\`

Reference \`extraction_handler.py\` for the R2 boto3 pattern and \`submit_extraction_jobs.py\` for the submission pattern.`,
  },
  {
    step: 2,
    id: 'extract',
    enabled: true,
    title: 'Submit Text Extraction Jobs',
    description: 'Queue extract_text jobs for all pending documents that have an R2 key. Workers will download each PDF from R2 and extract text using PyMuPDF and pdfplumber.',
    actionLabel: 'Submit Jobs',
  },
  {
    step: 3,
    id: 'workers',
    enabled: true,
    title: 'Start Extraction Workers',
    description: 'Launch the auto-scaling extraction worker process on this machine. It spins up workers based on available CPU/memory and claims extract_text jobs from the queue.',
    actionLabel: 'Start Workers',
  },
  {
    step: 4,
    id: 'ocr',
    enabled: false,
    title: 'OCR Processing (Scanned PDFs)',
    description: 'Extract text from scanned PDFs using Tesseract OCR — for documents where PyMuPDF returned empty or minimal text.',
    hint: 'ocr_all_documents.py exists but is not integrated into the job pool system.',
    prompt: `Integrate OCR processing into the Epstein job pipeline.

Create an \`ocr_extract\` job handler in \`epstein_extraction/services/job_handlers/\` that:
1. Downloads a PDF from Cloudflare R2 using the document's r2_key
2. Runs Tesseract OCR on each page using pytesseract
3. Saves the combined text to \`documents.full_text\` and sets \`extraction_status='completed'\`
4. Registers in \`__init__.py\` alongside extract_text and chunk_embed

Then add \`submit_ocr_jobs.py\` that inserts \`ocr_extract\` jobs for documents where:
- full_text IS NULL (or LENGTH < 50) AND r2_key IS NOT NULL AND extraction_status = 'completed'
  (i.e., the regular extractor already ran but returned no text — likely scanned)

Follow the patterns in \`extraction_handler.py\` and \`submit_extraction_jobs.py\`.`,
  },
  {
    step: 5,
    id: 'embed',
    enabled: true,
    title: 'Start Embedding Server',
    description: 'Launch the local sentence-transformer HTTP server on port 5050. This must be running before chunk_embed workers can generate vector embeddings.',
    actionLabel: 'Start Server',
  },
  {
    step: 6,
    id: 'chunk',
    enabled: true,
    title: 'Submit Chunk & Embed Jobs',
    description: 'Queue chunk_embed jobs for documents that have text but no vector embeddings. Workers split text into chunks and call the embedding server.',
    actionLabel: 'Submit Jobs',
  },
  {
    step: 7,
    id: 'ner',
    enabled: false,
    title: 'Named Entity Recognition',
    description: 'Extract people, organizations, and locations from document text using NLP.',
    hint: 'ner_processor.py exists but is not integrated into the job pool.',
    prompt: `Integrate Named Entity Recognition into the Epstein job pipeline.

Create a \`ner_extract\` job handler in \`epstein_extraction/services/job_handlers/\` that:
1. Reads \`documents.full_text\` for the given document_id
2. Runs spaCy NER (en_core_web_lg) or calls Claude API to extract entities
3. Saves to a \`document_entities\` table:
   (id, document_id, entity_text, entity_type, start_char, end_char, confidence)
4. Registers in \`__init__.py\`

Add \`submit_ner_jobs.py\` targeting documents with full_text but no rows in document_entities.
Follow the patterns in \`chunk_embed_handler.py\` and \`submit_chunk_embed_jobs.py\`.`,
  },
  {
    step: 8,
    id: 'financial',
    enabled: false,
    title: 'Financial Data Extraction',
    description: 'Extract transactions, wire transfers, account numbers, and dollar amounts using AI.',
    hint: 'extract_financials.py exists but is not integrated into the job pool.',
    prompt: `Integrate financial data extraction into the Epstein job pipeline.

Create a \`financial_extract\` job handler in \`epstein_extraction/services/job_handlers/\` that:
1. Reads \`documents.full_text\` for the given document_id
2. Calls Claude API (claude-sonnet-4-6) with a structured prompt to extract:
   - Dollar amounts, dates, account numbers, wire transfers, payers, recipients
3. Saves results to a \`document_financials\` table:
   (id, document_id, amount_usd, transaction_date, account_number, payer, recipient, description, raw_json)
4. Registers in \`__init__.py\`

Add \`submit_financial_jobs.py\` targeting documents with full_text but no rows in document_financials.
Reference the \`chunk_embed_handler.py\` pattern.`,
  },
  {
    step: 9,
    id: 'vision',
    enabled: false,
    title: 'Vision Analysis',
    description: 'Analyze document images and photos using AI vision models to generate descriptions.',
    hint: 'run_vision_analysis.py exists but is not integrated into the job pool.',
    prompt: `Integrate vision analysis into the Epstein job pipeline.

Create a \`vision_analyze\` job handler in \`epstein_extraction/services/job_handlers/\` that:
1. Downloads images or PDF pages from Cloudflare R2
2. Sends them to Claude claude-haiku-4-5-20251001 (Anthropic API) for description
3. Saves image descriptions to a new \`document_image_descriptions\` table
   (columns: id, document_id, page_number, description, analyzed_at)
4. Registers in \`__init__.py\`

Add \`submit_vision_jobs.py\` following the pattern of \`submit_extraction_jobs.py\`.
Documents to target: those with r2_key but no rows in document_image_descriptions.`,
  },
];

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      onClick={async () => {
        await navigator.clipboard.writeText(text);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      }}
      className="flex items-center gap-1.5 px-2 py-1 text-xs bg-surface-overlay border border-border-subtle rounded hover:bg-surface-raised transition-colors text-text-tertiary hover:text-text-secondary"
    >
      {copied ? <CheckCircle className="h-3 w-3 text-green-400" /> : <FileText className="h-3 w-3" />}
      {copied ? 'Copied!' : 'Copy prompt'}
    </button>
  );
}

function LaunchTab() {
  const queryClient = useQueryClient();
  const [results, setResults] = useState<Record<string, { ok: boolean; msg: string }>>({});

  const { data: launchStatus } = useQuery({
    queryKey: ['pipeline-launch-status'],
    queryFn: pipelineApi.getLaunchStatus,
  });

  function makeOnSuccess(id: string) {
    return (data: LaunchResult) => {
      setResults(prev => ({ ...prev, [id]: { ok: data.success, msg: data.message } }));
      queryClient.invalidateQueries({ queryKey: ['pipeline-jobs'] });
    };
  }
  function makeOnError(id: string) {
    return (err: Error) => {
      setResults(prev => ({ ...prev, [id]: { ok: false, msg: err.message } }));
    };
  }

  const submitExtractMutation = useMutation({
    mutationFn: pipelineApi.submitExtractText,
    onSuccess: makeOnSuccess('extract'),
    onError: makeOnError('extract'),
  });
  const submitChunkMutation = useMutation({
    mutationFn: pipelineApi.submitChunkEmbed,
    onSuccess: makeOnSuccess('chunk'),
    onError: makeOnError('chunk'),
  });
  const startWorkersMutation = useMutation({
    mutationFn: pipelineApi.startWorkers,
    onSuccess: makeOnSuccess('workers'),
    onError: makeOnError('workers'),
  });
  const startEmbedMutation = useMutation({
    mutationFn: pipelineApi.startEmbeddingServer,
    onSuccess: makeOnSuccess('embed'),
    onError: makeOnError('embed'),
  });

  // Map step ID → mutation for enabled steps
  const mutationMap: Record<string, ReturnType<typeof useMutation<LaunchResult, Error, void>>> = {
    extract: submitExtractMutation,
    workers: startWorkersMutation,
    embed: startEmbedMutation,
    chunk: submitChunkMutation,
  };

  const scriptKeyMap: Record<string, string> = {
    extract: 'submitExtractText',
    workers: 'startWorkers',
    embed: 'startEmbeddingServer',
    chunk: 'submitChunkEmbed',
  };

  const isLastStep = (i: number) => i === PIPELINE_STEPS.length - 1;

  return (
    <div className="max-w-2xl">
      <p className="text-sm text-text-tertiary mb-6">
        Pipeline steps in chronological order. Click actions to queue jobs or start processes.
        Grayed steps need to be built first — use the copy button to get a Claude prompt.
      </p>

      <div className="relative">
        {PIPELINE_STEPS.map((step, i) => {
          const result = results[step.id];
          const mutation = step.enabled ? mutationMap[step.id] : undefined;
          const isPending = mutation?.isPending ?? false;
          const scriptAvailable = !step.enabled
            ? false
            : (launchStatus?.scripts[scriptKeyMap[step.id]] ?? true);

          return (
            <div key={step.id} className="flex gap-4">
              {/* Step indicator column */}
              <div className="flex flex-col items-center">
                <div className={cn(
                  'w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold shrink-0 z-10',
                  step.enabled
                    ? 'bg-accent-blue text-white'
                    : 'bg-surface-overlay border border-border-subtle text-text-tertiary',
                )}>
                  {step.step}
                </div>
                {!isLastStep(i) && (
                  <div className={cn(
                    'w-px flex-1 my-1 min-h-[1rem]',
                    step.enabled ? 'bg-accent-blue/30' : 'bg-border-subtle',
                  )} />
                )}
              </div>

              {/* Card */}
              <div className={cn(
                'flex-1 bg-surface-raised border border-border-subtle rounded-lg p-4 flex flex-col gap-2.5',
                isLastStep(i) ? 'mb-0' : 'mb-3',
                !step.enabled && 'opacity-70',
              )}>
                <div>
                  <h3 className={cn(
                    'font-medium text-sm',
                    step.enabled ? 'text-text-primary' : 'text-text-secondary',
                  )}>
                    {step.title}
                  </h3>
                  <p className="text-xs text-text-tertiary mt-0.5">{step.description}</p>
                </div>

                {/* Result banner */}
                {result && (
                  <div className={cn(
                    'flex items-start gap-2 px-3 py-1.5 rounded text-xs',
                    result.ok ? 'bg-green-400/10 text-green-400' : 'bg-red-400/10 text-red-400',
                  )}>
                    {result.ok
                      ? <CheckCircle className="h-3.5 w-3.5 shrink-0 mt-0.5" />
                      : <XCircle className="h-3.5 w-3.5 shrink-0 mt-0.5" />}
                    {result.msg}
                  </div>
                )}

                {/* Disabled hint */}
                {!step.enabled && step.hint && (
                  <div className="flex items-start gap-2 px-3 py-1.5 bg-amber-400/5 border border-amber-400/20 rounded text-xs">
                    <AlertTriangle className="h-3.5 w-3.5 text-amber-400 shrink-0 mt-0.5" />
                    <div className="flex-1 min-w-0">
                      <span className="text-amber-400/80">{step.hint}</span>
                      <div className="mt-1.5 flex items-center gap-2">
                        <span className="text-text-tertiary">Build with Claude:</span>
                        <CopyButton text={step.prompt!} />
                      </div>
                    </div>
                  </div>
                )}

                {/* Action button */}
                {step.enabled ? (
                  <button
                    onClick={() => mutation?.mutate()}
                    disabled={isPending || !scriptAvailable}
                    className={cn(
                      'self-start flex items-center gap-2 px-3 py-1.5 text-xs font-medium rounded-lg transition-colors',
                      'bg-accent-blue/10 text-accent-blue border border-accent-blue/30',
                      'hover:bg-accent-blue/20 disabled:opacity-50 disabled:cursor-not-allowed',
                    )}
                  >
                    {isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
                    {isPending ? 'Running…' : step.actionLabel}
                  </button>
                ) : (
                  <button
                    disabled
                    className="self-start flex items-center gap-2 px-3 py-1.5 text-xs font-medium rounded-lg bg-surface-overlay text-text-disabled cursor-not-allowed border border-border-subtle"
                  >
                    <Clock className="h-3.5 w-3.5" />
                    Not built yet
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// --- Main Page ---

export function PipelinePage() {
  const [activeTab, setActiveTab] = useState<TabKey>('overview');

  const { data: status, isLoading: statusLoading, refetch: refetchStatus } = useQuery({
    queryKey: ['pipeline-status'],
    queryFn: pipelineApi.getStatus,
    refetchInterval: 5000,
  });

  const { data: nodes, refetch: refetchNodes } = useQuery({
    queryKey: ['pipeline-nodes'],
    queryFn: pipelineApi.getNodes,
    refetchInterval: 5000,
  });

  const { data: jobs, refetch: refetchJobs } = useQuery({
    queryKey: ['pipeline-jobs'],
    queryFn: pipelineApi.getJobs,
    refetchInterval: 5000,
  });

  const { data: kpis, refetch: refetchKpis } = useQuery({
    queryKey: ['pipeline-kpis'],
    queryFn: pipelineApi.getKpis,
    refetchInterval: 5000,
  });

  const { data: throughputHistory, refetch: refetchThroughput } = useQuery({
    queryKey: ['pipeline-throughput-history'],
    queryFn: () => pipelineApi.getThroughputHistory(30, 60),
    refetchInterval: 10000,
  });

  const refetchAll = () => {
    refetchStatus();
    refetchNodes();
    refetchJobs();
    refetchKpis();
    refetchThroughput();
  };

  const errorCount = jobs?.errors.length ?? 0;

  if (statusLoading) {
    return (
      <div className="flex items-center justify-center h-96">
        <Loader2 className="h-8 w-8 animate-spin text-accent-blue" />
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-text-primary">Pipeline Dashboard</h1>
          <p className="text-sm text-text-tertiary mt-1">
            Monitor distributed workloads, nodes, and job queues
          </p>
        </div>
        <button
          onClick={refetchAll}
          className="flex items-center gap-2 px-3 py-2 text-sm bg-surface-raised border border-border-subtle rounded-lg hover:bg-surface-overlay transition-colors"
        >
          <RefreshCw className="h-4 w-4" />
          Refresh
        </button>
      </div>

      {/* Tab Navigation */}
      <div className="flex items-center gap-1 border-b border-border-subtle">
        {tabs.map(tab => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={cn(
                'flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors -mb-px',
                activeTab === tab.key
                  ? 'border-accent-blue text-accent-blue'
                  : 'border-transparent text-text-tertiary hover:text-text-secondary hover:border-border-subtle'
              )}
            >
              <Icon className="h-4 w-4" />
              {tab.label}
              {tab.key === 'errors' && errorCount > 0 && (
                <span className="ml-1 px-1.5 py-0.5 bg-red-400/10 text-red-400 rounded-full text-xs">{errorCount}</span>
              )}
            </button>
          );
        })}
      </div>

      {/* Tab Content */}
      {activeTab === 'overview' && (
        <OverviewTab status={status} kpis={kpis} jobs={jobs} nodes={nodes} throughputHistory={throughputHistory} />
      )}
      {activeTab === 'nodes' && (
        <NodesTab nodes={nodes} />
      )}
      {activeTab === 'jobs' && (
        <JobQueuesTab jobs={jobs} kpis={kpis} />
      )}
      {activeTab === 'errors' && (
        <ErrorsTab errors={jobs?.errors} />
      )}
      {activeTab === 'launch' && (
        <LaunchTab />
      )}
    </div>
  );
}
