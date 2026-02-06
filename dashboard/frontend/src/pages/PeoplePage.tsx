import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Search,
  Users,
  FileText,
  Calendar,
  Link2,
  DollarSign,
  AlertTriangle,
  Merge,
  Check,
  ArrowUp,
  ArrowDown,
  ArrowUpDown,
  Filter,
} from 'lucide-react';
import { ConfidenceBadge, LoadingSpinner } from '@/components/shared';
import { peopleApi } from '@/api/endpoints/people';
import { cn } from '@/lib/utils';
import type { Person } from '@/types';

type SortField = 'fullName' | 'primaryRole' | 'documentCount' | 'eventCount' | 'relationshipCount' | 'financialCount' | 'totalMentions' | 'epsteinRelationship' | 'confidenceLevel';
type ViewMode = 'directory' | 'duplicates';

interface ColumnFilter {
  fullName: string;
  primaryRole: string;
  minDocs: string;
  minEvents: string;
  minRelations: string;
  minFinancial: string;
  minTotal: string;
  epsteinRelationship: string;
  confidence: string;
}

const PAGE_SIZE = 25;

const CONFIDENCE_OPTIONS = ['', 'high', 'medium', 'low'];
const EPSTEIN_RELATIONSHIP_OPTIONS = ['', 'victim', 'witness', 'defendant', 'prosecutor', 'judge', 'investigator', 'employee', 'defense_attorney', 'associate'];

export function PeoplePage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [viewMode, setViewMode] = useState<ViewMode>('directory');
  const [page, setPage] = useState(1);
  const [sortBy, setSortBy] = useState<SortField>('totalMentions');
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc');
  const [showFilters, setShowFilters] = useState(false);
  const [filters, setFilters] = useState<ColumnFilter>({
    fullName: '',
    primaryRole: '',
    minDocs: '',
    minEvents: '',
    minRelations: '',
    minFinancial: '',
    minTotal: '',
    epsteinRelationship: '',
    confidence: '',
  });
  const [selectedDuplicates, setSelectedDuplicates] = useState<Map<string, Set<number>>>(new Map());

  const filterDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [debouncedFilters, setDebouncedFilters] = useState(filters);

  useEffect(() => {
    if (filterDebounceRef.current) {
      clearTimeout(filterDebounceRef.current);
    }
    filterDebounceRef.current = setTimeout(() => {
      setDebouncedFilters(filters);
      setPage(1);
    }, 300);
    return () => {
      if (filterDebounceRef.current) clearTimeout(filterDebounceRef.current);
    };
  }, [filters]);

  const handleSort = (field: SortField) => {
    if (sortBy === field) {
      setSortDirection(d => d === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(field);
      setSortDirection(field === 'fullName' ? 'asc' : 'desc');
    }
  };

  const handleFilterChange = (key: keyof ColumnFilter, value: string) => {
    setFilters(prev => ({ ...prev, [key]: value }));
  };

  const clearFilters = () => {
    setFilters({
      fullName: '',
      primaryRole: '',
      minDocs: '',
      minEvents: '',
      minRelations: '',
      minFinancial: '',
      minTotal: '',
      epsteinRelationship: '',
      confidence: '',
    });
  };

  const hasActiveFilters = Object.values(filters).some(v => v !== '');

  const peopleQuery = useQuery({
    queryKey: ['people', page, sortBy, sortDirection, debouncedFilters],
    queryFn: () => peopleApi.list({
      page,
      pageSize: PAGE_SIZE,
      search: debouncedFilters.fullName || undefined,
      sortBy,
      sortDirection,
    }),
    enabled: viewMode === 'directory',
  });

  // Client-side filtering for additional filters
  const filteredPeople = (peopleQuery.data?.items ?? []).filter(person => {
    if (debouncedFilters.primaryRole &&
        !(person.primaryRole?.toLowerCase().includes(debouncedFilters.primaryRole.toLowerCase()))) {
      return false;
    }
    if (debouncedFilters.minDocs && (person.documentCount ?? 0) < parseInt(debouncedFilters.minDocs)) {
      return false;
    }
    if (debouncedFilters.minEvents && (person.eventCount ?? 0) < parseInt(debouncedFilters.minEvents)) {
      return false;
    }
    if (debouncedFilters.minRelations && (person.relationshipCount ?? 0) < parseInt(debouncedFilters.minRelations)) {
      return false;
    }
    if (debouncedFilters.minFinancial && (person.financialCount ?? 0) < parseInt(debouncedFilters.minFinancial)) {
      return false;
    }
    if (debouncedFilters.minTotal && (person.totalMentions ?? 0) < parseInt(debouncedFilters.minTotal)) {
      return false;
    }
    if (debouncedFilters.confidence && person.confidenceLevel !== debouncedFilters.confidence) {
      return false;
    }
    if (debouncedFilters.epsteinRelationship &&
        person.epsteinRelationship?.toLowerCase() !== debouncedFilters.epsteinRelationship.toLowerCase()) {
      return false;
    }
    return true;
  });

  const duplicatesQuery = useQuery({
    queryKey: ['duplicates'],
    queryFn: () => peopleApi.getDuplicates(),
    enabled: viewMode === 'duplicates',
  });

  const mergeMutation = useMutation({
    mutationFn: ({ primaryId, mergeIds }: { primaryId: number; mergeIds: number[] }) =>
      peopleApi.mergePersons(primaryId, mergeIds),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['people'] });
      queryClient.invalidateQueries({ queryKey: ['duplicates'] });
      setSelectedDuplicates(new Map());
    },
  });

  const toggleDuplicateSelection = (groupName: string, personId: number) => {
    setSelectedDuplicates(prev => {
      const newMap = new Map(prev);
      const groupSet = newMap.get(groupName) ?? new Set();
      if (groupSet.has(personId)) {
        groupSet.delete(personId);
      } else {
        groupSet.add(personId);
      }
      newMap.set(groupName, groupSet);
      return newMap;
    });
  };

  const handleMerge = (groupName: string, variants: Person[]) => {
    const selected = selectedDuplicates.get(groupName);
    if (!selected || selected.size < 2) return;

    const selectedIds = Array.from(selected);
    const sortedByMentions = variants
      .filter(v => selectedIds.includes(v.personId))
      .sort((a, b) => (b.totalMentions ?? 0) - (a.totalMentions ?? 0));

    const primaryId = sortedByMentions[0].personId;
    const mergeIds = selectedIds.filter(id => id !== primaryId);

    mergeMutation.mutate({ primaryId, mergeIds });
  };

  const pagination = peopleQuery.data;
  const duplicates = duplicatesQuery.data ?? [];

  const SortIcon = ({ field }: { field: SortField }) => {
    if (sortBy !== field) return <ArrowUpDown className="h-3 w-3 opacity-40" />;
    return sortDirection === 'asc'
      ? <ArrowUp className="h-3 w-3 text-accent-blue" />
      : <ArrowDown className="h-3 w-3 text-accent-blue" />;
  };

  const SortableHeader = ({ field, children, className }: { field: SortField; children: React.ReactNode; className?: string }) => (
    <th
      onClick={() => handleSort(field)}
      className={cn(
        'px-3 py-2 text-left text-xs font-semibold uppercase tracking-wider text-text-tertiary cursor-pointer hover:text-text-primary hover:bg-surface-overlay/50 transition-colors select-none',
        sortBy === field && 'text-accent-blue',
        className
      )}
    >
      <div className="flex items-center gap-1">
        {children}
        <SortIcon field={field} />
      </div>
    </th>
  );

  return (
    <div className="flex flex-col gap-4">
      {/* Page header */}
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-xl font-semibold text-text-primary">People Directory</h2>
          <p className="mt-1 text-sm text-text-secondary">
            {viewMode === 'directory'
              ? 'Browse all identified individuals. Click column headers to sort.'
              : 'Review and merge duplicate person records.'}
          </p>
        </div>

        {/* View Mode Toggle */}
        <div className="flex rounded-lg border border-border-subtle p-0.5 bg-surface-sunken">
          <button
            type="button"
            onClick={() => setViewMode('directory')}
            className={cn(
              'flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors',
              viewMode === 'directory'
                ? 'bg-accent-blue text-white'
                : 'text-text-secondary hover:text-text-primary'
            )}
          >
            <Users className="h-3.5 w-3.5" />
            Directory
          </button>
          <button
            type="button"
            onClick={() => setViewMode('duplicates')}
            className={cn(
              'flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors',
              viewMode === 'duplicates'
                ? 'bg-accent-orange text-white'
                : 'text-text-secondary hover:text-text-primary'
            )}
          >
            <AlertTriangle className="h-3.5 w-3.5" />
            Duplicates
            {duplicatesQuery.data && duplicatesQuery.data.length > 0 && (
              <span className="ml-1 rounded-full bg-accent-orange/20 px-1.5 py-0.5 text-[10px] font-bold">
                {duplicatesQuery.data.length}
              </span>
            )}
          </button>
        </div>
      </div>

      {viewMode === 'directory' && (
        <>
          {/* Filter toggle and stats */}
          <div className="flex items-center justify-between">
            <button
              type="button"
              onClick={() => setShowFilters(v => !v)}
              className={cn(
                'flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-xs font-medium transition-colors',
                showFilters || hasActiveFilters
                  ? 'border-accent-blue bg-accent-blue/10 text-accent-blue'
                  : 'border-border-subtle bg-surface-raised text-text-secondary hover:bg-surface-overlay'
              )}
            >
              <Filter className="h-3.5 w-3.5" />
              Filters
              {hasActiveFilters && (
                <span className="rounded-full bg-accent-blue px-1.5 py-0.5 text-[10px] text-white">
                  {Object.values(filters).filter(v => v !== '').length}
                </span>
              )}
            </button>

            <div className="flex items-center gap-3">
              {hasActiveFilters && (
                <button
                  type="button"
                  onClick={clearFilters}
                  className="text-xs text-text-tertiary hover:text-text-primary"
                >
                  Clear filters
                </button>
              )}
              {pagination && (
                <span className="text-xs text-text-tertiary">
                  {pagination.totalCount.toLocaleString()} people
                  {filteredPeople.length < (peopleQuery.data?.items.length ?? 0) &&
                    ` (${filteredPeople.length} shown)`}
                </span>
              )}
            </div>
          </div>

          {/* Error state */}
          {peopleQuery.isError && (
            <div className="flex flex-col items-center justify-center gap-4 rounded-lg border border-accent-red/30 bg-accent-red/10 py-12">
              <Users className="h-10 w-10 text-accent-red" />
              <p className="text-sm text-text-secondary">Failed to load people data.</p>
              <button
                type="button"
                onClick={() => peopleQuery.refetch()}
                className="rounded-md bg-accent-blue px-4 py-2 text-sm font-medium text-white hover:bg-accent-blue/80"
              >
                Retry
              </button>
            </div>
          )}

          {/* Loading state */}
          {peopleQuery.isLoading && <LoadingSpinner className="py-24" />}

          {/* Data table */}
          {!peopleQuery.isError && !peopleQuery.isLoading && (
            <div className="rounded-lg border border-border-subtle bg-surface-raised overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    {/* Sortable headers */}
                    <tr className="border-b border-border-subtle bg-surface-overlay/50">
                      <SortableHeader field="fullName" className="min-w-[200px]">
                        Name
                      </SortableHeader>
                      <SortableHeader field="primaryRole" className="min-w-[150px]">
                        Role
                      </SortableHeader>
                      <SortableHeader field="documentCount" className="text-center w-[80px]">
                        <FileText className="h-3 w-3" />
                        Docs
                      </SortableHeader>
                      <SortableHeader field="eventCount" className="text-center w-[80px]">
                        <Calendar className="h-3 w-3" />
                        Events
                      </SortableHeader>
                      <SortableHeader field="relationshipCount" className="text-center w-[80px]">
                        <Link2 className="h-3 w-3" />
                        Rels
                      </SortableHeader>
                      <SortableHeader field="financialCount" className="text-center w-[80px]">
                        <DollarSign className="h-3 w-3" />
                        Fin
                      </SortableHeader>
                      <SortableHeader field="totalMentions" className="text-center w-[80px]">
                        Total
                      </SortableHeader>
                      <SortableHeader field="epsteinRelationship" className="min-w-[120px]">
                        Epstein Link
                      </SortableHeader>
                      <SortableHeader field="confidenceLevel" className="text-center w-[100px]">
                        Confidence
                      </SortableHeader>
                    </tr>

                    {/* Filter row */}
                    {showFilters && (
                      <tr className="border-b border-border-subtle bg-surface-sunken">
                        <th className="px-2 py-2">
                          <div className="relative">
                            <Search className="absolute left-2 top-1/2 h-3 w-3 -translate-y-1/2 text-text-disabled" />
                            <input
                              type="text"
                              placeholder="Filter name..."
                              value={filters.fullName}
                              onChange={(e) => handleFilterChange('fullName', e.target.value)}
                              className="w-full rounded border border-border-subtle bg-surface-base py-1 pl-7 pr-2 text-xs text-text-primary placeholder:text-text-disabled focus:border-accent-blue focus:outline-none"
                            />
                          </div>
                        </th>
                        <th className="px-2 py-2">
                          <input
                            type="text"
                            placeholder="Filter role..."
                            value={filters.primaryRole}
                            onChange={(e) => handleFilterChange('primaryRole', e.target.value)}
                            className="w-full rounded border border-border-subtle bg-surface-base py-1 px-2 text-xs text-text-primary placeholder:text-text-disabled focus:border-accent-blue focus:outline-none"
                          />
                        </th>
                        <th className="px-2 py-2">
                          <input
                            type="number"
                            placeholder="Min"
                            value={filters.minDocs}
                            onChange={(e) => handleFilterChange('minDocs', e.target.value)}
                            className="w-full rounded border border-border-subtle bg-surface-base py-1 px-2 text-xs text-text-primary text-center placeholder:text-text-disabled focus:border-accent-blue focus:outline-none"
                          />
                        </th>
                        <th className="px-2 py-2">
                          <input
                            type="number"
                            placeholder="Min"
                            value={filters.minEvents}
                            onChange={(e) => handleFilterChange('minEvents', e.target.value)}
                            className="w-full rounded border border-border-subtle bg-surface-base py-1 px-2 text-xs text-text-primary text-center placeholder:text-text-disabled focus:border-accent-blue focus:outline-none"
                          />
                        </th>
                        <th className="px-2 py-2">
                          <input
                            type="number"
                            placeholder="Min"
                            value={filters.minRelations}
                            onChange={(e) => handleFilterChange('minRelations', e.target.value)}
                            className="w-full rounded border border-border-subtle bg-surface-base py-1 px-2 text-xs text-text-primary text-center placeholder:text-text-disabled focus:border-accent-blue focus:outline-none"
                          />
                        </th>
                        <th className="px-2 py-2">
                          <input
                            type="number"
                            placeholder="Min"
                            value={filters.minFinancial}
                            onChange={(e) => handleFilterChange('minFinancial', e.target.value)}
                            className="w-full rounded border border-border-subtle bg-surface-base py-1 px-2 text-xs text-text-primary text-center placeholder:text-text-disabled focus:border-accent-blue focus:outline-none"
                          />
                        </th>
                        <th className="px-2 py-2">
                          <input
                            type="number"
                            placeholder="Min"
                            value={filters.minTotal}
                            onChange={(e) => handleFilterChange('minTotal', e.target.value)}
                            className="w-full rounded border border-border-subtle bg-surface-base py-1 px-2 text-xs text-text-primary text-center placeholder:text-text-disabled focus:border-accent-blue focus:outline-none"
                          />
                        </th>
                        <th className="px-2 py-2">
                          <select
                            value={filters.epsteinRelationship}
                            onChange={(e) => handleFilterChange('epsteinRelationship', e.target.value)}
                            className="w-full rounded border border-border-subtle bg-surface-base py-1 px-1 text-xs text-text-primary focus:border-accent-blue focus:outline-none"
                          >
                            <option value="">All</option>
                            {EPSTEIN_RELATIONSHIP_OPTIONS.filter(o => o).map(opt => (
                              <option key={opt} value={opt}>{opt.replace('_', ' ')}</option>
                            ))}
                          </select>
                        </th>
                        <th className="px-2 py-2">
                          <select
                            value={filters.confidence}
                            onChange={(e) => handleFilterChange('confidence', e.target.value)}
                            className="w-full rounded border border-border-subtle bg-surface-base py-1 px-1 text-xs text-text-primary focus:border-accent-blue focus:outline-none"
                          >
                            <option value="">All</option>
                            {CONFIDENCE_OPTIONS.filter(o => o).map(opt => (
                              <option key={opt} value={opt}>{opt}</option>
                            ))}
                          </select>
                        </th>
                      </tr>
                    )}
                  </thead>
                  <tbody className="divide-y divide-border-subtle">
                    {filteredPeople.length === 0 && (
                      <tr>
                        <td colSpan={9} className="px-4 py-12 text-center text-sm text-text-disabled">
                          {hasActiveFilters ? 'No people match the current filters.' : 'No people data available.'}
                        </td>
                      </tr>
                    )}
                    {filteredPeople.map((person) => (
                      <tr
                        key={person.personId}
                        onClick={() => navigate(`/people/${person.personId}`)}
                        className="cursor-pointer transition-colors hover:bg-surface-overlay"
                      >
                        <td className="px-3 py-2.5">
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              navigate(`/people/${person.personId}`);
                            }}
                            className="font-medium text-accent-blue hover:underline text-sm"
                          >
                            {person.fullName}
                          </button>
                        </td>
                        <td className="px-3 py-2.5">
                          {person.primaryRole ? (
                            <span className="inline-flex items-center rounded-sm bg-entity-person/15 border border-entity-person/30 px-1.5 py-0.5 text-xs text-entity-person">
                              {person.primaryRole}
                            </span>
                          ) : (
                            <span className="text-xs text-text-disabled">--</span>
                          )}
                        </td>
                        <td className="px-3 py-2.5 text-center">
                          <span className={cn(
                            'font-mono text-xs',
                            (person.documentCount ?? 0) > 0 ? 'text-text-primary' : 'text-text-disabled'
                          )}>
                            {(person.documentCount ?? 0).toLocaleString()}
                          </span>
                        </td>
                        <td className="px-3 py-2.5 text-center">
                          <span className={cn(
                            'font-mono text-xs',
                            (person.eventCount ?? 0) > 0 ? 'text-text-primary' : 'text-text-disabled'
                          )}>
                            {(person.eventCount ?? 0).toLocaleString()}
                          </span>
                        </td>
                        <td className="px-3 py-2.5 text-center">
                          <span className={cn(
                            'font-mono text-xs',
                            (person.relationshipCount ?? 0) > 0 ? 'text-text-primary' : 'text-text-disabled'
                          )}>
                            {person.relationshipCount ?? 0}
                          </span>
                        </td>
                        <td className="px-3 py-2.5 text-center">
                          <span className={cn(
                            'font-mono text-xs',
                            (person.financialCount ?? 0) > 0 ? 'text-accent-green' : 'text-text-disabled'
                          )}>
                            {person.financialCount ?? 0}
                          </span>
                        </td>
                        <td className="px-3 py-2.5 text-center">
                          <span className={cn(
                            'font-mono text-xs font-semibold',
                            (person.totalMentions ?? 0) > 100 ? 'text-accent-blue' :
                            (person.totalMentions ?? 0) > 10 ? 'text-text-primary' : 'text-text-tertiary'
                          )}>
                            {(person.totalMentions ?? 0).toLocaleString()}
                          </span>
                        </td>
                        <td className="px-3 py-2.5">
                          {person.epsteinRelationship ? (
                            <span className="inline-flex items-center rounded-sm bg-accent-purple/15 border border-accent-purple/30 px-1.5 py-0.5 text-xs text-accent-purple">
                              {person.epsteinRelationship}
                            </span>
                          ) : (
                            <span className="text-xs text-text-disabled">--</span>
                          )}
                        </td>
                        <td className="px-3 py-2.5 text-center">
                          <ConfidenceBadge level={person.confidenceLevel} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Pagination */}
              {pagination && pagination.totalPages > 1 && (
                <div className="flex items-center justify-between border-t border-border-subtle px-4 py-3">
                  <span className="text-xs text-text-tertiary">
                    Page {page} of {pagination.totalPages}
                  </span>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => setPage(p => Math.max(1, p - 1))}
                      disabled={page <= 1}
                      className="rounded-md border border-border-subtle px-2.5 py-1 text-xs text-text-secondary hover:bg-surface-overlay disabled:opacity-40 disabled:cursor-not-allowed"
                    >
                      Previous
                    </button>
                    <button
                      type="button"
                      onClick={() => setPage(p => Math.min(pagination.totalPages, p + 1))}
                      disabled={page >= pagination.totalPages}
                      className="rounded-md border border-border-subtle px-2.5 py-1 text-xs text-text-secondary hover:bg-surface-overlay disabled:opacity-40 disabled:cursor-not-allowed"
                    >
                      Next
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}
        </>
      )}

      {viewMode === 'duplicates' && (
        <>
          {duplicatesQuery.isLoading && <LoadingSpinner className="py-24" />}

          {duplicatesQuery.isError && (
            <div className="flex flex-col items-center justify-center gap-4 rounded-lg border border-accent-red/30 bg-accent-red/10 py-12">
              <AlertTriangle className="h-10 w-10 text-accent-red" />
              <p className="text-sm text-text-secondary">Failed to load duplicate data.</p>
              <button
                type="button"
                onClick={() => duplicatesQuery.refetch()}
                className="rounded-md bg-accent-blue px-4 py-2 text-sm font-medium text-white hover:bg-accent-blue/80"
              >
                Retry
              </button>
            </div>
          )}

          {!duplicatesQuery.isLoading && !duplicatesQuery.isError && duplicates.length === 0 && (
            <div className="flex flex-col items-center justify-center gap-3 rounded-lg border border-border-subtle bg-surface-raised py-16">
              <Check className="h-12 w-12 text-accent-green" />
              <p className="text-sm text-text-secondary">No duplicate records detected.</p>
            </div>
          )}

          {!duplicatesQuery.isLoading && !duplicatesQuery.isError && duplicates.length > 0 && (
            <div className="space-y-4">
              <p className="text-xs text-text-tertiary">
                Found {duplicates.length} groups of potential duplicates. Select records to merge, then click the merge button.
              </p>

              {duplicates.map((group) => {
                const selected = selectedDuplicates.get(group.canonicalName) ?? new Set();
                const canMerge = selected.size >= 2;

                return (
                  <div
                    key={group.canonicalName}
                    className="rounded-lg border border-border-subtle bg-surface-raised overflow-hidden"
                  >
                    <div className="flex items-center justify-between border-b border-border-subtle bg-surface-overlay/50 px-4 py-2">
                      <div className="flex items-center gap-2">
                        <AlertTriangle className="h-4 w-4 text-accent-orange" />
                        <span className="text-sm font-medium text-text-primary">
                          {group.canonicalName}
                        </span>
                        <span className="text-xs text-text-tertiary">
                          ({group.variants.length} variants)
                        </span>
                      </div>
                      <button
                        type="button"
                        onClick={() => handleMerge(group.canonicalName, group.variants)}
                        disabled={!canMerge || mergeMutation.isPending}
                        className={cn(
                          'flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors',
                          canMerge
                            ? 'bg-accent-blue text-white hover:bg-accent-blue/80'
                            : 'bg-surface-sunken text-text-disabled cursor-not-allowed'
                        )}
                      >
                        <Merge className="h-3.5 w-3.5" />
                        Merge Selected ({selected.size})
                      </button>
                    </div>

                    <div className="divide-y divide-border-subtle">
                      {group.variants.map((variant) => (
                        <div
                          key={variant.personId}
                          onClick={() => toggleDuplicateSelection(group.canonicalName, variant.personId)}
                          className={cn(
                            'flex items-center gap-3 px-4 py-2 cursor-pointer transition-colors',
                            selected.has(variant.personId)
                              ? 'bg-accent-blue/10'
                              : 'hover:bg-surface-overlay'
                          )}
                        >
                          <div className={cn(
                            'h-4 w-4 rounded border flex items-center justify-center',
                            selected.has(variant.personId)
                              ? 'bg-accent-blue border-accent-blue'
                              : 'border-border-subtle'
                          )}>
                            {selected.has(variant.personId) && (
                              <Check className="h-3 w-3 text-white" />
                            )}
                          </div>
                          <span className="flex-1 text-sm text-text-primary">
                            {variant.fullName}
                          </span>
                          {variant.primaryRole && (
                            <span className="text-xs text-text-tertiary">{variant.primaryRole}</span>
                          )}
                          <span className="text-xs text-text-disabled">
                            ID: {variant.personId}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </>
      )}
    </div>
  );
}
