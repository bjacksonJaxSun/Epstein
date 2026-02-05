import { useState } from 'react';
import {
  DollarSign,
  ArrowUpDown,
  ChevronLeft,
  ChevronRight,
  AlertCircle,
  Users,
  Banknote,
  BarChart3,
  ArrowRight,
} from 'lucide-react';
import { format } from 'date-fns';
import { LoadingSpinner, StatCard } from '@/components/shared';
import { SankeyDiagram } from '@/components/financial/SankeyDiagram';
import {
  useFinancialTransactions,
  useSankeyData,
  useFinancialSummary,
} from '@/hooks/useFinancials';
import { cn } from '@/lib/utils';
import type { FinancialTransaction } from '@/types';

function formatCurrency(amount: number, currency?: string): string {
  const symbols: Record<string, string> = {
    USD: '$',
    EUR: '\u20AC',
    GBP: '\u00A3',
    CHF: 'CHF ',
    JPY: '\u00A5',
  };
  const sym = symbols[currency ?? 'USD'] ?? (currency ? `${currency} ` : '$');
  return `${sym}${amount.toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

function formatDate(dateStr: string | undefined): string {
  if (!dateStr) return '--';
  try {
    return format(new Date(dateStr), 'MMM d, yyyy');
  } catch {
    return dateStr;
  }
}

type SortField = 'date' | 'amount';
type SortDir = 'asc' | 'desc';
type ActiveTab = 'sankey' | 'table';

export function FinancialPage() {
  const [page, setPage] = useState(1);
  const [sortField, setSortField] = useState<SortField>('date');
  const [sortDir, setSortDir] = useState<SortDir>('desc');
  const [activeTab, setActiveTab] = useState<ActiveTab>('sankey');

  // Fetch data
  const {
    data: txData,
    isLoading: txLoading,
    isError: txError,
  } = useFinancialTransactions({ page, pageSize: 25 });

  const {
    data: sankeyData,
    isLoading: sankeyLoading,
    isError: sankeyError,
  } = useSankeyData();

  const transactions = txData?.items ?? [];
  const pagination = txData;
  const summary = useFinancialSummary(transactions);

  // Sort transactions client-side
  const sorted = [...transactions].sort((a, b) => {
    if (sortField === 'date') {
      const da = new Date(a.transactionDate).getTime();
      const db = new Date(b.transactionDate).getTime();
      return sortDir === 'asc' ? da - db : db - da;
    }
    const diff = Math.abs(a.amount) - Math.abs(b.amount);
    return sortDir === 'asc' ? diff : -diff;
  });

  function toggleSort(field: SortField) {
    if (sortField === field) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortField(field);
      setSortDir('desc');
    }
  }

  function SortIcon({ field }: { field: SortField }) {
    return (
      <ArrowUpDown
        className={cn(
          'h-3 w-3 ml-1 inline',
          sortField === field ? 'text-accent-blue' : 'text-text-disabled'
        )}
      />
    );
  }

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div>
        <h2 className="text-xl font-semibold text-text-primary">
          Financial Flows
        </h2>
        <p className="mt-1 text-sm text-text-secondary">
          Transaction tracking and financial flow analysis.
        </p>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Transaction Volume"
          value={formatCurrency(summary.totalVolume)}
          icon={DollarSign}
          iconColor="text-entity-financial"
          trend={
            pagination
              ? `Page ${page} of ${pagination.totalPages}`
              : undefined
          }
        />
        <StatCard
          label="Transaction Count"
          value={pagination?.totalCount ?? summary.transactionCount}
          icon={Banknote}
          iconColor="text-accent-amber"
        />
        <StatCard
          label="Unique Parties"
          value={summary.uniqueParties}
          icon={Users}
          iconColor="text-entity-person"
        />
        <StatCard
          label="Currencies"
          value={summary.currencyCount || '--'}
          icon={BarChart3}
          iconColor="text-accent-purple"
          trend={summary.currencyBreakdown || undefined}
        />
      </div>

      {/* Tab Bar */}
      <div className="flex items-center gap-1 rounded-lg border border-border-subtle bg-surface-raised p-1">
        <TabButton
          active={activeTab === 'sankey'}
          onClick={() => setActiveTab('sankey')}
          icon={<BarChart3 className="h-4 w-4" />}
          label="Sankey Diagram"
        />
        <TabButton
          active={activeTab === 'table'}
          onClick={() => setActiveTab('table')}
          icon={<Banknote className="h-4 w-4" />}
          label="Transaction Table"
        />
      </div>

      {/* Active Tab Content */}
      {activeTab === 'sankey' && (
        <div className="rounded-lg border border-border-subtle bg-surface-raised overflow-hidden">
          <div className="flex items-center gap-3 border-b border-border-subtle px-6 py-4">
            <BarChart3 className="h-5 w-5 text-text-tertiary" />
            <h3 className="text-sm font-semibold uppercase tracking-wider text-text-tertiary">
              Financial Flow Diagram
            </h3>
          </div>

          {sankeyLoading && <LoadingSpinner className="py-24" />}

          {sankeyError && (
            <div className="flex flex-col items-center justify-center gap-3 py-16">
              <AlertCircle className="h-8 w-8 text-accent-red" />
              <p className="text-sm text-accent-red">
                Failed to load financial flow data.
              </p>
            </div>
          )}

          {!sankeyLoading &&
            !sankeyError &&
            (!sankeyData ||
              sankeyData.nodes.length === 0 ||
              sankeyData.links.length === 0) && (
              <div className="flex flex-col items-center justify-center gap-3 py-16">
                <DollarSign className="h-10 w-10 text-text-disabled" />
                <p className="text-sm text-text-disabled">
                  No financial transactions recorded.
                </p>
              </div>
            )}

          {!sankeyLoading &&
            !sankeyError &&
            sankeyData &&
            sankeyData.nodes.length > 0 &&
            sankeyData.links.length > 0 && (
              <div className="p-4">
                <SankeyDiagram data={sankeyData} height={500} />
                <div className="mt-3 flex items-center justify-center gap-6 text-xs text-text-tertiary">
                  <div className="flex items-center gap-2">
                    <div className="h-2.5 w-2.5 rounded-sm bg-[#4A9EFF]" />
                    <span>Person</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="h-2.5 w-2.5 rounded-sm bg-[#A855F7]" />
                    <span>Organization</span>
                  </div>
                </div>
              </div>
            )}
        </div>
      )}

      {activeTab === 'table' && (
        <>
          {/* Transaction Table */}
          <div className="rounded-lg border border-border-subtle bg-surface-raised overflow-hidden">
            {txLoading && <LoadingSpinner className="py-24" />}

            {txError && (
              <div className="flex flex-col items-center justify-center gap-3 py-12">
                <AlertCircle className="h-8 w-8 text-accent-red" />
                <p className="text-sm text-accent-red">
                  Failed to load transactions.
                </p>
              </div>
            )}

            {!txLoading && !txError && transactions.length === 0 && (
              <div className="flex flex-col items-center justify-center gap-3 py-16">
                <DollarSign className="h-10 w-10 text-text-disabled" />
                <p className="text-sm text-text-disabled">
                  No transactions found.
                </p>
              </div>
            )}

            {!txLoading && !txError && sorted.length > 0 && (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border-subtle">
                      <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-text-tertiary">
                        <button
                          type="button"
                          onClick={() => toggleSort('date')}
                          className="inline-flex items-center hover:text-text-primary"
                        >
                          Date <SortIcon field="date" />
                        </button>
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-text-tertiary">
                        Type
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-text-tertiary">
                        From
                      </th>
                      <th className="px-2 py-3 text-center text-xs font-semibold uppercase tracking-wider text-text-tertiary" />
                      <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-text-tertiary">
                        To
                      </th>
                      <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wider text-text-tertiary">
                        <button
                          type="button"
                          onClick={() => toggleSort('amount')}
                          className="inline-flex items-center hover:text-text-primary"
                        >
                          Amount <SortIcon field="amount" />
                        </button>
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-text-tertiary">
                        Purpose
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-text-tertiary">
                        Bank
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border-subtle">
                    {sorted.map((tx) => (
                      <TransactionRow key={tx.transactionId} tx={tx} />
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
                Page {page} of {pagination.totalPages} (
                {pagination.totalCount.toLocaleString()} total)
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
                  onClick={() =>
                    setPage((p) => Math.min(pagination.totalPages, p + 1))
                  }
                  disabled={page >= pagination.totalPages}
                  className="flex items-center gap-1 rounded-md border border-border-subtle px-2.5 py-1 text-xs text-text-secondary transition-colors hover:bg-surface-overlay disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  Next
                  <ChevronRight className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Sub-components                                                      */
/* ------------------------------------------------------------------ */

function TabButton({
  active,
  onClick,
  icon,
  label,
}: {
  active: boolean;
  onClick: () => void;
  icon: React.ReactNode;
  label: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'flex items-center gap-2 rounded-md px-4 py-2 text-sm font-medium transition-colors',
        active
          ? 'bg-surface-overlay text-text-primary'
          : 'text-text-tertiary hover:text-text-secondary hover:bg-surface-sunken'
      )}
    >
      {icon}
      {label}
    </button>
  );
}

function TransactionRow({ tx }: { tx: FinancialTransaction }) {
  const isOutgoing = tx.amount < 0;
  return (
    <tr className="transition-colors hover:bg-surface-overlay">
      <td className="px-4 py-3 text-xs text-text-secondary whitespace-nowrap">
        {formatDate(tx.transactionDate)}
      </td>
      <td className="px-4 py-3">
        {tx.transactionType ? (
          <span className="inline-flex items-center rounded-sm border border-border-subtle bg-surface-overlay px-1.5 py-0.5 text-xs text-text-secondary">
            {tx.transactionType}
          </span>
        ) : (
          <span className="text-xs text-text-disabled">--</span>
        )}
      </td>
      <td className="px-4 py-3 text-xs text-text-primary max-w-[160px] truncate">
        {tx.fromName ?? '--'}
      </td>
      <td className="px-2 py-3 text-center">
        <ArrowRight className="h-3.5 w-3.5 text-text-disabled inline" />
      </td>
      <td className="px-4 py-3 text-xs text-text-primary max-w-[160px] truncate">
        {tx.toName ?? '--'}
      </td>
      <td
        className={cn(
          'px-4 py-3 text-xs font-mono text-right whitespace-nowrap',
          isOutgoing ? 'text-accent-red' : 'text-accent-green'
        )}
      >
        {formatCurrency(Math.abs(tx.amount), tx.currency ?? undefined)}
      </td>
      <td className="px-4 py-3 text-xs text-text-secondary max-w-[160px] truncate">
        {tx.purpose ?? '--'}
      </td>
      <td className="px-4 py-3 text-xs text-text-tertiary max-w-[120px] truncate">
        {tx.bankName ?? '--'}
      </td>
    </tr>
  );
}
