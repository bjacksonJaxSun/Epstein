import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Clipboard,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  ChevronUp,
  AlertCircle,
  FileText,
  Shield,
} from 'lucide-react';
import { format } from 'date-fns';
import { evidenceApi } from '@/api/endpoints/evidence';
import type { EvidenceItem } from '@/api/endpoints/evidence';
import { LoadingSpinner } from '@/components/shared';
import { cn } from '@/lib/utils';

function formatDate(dateStr: string | undefined): string {
  if (!dateStr) return '--';
  try {
    return format(new Date(dateStr), 'MMM d, yyyy');
  } catch {
    return dateStr;
  }
}

function StatusBadge({ status }: { status: string | undefined }) {
  if (!status) return <span className="text-xs text-text-disabled">--</span>;

  const colors: Record<string, string> = {
    in_custody: 'bg-accent-green/15 text-accent-green border-accent-green/30',
    released: 'bg-accent-amber/15 text-accent-amber border-accent-amber/30',
    destroyed: 'bg-accent-red/15 text-accent-red border-accent-red/30',
    transferred: 'bg-accent-blue/15 text-accent-blue border-accent-blue/30',
    sealed: 'bg-accent-purple/15 text-accent-purple border-accent-purple/30',
  };

  const normalized = status.toLowerCase().replace(/\s+/g, '_');
  const style = colors[normalized] ?? 'bg-border-subtle text-text-secondary border-border-default';

  return (
    <span
      className={cn(
        'inline-flex items-center rounded-sm border px-1.5 py-0.5 text-xs font-medium',
        style
      )}
    >
      {status.replace(/_/g, ' ')}
    </span>
  );
}

export function EvidencePage() {
  const [page, setPage] = useState(1);
  const [expandedId, setExpandedId] = useState<number | null>(null);

  const { data, isLoading, isError } = useQuery({
    queryKey: ['evidence', page],
    queryFn: () => evidenceApi.list({ page, pageSize: 20 }),
  });

  const items = data?.items ?? [];
  const pagination = data;

  function toggleExpanded(id: number) {
    setExpandedId((prev) => (prev === id ? null : id));
  }

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div>
        <h2 className="text-xl font-semibold text-text-primary">Evidence</h2>
        <p className="mt-1 text-sm text-text-secondary">
          Evidence tagging, chain of custody tracking, and classification tools.
        </p>
      </div>

      {/* Evidence Table */}
      <div className="rounded-lg border border-border-subtle bg-surface-raised overflow-hidden">
        {isLoading && <LoadingSpinner className="py-24" />}

        {isError && (
          <div className="flex flex-col items-center justify-center gap-3 py-12">
            <AlertCircle className="h-8 w-8 text-accent-red" />
            <p className="text-sm text-accent-red">Failed to load evidence records.</p>
          </div>
        )}

        {!isLoading && !isError && items.length === 0 && (
          <div className="flex flex-col items-center justify-center gap-3 py-16">
            <Clipboard className="h-10 w-10 text-text-disabled" />
            <p className="text-sm text-text-disabled">No evidence records found.</p>
          </div>
        )}

        {!isLoading && !isError && items.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border-subtle">
                  <th className="w-8 px-2 py-3" />
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-text-tertiary">
                    Evidence #
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-text-tertiary">
                    Type
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-text-tertiary">
                    Description
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-text-tertiary">
                    Seized From
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-text-tertiary">
                    Seizure Date
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-text-tertiary">
                    Status
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-text-tertiary">
                    Current Location
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border-subtle">
                {items.map((item) => (
                  <EvidenceRow
                    key={item.evidenceId}
                    item={item}
                    isExpanded={expandedId === item.evidenceId}
                    onToggle={() => toggleExpanded(item.evidenceId)}
                  />
                ))}
              </tbody>
            </table>
          </div>
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

function EvidenceRow({
  item,
  isExpanded,
  onToggle,
}: {
  item: EvidenceItem;
  isExpanded: boolean;
  onToggle: () => void;
}) {
  return (
    <>
      <tr
        onClick={onToggle}
        className="cursor-pointer transition-colors hover:bg-surface-overlay"
      >
        <td className="px-2 py-3 text-center">
          {isExpanded ? (
            <ChevronUp className="h-4 w-4 text-text-tertiary inline" />
          ) : (
            <ChevronDown className="h-4 w-4 text-text-tertiary inline" />
          )}
        </td>
        <td className="px-4 py-3">
          <span className="text-xs font-mono text-accent-blue">
            {item.evidenceNumber ?? `EV-${item.evidenceId}`}
          </span>
        </td>
        <td className="px-4 py-3">
          {item.evidenceType ? (
            <span className="inline-flex items-center rounded-sm border border-border-subtle bg-surface-overlay px-1.5 py-0.5 text-xs text-text-secondary">
              {item.evidenceType}
            </span>
          ) : (
            <span className="text-xs text-text-disabled">--</span>
          )}
        </td>
        <td className="px-4 py-3 text-xs text-text-secondary max-w-[250px] truncate">
          {item.description ?? '--'}
        </td>
        <td className="px-4 py-3 text-xs text-text-secondary">
          {item.seizedFrom ?? '--'}
        </td>
        <td className="px-4 py-3 text-xs text-text-secondary whitespace-nowrap">
          {formatDate(item.seizureDate)}
        </td>
        <td className="px-4 py-3">
          <StatusBadge status={item.status} />
        </td>
        <td className="px-4 py-3 text-xs text-text-secondary max-w-[150px] truncate">
          {item.currentLocation ?? '--'}
        </td>
      </tr>

      {/* Expanded Row */}
      {isExpanded && (
        <tr>
          <td colSpan={8} className="bg-surface-sunken px-6 py-4">
            <div className="flex flex-col gap-4">
              {/* Full Description */}
              {item.description && (
                <div>
                  <h4 className="text-xs font-semibold uppercase tracking-wider text-text-tertiary mb-1">
                    Full Description
                  </h4>
                  <p className="text-sm text-text-secondary leading-relaxed">
                    {item.description}
                  </p>
                </div>
              )}

              {/* Chain of Custody */}
              <div>
                <div className="flex items-center gap-1.5 mb-2">
                  <Shield className="h-3.5 w-3.5 text-text-tertiary" />
                  <h4 className="text-xs font-semibold uppercase tracking-wider text-text-tertiary">
                    Chain of Custody
                  </h4>
                </div>
                {item.chainOfCustody && item.chainOfCustody.length > 0 ? (
                  <div className="flex flex-col gap-2">
                    {item.chainOfCustody.map((record, i) => (
                      <div
                        key={i}
                        className="flex items-start gap-3 rounded-md border border-border-subtle bg-surface-raised p-3 text-xs"
                      >
                        <span className="text-text-tertiary whitespace-nowrap">
                          {formatDate(record.date)}
                        </span>
                        <span className="inline-flex items-center rounded-sm border border-border-subtle bg-surface-overlay px-1.5 py-0.5 text-text-secondary">
                          {record.action}
                        </span>
                        <span className="text-text-primary font-medium">
                          {record.handler}
                        </span>
                        {record.notes && (
                          <span className="text-text-secondary flex-1">
                            {record.notes}
                          </span>
                        )}
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-text-disabled">No chain of custody records.</p>
                )}
              </div>

              {/* Source Document */}
              {item.sourceDocumentEfta && (
                <div className="flex items-center gap-2 text-xs">
                  <FileText className="h-3.5 w-3.5 text-text-tertiary" />
                  <span className="text-text-tertiary">Source Document:</span>
                  <span className="font-mono text-accent-blue">{item.sourceDocumentEfta}</span>
                </div>
              )}
            </div>
          </td>
        </tr>
      )}
    </>
  );
}
