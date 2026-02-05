import { ChevronLeft, ChevronRight } from 'lucide-react';
import { cn } from '@/lib/utils';

export interface Column<T> {
  key: string;
  header: string;
  render?: (item: T) => React.ReactNode;
  sortable?: boolean;
  width?: string;
}

interface PaginationConfig {
  page: number;
  pageSize: number;
  totalCount: number;
  onPageChange: (page: number) => void;
}

interface DataTableProps<T> {
  data: T[];
  columns: Column<T>[];
  loading?: boolean;
  emptyMessage?: string;
  onRowClick?: (item: T) => void;
  pagination?: PaginationConfig;
  keyExtractor: (item: T) => string | number;
}

function SkeletonRow({ columnCount }: { columnCount: number }) {
  return (
    <tr className="border-b border-border-subtle">
      {Array.from({ length: columnCount }).map((_, i) => (
        <td key={i} className="px-4 py-3">
          <div className="h-4 animate-pulse rounded bg-surface-overlay" />
        </td>
      ))}
    </tr>
  );
}

export function DataTable<T>({
  data,
  columns,
  loading = false,
  emptyMessage = 'No data available.',
  onRowClick,
  pagination,
  keyExtractor,
}: DataTableProps<T>) {
  const totalPages = pagination
    ? Math.ceil(pagination.totalCount / pagination.pageSize)
    : 1;

  return (
    <div className="flex flex-col gap-0 rounded-lg border border-border-subtle bg-surface-raised overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="bg-surface-sunken">
              {columns.map((col) => (
                <th
                  key={col.key}
                  className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-text-secondary"
                  style={col.width ? { width: col.width } : undefined}
                >
                  {col.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              Array.from({ length: 5 }).map((_, i) => (
                <SkeletonRow key={i} columnCount={columns.length} />
              ))
            ) : data.length === 0 ? (
              <tr>
                <td
                  colSpan={columns.length}
                  className="px-4 py-16 text-center text-sm text-text-disabled"
                >
                  {emptyMessage}
                </td>
              </tr>
            ) : (
              data.map((item) => (
                <tr
                  key={keyExtractor(item)}
                  className={cn(
                    'border-b border-border-subtle bg-surface-raised transition-colors',
                    onRowClick &&
                      'cursor-pointer hover:bg-surface-overlay'
                  )}
                  onClick={() => onRowClick?.(item)}
                >
                  {columns.map((col) => (
                    <td
                      key={col.key}
                      className="px-4 py-3 text-sm text-text-primary"
                    >
                      {col.render
                        ? col.render(item)
                        : String(
                            (item as Record<string, unknown>)[col.key] ?? ''
                          )}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {pagination && !loading && data.length > 0 && (
        <div className="flex items-center justify-between border-t border-border-subtle bg-surface-sunken px-4 py-3">
          <span className="text-xs text-text-tertiary">
            Showing{' '}
            {Math.min(
              (pagination.page - 1) * pagination.pageSize + 1,
              pagination.totalCount
            )}
            -{Math.min(pagination.page * pagination.pageSize, pagination.totalCount)}{' '}
            of {pagination.totalCount.toLocaleString()}
          </span>
          <div className="flex items-center gap-2">
            <button
              type="button"
              disabled={pagination.page <= 1}
              onClick={() => pagination.onPageChange(pagination.page - 1)}
              className={cn(
                'flex h-8 w-8 items-center justify-center rounded-md text-sm transition-colors',
                pagination.page <= 1
                  ? 'cursor-not-allowed text-text-disabled'
                  : 'text-text-secondary hover:bg-surface-overlay hover:text-text-primary'
              )}
              aria-label="Previous page"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <span className="text-xs text-text-secondary">
              Page {pagination.page} of {totalPages}
            </span>
            <button
              type="button"
              disabled={pagination.page >= totalPages}
              onClick={() => pagination.onPageChange(pagination.page + 1)}
              className={cn(
                'flex h-8 w-8 items-center justify-center rounded-md text-sm transition-colors',
                pagination.page >= totalPages
                  ? 'cursor-not-allowed text-text-disabled'
                  : 'text-text-secondary hover:bg-surface-overlay hover:text-text-primary'
              )}
              aria-label="Next page"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
