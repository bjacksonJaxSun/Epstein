import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Database,
  FileText,
  Image,
  Eye,
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
} from 'lucide-react';
import { apiGet, apiPost } from '@/api/client';
import { cn } from '@/lib/utils';

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

// --- API ---

const pipelineApi = {
  getStatus: () => apiGet<PipelineStatus>('/pipeline/status'),
  getNodes: () => apiGet<NodeInfo[]>('/pipeline/nodes'),
  getJobs: () => apiGet<JobsResponse>('/pipeline/jobs'),
  getKpis: () => apiGet<PipelineKpis>('/pipeline/kpis'),
  sendNodeCommand: (hostname: string, command: string) =>
    apiPost<{ success: boolean; message: string }>(`/pipeline/nodes/${encodeURIComponent(hostname)}/command`, { command }),
  sendWorkerCommand: (workerId: string, command: string) =>
    apiPost<{ success: boolean; message: string }>(`/pipeline/workers/${encodeURIComponent(workerId)}/command`, { command }),
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

// --- Tab Navigation ---

type TabKey = 'overview' | 'nodes' | 'jobs' | 'errors';

const tabs: { key: TabKey; label: string; icon: typeof Activity }[] = [
  { key: 'overview', label: 'Overview', icon: Activity },
  { key: 'nodes', label: 'Nodes', icon: Server },
  { key: 'jobs', label: 'Job Queues', icon: Database },
  { key: 'errors', label: 'Errors', icon: AlertTriangle },
];

// --- Overview Tab ---

function OverviewTab({ status, kpis, jobs, nodes }: {
  status: PipelineStatus | undefined;
  kpis: PipelineKpis | undefined;
  jobs: JobsResponse | undefined;
  nodes: NodeInfo[] | undefined;
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
      <div className="bg-surface-raised border border-border-subtle rounded-lg overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border-subtle text-left">
                <th className="px-4 py-3 text-text-tertiary font-medium">Job Type</th>
                <th className="px-4 py-3 text-text-tertiary font-medium text-right">Pending</th>
                <th className="px-4 py-3 text-text-tertiary font-medium text-right">Running</th>
                <th className="px-4 py-3 text-text-tertiary font-medium text-right">Completed</th>
                <th className="px-4 py-3 text-text-tertiary font-medium text-right">Failed</th>
                <th className="px-4 py-3 text-text-tertiary font-medium text-right">Total</th>
                <th className="px-4 py-3 text-text-tertiary font-medium text-right">Rate/min</th>
                <th className="px-4 py-3 text-text-tertiary font-medium text-right">ETA</th>
                <th className="px-4 py-3 text-text-tertiary font-medium w-40">Progress</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border-subtle">
              {jobs.summary.map(row => {
                const eta = kpis?.queueEta.find(e => e.jobType === row.jobType);
                const rate = row.completed5Min > 0 ? (row.completed5Min / 5).toFixed(1) : '0';
                return (
                  <tr key={row.jobType} className="hover:bg-surface-overlay/50">
                    <td className="px-4 py-3 text-text-primary font-mono">{row.jobType}</td>
                    <td className="px-4 py-3 text-right text-text-secondary">{row.pending.toLocaleString()}</td>
                    <td className="px-4 py-3 text-right">
                      <span className={row.running > 0 ? 'text-amber-400' : 'text-text-secondary'}>
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
                        <ProgressBar percent={row.pctComplete} className="flex-1" />
                        <span className="text-xs text-text-tertiary w-12 text-right">{row.pctComplete.toFixed(1)}%</span>
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

  const refetchAll = () => {
    refetchStatus();
    refetchNodes();
    refetchJobs();
    refetchKpis();
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
        <OverviewTab status={status} kpis={kpis} jobs={jobs} nodes={nodes} />
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
    </div>
  );
}
