import { useQuery } from '@tanstack/react-query';
import { financialApi } from '@/api/endpoints/financial';
import type { SankeyData, FinancialTransaction, PaginatedResponse } from '@/types';

export function useSankeyData(params?: { minAmount?: number }) {
  return useQuery<SankeyData>({
    queryKey: ['financial', 'sankey', params],
    queryFn: () => financialApi.getSankeyData(params),
  });
}

export function useFinancialTransactions(params: {
  page?: number;
  pageSize?: number;
  fromName?: string;
  toName?: string;
}) {
  return useQuery<PaginatedResponse<FinancialTransaction>>({
    queryKey: ['financial', 'transactions', params],
    queryFn: () => financialApi.list(params),
  });
}

export function useFinancialSummary(transactions: FinancialTransaction[]) {
  const totalVolume = transactions.reduce(
    (sum, t) => sum + Math.abs(t.amount),
    0
  );

  const uniqueParties = new Set<string>();
  const currencyCounts = new Map<string, number>();

  for (const t of transactions) {
    if (t.fromName) uniqueParties.add(t.fromName);
    if (t.toName) uniqueParties.add(t.toName);
    const cur = t.currency ?? 'USD';
    currencyCounts.set(cur, (currencyCounts.get(cur) ?? 0) + 1);
  }

  const currencyBreakdown = Array.from(currencyCounts.entries())
    .sort((a, b) => b[1] - a[1])
    .map(([cur, count]) => `${cur}: ${count}`)
    .join(', ');

  return {
    totalVolume,
    transactionCount: transactions.length,
    uniqueParties: uniqueParties.size,
    currencyCount: currencyCounts.size,
    currencyBreakdown,
  };
}
