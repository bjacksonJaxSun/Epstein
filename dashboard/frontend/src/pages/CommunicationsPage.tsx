import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  MessageSquare,
  Mail,
  Phone,
  FileText,
  Search,
  ChevronLeft,
  ChevronRight,
  AlertCircle,
  X,
  Paperclip,
  ArrowRight,
} from 'lucide-react';
import { format } from 'date-fns';
import { communicationsApi } from '@/api/endpoints/communications';
import type { Communication } from '@/api/endpoints/communications';
import { LoadingSpinner, ConfidenceBadge } from '@/components/shared';
import { cn } from '@/lib/utils';

const COMM_TYPES = [
  { key: 'all', label: 'All Types' },
  { key: 'email', label: 'Email' },
  { key: 'letter', label: 'Letter' },
  { key: 'phone', label: 'Phone' },
];

function getCommIcon(type: string) {
  switch (type.toLowerCase()) {
    case 'email': return Mail;
    case 'phone': return Phone;
    default: return FileText;
  }
}

function formatDate(dateStr: string | undefined): string {
  if (!dateStr) return '--';
  try {
    return format(new Date(dateStr), 'MMM d, yyyy');
  } catch {
    return dateStr;
  }
}

function formatDateTime(dateStr: string | undefined, timeStr: string | undefined): string {
  if (!dateStr) return '--';
  try {
    const base = format(new Date(dateStr), 'MMM d, yyyy');
    return timeStr ? `${base} at ${timeStr}` : base;
  } catch {
    return dateStr;
  }
}

export function CommunicationsPage() {
  const [commType, setCommType] = useState('all');
  const [search, setSearch] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [page, setPage] = useState(1);
  const [selectedComm, setSelectedComm] = useState<Communication | null>(null);

  const { data, isLoading, isError } = useQuery({
    queryKey: ['communications', page, commType, search, dateFrom, dateTo],
    queryFn: () =>
      communicationsApi.list({
        page,
        pageSize: 20,
        communicationType: commType !== 'all' ? commType : undefined,
        search: search || undefined,
        dateFrom: dateFrom || undefined,
        dateTo: dateTo || undefined,
      }),
  });

  const items = data?.items ?? [];
  const pagination = data;

  function handleSearch(value: string) {
    setSearch(value);
    setPage(1);
  }

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div>
        <h2 className="text-xl font-semibold text-text-primary">Communications</h2>
        <p className="mt-1 text-sm text-text-secondary">
          Emails, phone calls, and other communications extracted from documents.
        </p>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-4">
        {/* Type Filter */}
        <div className="flex items-center rounded-lg border border-border-subtle bg-surface-raised p-0.5">
          {COMM_TYPES.map(({ key, label }) => {
            const Icon = key === 'all' ? MessageSquare : getCommIcon(key);
            return (
              <button
                key={key}
                type="button"
                onClick={() => { setCommType(key); setPage(1); }}
                className={cn(
                  'flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors',
                  commType === key
                    ? 'bg-accent-blue/15 text-accent-blue'
                    : 'text-text-secondary hover:bg-surface-overlay hover:text-text-primary'
                )}
              >
                <Icon className="h-3.5 w-3.5" />
                {label}
              </button>
            );
          })}
        </div>

        {/* Date Range */}
        <div className="flex items-center gap-1.5">
          <input
            type="date"
            value={dateFrom}
            onChange={(e) => { setDateFrom(e.target.value); setPage(1); }}
            className="rounded-md border border-border-subtle bg-surface-raised px-2 py-1.5 text-xs text-text-primary focus:border-accent-blue focus:outline-none [color-scheme:dark]"
          />
          <span className="text-xs text-text-tertiary">to</span>
          <input
            type="date"
            value={dateTo}
            onChange={(e) => { setDateTo(e.target.value); setPage(1); }}
            className="rounded-md border border-border-subtle bg-surface-raised px-2 py-1.5 text-xs text-text-primary focus:border-accent-blue focus:outline-none [color-scheme:dark]"
          />
        </div>

        {/* Sender/Recipient Search */}
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-text-tertiary" />
          <input
            type="text"
            value={search}
            onChange={(e) => handleSearch(e.target.value)}
            placeholder="Search sender, recipient, subject..."
            className="w-full rounded-md border border-border-subtle bg-surface-raised py-1.5 pl-9 pr-8 text-xs text-text-primary placeholder:text-text-disabled focus:border-accent-blue focus:outline-none"
          />
          {search && (
            <button
              type="button"
              onClick={() => handleSearch('')}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-text-tertiary hover:text-text-primary"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* Content */}
      <div className="flex gap-4">
        {/* Communication List */}
        <div className={cn('flex flex-col gap-2', selectedComm ? 'w-[60%]' : 'w-full')}>
          {isLoading && <LoadingSpinner className="py-24" />}

          {isError && (
            <div className="flex flex-col items-center justify-center gap-3 rounded-lg border border-accent-red/30 bg-accent-red/5 py-12">
              <AlertCircle className="h-8 w-8 text-accent-red" />
              <p className="text-sm text-accent-red">Failed to load communications.</p>
            </div>
          )}

          {!isLoading && !isError && items.length === 0 && (
            <div className="flex flex-col items-center justify-center gap-3 rounded-lg border border-border-subtle bg-surface-raised py-16">
              <MessageSquare className="h-10 w-10 text-text-disabled" />
              <p className="text-sm text-text-disabled">No communications found.</p>
            </div>
          )}

          {!isLoading && !isError && items.length > 0 && (
            items.map((comm) => (
              <CommCard
                key={comm.communicationId}
                comm={comm}
                isSelected={selectedComm?.communicationId === comm.communicationId}
                onSelect={() => setSelectedComm(comm)}
              />
            ))
          )}
        </div>

        {/* Detail Panel */}
        {selectedComm && (
          <CommDetailPanel
            comm={selectedComm}
            onClose={() => setSelectedComm(null)}
          />
        )}
      </div>

      {/* Pagination */}
      {pagination && pagination.totalPages > 1 && (
        <div className="flex items-center justify-between rounded-lg border border-border-subtle bg-surface-raised p-3">
          <span className="text-xs text-text-tertiary">
            Page {page} of {pagination.totalPages}
            {' '}({pagination.totalCount.toLocaleString()} total)
          </span>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
              className="flex items-center gap-1 rounded-md border border-border-subtle px-2.5 py-1 text-xs text-text-secondary transition-colors hover:bg-surface-overlay disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <ChevronLeft className="h-3.5 w-3.5" />
              Previous
            </button>
            <button
              type="button"
              onClick={() => setPage((p) => Math.min(pagination.totalPages, p + 1))}
              disabled={page >= pagination.totalPages}
              className="flex items-center gap-1 rounded-md border border-border-subtle px-2.5 py-1 text-xs text-text-secondary transition-colors hover:bg-surface-overlay disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Next
              <ChevronRight className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function CommCard({
  comm,
  isSelected,
  onSelect,
}: {
  comm: Communication;
  isSelected: boolean;
  onSelect: () => void;
}) {
  const Icon = getCommIcon(comm.communicationType);
  const preview = comm.bodyText
    ? comm.bodyText.length > 200
      ? `${comm.bodyText.substring(0, 200)}...`
      : comm.bodyText
    : null;

  return (
    <button
      type="button"
      onClick={onSelect}
      className={cn(
        'w-full rounded-lg border-l-2 p-4 text-left transition-colors',
        isSelected
          ? 'border-accent-blue bg-surface-overlay'
          : 'border-transparent bg-surface-raised hover:border-accent-blue hover:bg-surface-overlay'
      )}
    >
      <div className="flex items-start gap-3">
        <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-surface-overlay">
          <Icon className="h-4 w-4 text-text-tertiary" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-2">
            <h4 className="text-sm font-semibold text-text-primary truncate">
              {comm.subject ?? `${comm.communicationType} communication`}
            </h4>
            <span className="text-xs text-text-tertiary whitespace-nowrap shrink-0">
              {formatDate(comm.communicationDate)}
            </span>
          </div>

          <div className="mt-1 flex items-center gap-1 text-xs text-text-secondary">
            <span className="font-medium">{comm.fromName ?? 'Unknown'}</span>
            <ArrowRight className="h-3 w-3 text-text-disabled" />
            <span className="font-medium">{comm.toName ?? 'Unknown'}</span>
          </div>

          {comm.attachmentCount > 0 && (
            <div className="mt-1 flex items-center gap-1 text-xs text-text-tertiary">
              <Paperclip className="h-3 w-3" />
              <span>{comm.attachmentCount} attachment{comm.attachmentCount !== 1 ? 's' : ''}</span>
            </div>
          )}

          {preview && (
            <p className="mt-2 text-xs text-text-secondary line-clamp-2 leading-relaxed">
              {preview}
            </p>
          )}
        </div>
      </div>
    </button>
  );
}

function CommDetailPanel({
  comm,
  onClose,
}: {
  comm: Communication;
  onClose: () => void;
}) {
  const Icon = getCommIcon(comm.communicationType);

  return (
    <div className="w-[40%] shrink-0 overflow-y-auto rounded-lg border border-border-subtle bg-surface-raised">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border-subtle p-4">
        <h3 className="text-sm font-semibold text-text-primary">Communication Details</h3>
        <button
          type="button"
          onClick={onClose}
          className="text-text-tertiary hover:text-text-primary"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Metadata */}
      <div className="border-b border-border-subtle p-4">
        <div className="flex items-center gap-2 mb-3">
          <Icon className="h-5 w-5 text-text-tertiary" />
          <span className="inline-flex items-center rounded-sm border border-border-subtle bg-surface-overlay px-1.5 py-0.5 text-xs text-text-secondary capitalize">
            {comm.communicationType}
          </span>
          {comm.confidenceLevel && (
            <ConfidenceBadge level={comm.confidenceLevel} />
          )}
        </div>

        <h4 className="text-sm font-semibold text-text-primary mb-3">
          {comm.subject ?? 'No Subject'}
        </h4>

        <dl className="flex flex-col gap-2 text-xs">
          <div className="flex items-center justify-between">
            <dt className="text-text-tertiary">From</dt>
            <dd className="text-text-primary font-medium">{comm.fromName ?? '--'}</dd>
          </div>
          <div className="flex items-center justify-between">
            <dt className="text-text-tertiary">To</dt>
            <dd className="text-text-primary font-medium">{comm.toName ?? '--'}</dd>
          </div>
          {comm.ccNames && comm.ccNames.length > 0 && (
            <div className="flex items-start justify-between">
              <dt className="text-text-tertiary">CC</dt>
              <dd className="text-text-secondary text-right">
                {comm.ccNames.join(', ')}
              </dd>
            </div>
          )}
          <div className="flex items-center justify-between">
            <dt className="text-text-tertiary">Date</dt>
            <dd className="text-text-secondary">
              {formatDateTime(comm.communicationDate, comm.communicationTime)}
            </dd>
          </div>
          {comm.attachmentCount > 0 && (
            <div className="flex items-center justify-between">
              <dt className="text-text-tertiary flex items-center gap-1">
                <Paperclip className="h-3 w-3" /> Attachments
              </dt>
              <dd className="text-text-secondary">{comm.attachmentCount}</dd>
            </div>
          )}
        </dl>

        {comm.sourceDocumentEfta && (
          <div className="mt-3 text-xs">
            <span className="text-text-tertiary">Source: </span>
            <span className="font-mono text-accent-blue">{comm.sourceDocumentEfta}</span>
          </div>
        )}
      </div>

      {/* Body Text */}
      <div className="p-4">
        <h4 className="text-xs font-semibold uppercase tracking-wider text-text-tertiary mb-3">
          Message Body
        </h4>
        {comm.bodyText ? (
          <div className="whitespace-pre-wrap text-sm leading-relaxed text-text-secondary">
            {comm.bodyText}
          </div>
        ) : (
          <p className="text-xs text-text-disabled">No body text available.</p>
        )}
      </div>
    </div>
  );
}
