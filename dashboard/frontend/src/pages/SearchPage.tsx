import { useState, useMemo, useCallback } from 'react';
import { useSearchParams, useNavigate } from 'react-router';
import {
  Search,
  User,
  Building2,
  MapPin,
  Calendar,
  FileText,
  Filter,
  ChevronLeft,
  ChevronRight,
  AlertTriangle,
  ExternalLink,
} from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { format } from 'date-fns';
import { searchApi } from '@/api/endpoints/search';
import { LoadingSpinner } from '@/components/shared';
import { cn } from '@/lib/utils';
import type { EntitySearchResult, SearchResult } from '@/types';

type SearchTab = 'documents' | 'entities';

const entityTypes = [
  { key: 'person', label: 'People', icon: User, color: 'text-entity-person bg-entity-person/15' },
  { key: 'organization', label: 'Organizations', icon: Building2, color: 'text-entity-organization bg-entity-organization/15' },
  { key: 'document', label: 'Documents', icon: FileText, color: 'text-entity-document bg-entity-document/15' },
  { key: 'event', label: 'Events', icon: Calendar, color: 'text-entity-event bg-entity-event/15' },
  { key: 'location', label: 'Locations', icon: MapPin, color: 'text-entity-location bg-entity-location/15' },
] as const;

const typeLabels: Record<string, string> = {
  person: 'People',
  organization: 'Organizations',
  document: 'Documents',
  event: 'Events',
  location: 'Locations',
};

function groupByType(results: EntitySearchResult[]) {
  const groups: Record<string, EntitySearchResult[]> = {};
  for (const result of results) {
    const type = result.entityType;
    if (!groups[type]) {
      groups[type] = [];
    }
    groups[type].push(result);
  }
  return groups;
}

function formatDate(dateStr: string | undefined): string {
  if (!dateStr) return '';
  try {
    return format(new Date(dateStr), 'MMM d, yyyy');
  } catch {
    return dateStr;
  }
}

function HighlightedSnippet({ html }: { html: string | undefined }) {
  if (!html) return <span className="text-text-tertiary italic">No preview available</span>;
  return (
    <span
      className="text-text-secondary"
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}

function DocumentSearchResults({
  query,
  page,
  onPageChange,
}: {
  query: string;
  page: number;
  onPageChange: (page: number) => void;
}) {
  const pageSize = 20;

  const { data, isLoading, error } = useQuery({
    queryKey: ['search-documents', query, page],
    queryFn: () => searchApi.fullText({ query, page, pageSize }),
    enabled: query.length >= 2,
    staleTime: 30_000,
  });

  const navigate = useNavigate();

  const openDocument = useCallback((documentId: number) => {
    window.open(`/api/documents/${documentId}/file`, '_blank');
  }, []);

  if (isLoading) {
    return <LoadingSpinner className="py-24" size="lg" />;
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 rounded-lg border border-border-subtle bg-surface-raised py-24">
        <AlertTriangle className="h-12 w-12 text-accent-red" />
        <p className="text-sm text-text-secondary">
          Error loading search results. Please try again.
        </p>
      </div>
    );
  }

  if (!data || data.totalCount === 0) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 rounded-lg border border-border-subtle bg-surface-raised py-24">
        <Search className="h-12 w-12 text-text-disabled" />
        <p className="text-sm text-text-disabled">
          No documents found for &quot;{query}&quot;
        </p>
      </div>
    );
  }

  const totalPages = Math.ceil(data.totalCount / pageSize);

  return (
    <div className="flex flex-col gap-4">
      {/* Results count */}
      <p className="text-sm text-text-secondary">
        Found {data.totalCount.toLocaleString()} document{data.totalCount !== 1 ? 's' : ''}
      </p>

      {/* Results list */}
      <div className="flex flex-col gap-3">
        {data.items.map((result: SearchResult) => (
          <div
            key={result.documentId}
            className="group rounded-lg border border-border-subtle bg-surface-raised p-4 transition-colors hover:border-border-default"
          >
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1 min-w-0">
                {/* Title and EFTA */}
                <div className="flex items-center gap-2 mb-1">
                  <button
                    type="button"
                    onClick={() => openDocument(result.documentId)}
                    className="font-medium text-accent-blue hover:underline truncate"
                  >
                    {result.title || result.eftaNumber}
                  </button>
                  {result.isRedacted && (
                    <span className="shrink-0 inline-flex items-center rounded-sm border border-accent-amber/30 bg-accent-amber/15 px-1.5 py-0.5 text-xs font-medium text-accent-amber">
                      Redacted
                    </span>
                  )}
                </div>

                {/* Metadata row */}
                <div className="flex items-center gap-3 text-xs text-text-tertiary mb-2">
                  <span className="font-mono">{result.eftaNumber}</span>
                  {result.documentType && (
                    <span className="inline-flex items-center rounded-sm border border-border-default bg-surface-overlay px-1.5 py-0.5">
                      {result.documentType.replace(/_/g, ' ')}
                    </span>
                  )}
                  {result.documentDate && (
                    <span>{formatDate(result.documentDate)}</span>
                  )}
                  {result.pageCount && (
                    <span>{result.pageCount} page{result.pageCount !== 1 ? 's' : ''}</span>
                  )}
                </div>

                {/* Snippet */}
                <div className="text-sm line-clamp-2">
                  <HighlightedSnippet html={result.snippet} />
                </div>
              </div>

              {/* Open button */}
              <button
                type="button"
                onClick={() => openDocument(result.documentId)}
                className="shrink-0 flex items-center gap-1 rounded-md border border-border-default bg-surface-base px-2.5 py-1.5 text-xs font-medium text-text-secondary transition-colors hover:bg-surface-overlay hover:text-text-primary"
              >
                <ExternalLink className="h-3.5 w-3.5" />
                Open PDF
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between border-t border-border-subtle pt-4">
          <p className="text-sm text-text-tertiary">
            Page {page} of {totalPages}
          </p>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => onPageChange(page - 1)}
              disabled={page <= 1}
              className="flex items-center gap-1 rounded-md border border-border-default bg-surface-base px-3 py-1.5 text-sm font-medium text-text-secondary transition-colors hover:bg-surface-overlay disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <ChevronLeft className="h-4 w-4" />
              Previous
            </button>
            <button
              type="button"
              onClick={() => onPageChange(page + 1)}
              disabled={page >= totalPages}
              className="flex items-center gap-1 rounded-md border border-border-default bg-surface-base px-3 py-1.5 text-sm font-medium text-text-secondary transition-colors hover:bg-surface-overlay disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Next
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function EntitySearchResults({ query }: { query: string }) {
  const navigate = useNavigate();
  const [selectedTypes, setSelectedTypes] = useState<Set<string>>(new Set());

  const { data: results, isLoading } = useQuery<EntitySearchResult[]>({
    queryKey: ['search-entities', query],
    queryFn: () => searchApi.entities({ query }),
    enabled: query.length >= 2,
    staleTime: 30_000,
  });

  const grouped = useMemo(() => {
    if (!results) return {};
    const filtered =
      selectedTypes.size > 0
        ? results.filter((r) => selectedTypes.has(r.entityType))
        : results;
    return groupByType(filtered);
  }, [results, selectedTypes]);

  const totalCount = results?.length ?? 0;

  const toggleType = useCallback((type: string) => {
    setSelectedTypes((prev) => {
      const next = new Set(prev);
      if (next.has(type)) {
        next.delete(type);
      } else {
        next.add(type);
      }
      return next;
    });
  }, []);

  const typeCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    if (results) {
      for (const r of results) {
        counts[r.entityType] = (counts[r.entityType] ?? 0) + 1;
      }
    }
    return counts;
  }, [results]);

  const navigateToEntity = useCallback(
    (result: EntitySearchResult) => {
      if (result.entityType === 'person') {
        navigate(`/people/${result.id}`);
      } else if (result.entityType === 'document') {
        navigate('/documents');
      } else if (result.entityType === 'organization') {
        navigate('/organizations');
      } else if (result.entityType === 'event') {
        navigate('/timeline');
      } else if (result.entityType === 'location') {
        navigate('/locations');
      }
    },
    [navigate]
  );

  if (isLoading) {
    return <LoadingSpinner className="py-24" size="lg" />;
  }

  if (totalCount === 0) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 rounded-lg border border-border-subtle bg-surface-raised py-24">
        <Search className="h-12 w-12 text-text-disabled" />
        <p className="text-sm text-text-disabled">
          No entities found for &quot;{query}&quot;
        </p>
      </div>
    );
  }

  return (
    <div className="flex gap-6">
      {/* Filter Sidebar */}
      <aside className="hidden w-56 shrink-0 lg:block">
        <div className="rounded-lg border border-border-subtle bg-surface-raised p-4">
          <div className="mb-3 flex items-center gap-2">
            <Filter className="h-4 w-4 text-text-tertiary" />
            <h3 className="text-sm font-medium text-text-primary">
              Filter by Type
            </h3>
          </div>
          <div className="flex flex-col gap-1">
            {entityTypes.map((et) => {
              const count = typeCounts[et.key] ?? 0;
              const Icon = et.icon;
              return (
                <label
                  key={et.key}
                  className={cn(
                    'flex cursor-pointer items-center gap-2.5 rounded-md px-2 py-1.5 text-sm transition-colors',
                    selectedTypes.has(et.key)
                      ? 'bg-surface-overlay text-text-primary'
                      : 'text-text-secondary hover:bg-surface-overlay'
                  )}
                >
                  <input
                    type="checkbox"
                    checked={selectedTypes.has(et.key)}
                    onChange={() => toggleType(et.key)}
                    className="sr-only"
                  />
                  <div
                    className={cn(
                      'flex h-4 w-4 items-center justify-center rounded border transition-colors',
                      selectedTypes.has(et.key)
                        ? 'border-accent-blue bg-accent-blue'
                        : 'border-border-default bg-surface-base'
                    )}
                  >
                    {selectedTypes.has(et.key) && (
                      <svg className="h-3 w-3 text-white" viewBox="0 0 12 12">
                        <path
                          d="M10 3L4.5 8.5L2 6"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth="2"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                        />
                      </svg>
                    )}
                  </div>
                  <Icon className="h-4 w-4 shrink-0" />
                  <span className="flex-1">{et.label}</span>
                  <span className="text-xs text-text-tertiary">
                    {count}
                  </span>
                </label>
              );
            })}
          </div>
          {selectedTypes.size > 0 && (
            <button
              type="button"
              onClick={() => setSelectedTypes(new Set())}
              className="mt-3 text-xs font-medium text-accent-blue hover:underline"
            >
              Clear filters
            </button>
          )}
        </div>
      </aside>

      {/* Results */}
      <div className="flex min-w-0 flex-1 flex-col gap-4">
        <p className="text-sm text-text-secondary">
          Found {totalCount} entit{totalCount !== 1 ? 'ies' : 'y'}
        </p>
        {Object.entries(typeLabels).map(([type, label]) => {
          const items = grouped[type];
          if (!items || items.length === 0) return null;
          const typeInfo = entityTypes.find((et) => et.key === type);
          const Icon = typeInfo?.icon ?? FileText;
          return (
            <div key={type}>
              <div className="mb-2 flex items-center gap-2">
                <h3 className="text-sm font-semibold text-text-primary">
                  {label}
                </h3>
                <span className="flex h-5 min-w-[20px] items-center justify-center rounded-full bg-surface-overlay px-1.5 text-xs font-semibold text-text-tertiary">
                  {items.length}
                </span>
              </div>
              <div className="flex flex-col gap-2">
                {items.map((result) => (
                  <button
                    key={`${result.entityType}-${result.id}`}
                    type="button"
                    onClick={() => navigateToEntity(result)}
                    className="flex items-center gap-3 rounded-lg border border-border-subtle bg-surface-raised p-3 text-left transition-colors hover:border-border-default hover:bg-surface-overlay"
                  >
                    <div
                      className={cn(
                        'flex h-9 w-9 shrink-0 items-center justify-center rounded-md',
                        typeInfo?.color ?? 'text-entity-document bg-entity-document/15'
                      )}
                    >
                      <Icon className="h-4 w-4" />
                    </div>
                    <div className="flex min-w-0 flex-col">
                      <span className="truncate font-medium text-text-primary">
                        {result.name}
                      </span>
                      {result.subtitle && (
                        <span className="truncate text-xs text-text-tertiary">
                          {result.subtitle}
                        </span>
                      )}
                    </div>
                  </button>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function SearchPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const query = searchParams.get('q') ?? '';
  const tabParam = searchParams.get('tab') as SearchTab | null;
  const pageParam = parseInt(searchParams.get('page') ?? '1', 10);

  const [activeTab, setActiveTab] = useState<SearchTab>(tabParam || 'documents');
  const [page, setPage] = useState(pageParam);

  const handleTabChange = useCallback((tab: SearchTab) => {
    setActiveTab(tab);
    setPage(1);
    setSearchParams((prev) => {
      prev.set('tab', tab);
      prev.delete('page');
      return prev;
    });
  }, [setSearchParams]);

  const handlePageChange = useCallback((newPage: number) => {
    setPage(newPage);
    setSearchParams((prev) => {
      prev.set('page', String(newPage));
      return prev;
    });
  }, [setSearchParams]);

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div>
        <h2 className="text-xl font-semibold text-text-primary">
          Search Results
        </h2>
        {query && (
          <p className="mt-1 text-sm text-text-secondary">
            Searching for &quot;{query}&quot;
          </p>
        )}
      </div>

      {!query && (
        <div className="flex flex-col items-center justify-center gap-4 rounded-lg border border-border-subtle bg-surface-raised py-24">
          <Search className="h-12 w-12 text-text-disabled" />
          <p className="text-sm text-text-disabled">
            Enter a search query using the search bar above.
          </p>
        </div>
      )}

      {query && (
        <>
          {/* Tabs */}
          <div className="flex gap-1 border-b border-border-subtle">
            <button
              type="button"
              onClick={() => handleTabChange('documents')}
              className={cn(
                'flex items-center gap-2 border-b-2 px-4 py-2 text-sm font-medium transition-colors',
                activeTab === 'documents'
                  ? 'border-accent-blue text-accent-blue'
                  : 'border-transparent text-text-secondary hover:text-text-primary'
              )}
            >
              <FileText className="h-4 w-4" />
              Full-Text Search
            </button>
            <button
              type="button"
              onClick={() => handleTabChange('entities')}
              className={cn(
                'flex items-center gap-2 border-b-2 px-4 py-2 text-sm font-medium transition-colors',
                activeTab === 'entities'
                  ? 'border-accent-blue text-accent-blue'
                  : 'border-transparent text-text-secondary hover:text-text-primary'
              )}
            >
              <User className="h-4 w-4" />
              Entity Search
            </button>
          </div>

          {/* Tab Content */}
          {activeTab === 'documents' && (
            <DocumentSearchResults
              query={query}
              page={page}
              onPageChange={handlePageChange}
            />
          )}
          {activeTab === 'entities' && (
            <EntitySearchResults query={query} />
          )}
        </>
      )}
    </div>
  );
}
