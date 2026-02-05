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
} from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { searchApi } from '@/api/endpoints/search';
import { LoadingSpinner } from '@/components/shared';
import { cn } from '@/lib/utils';
import type { EntitySearchResult } from '@/types';

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

export function SearchPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const query = searchParams.get('q') ?? '';
  const [selectedTypes, setSelectedTypes] = useState<Set<string>>(new Set());

  const { data: results, isLoading } = useQuery<EntitySearchResult[]>({
    queryKey: ['search-page', query],
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

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div>
        <h2 className="text-xl font-semibold text-text-primary">
          Search Results
        </h2>
        {query && (
          <p className="mt-1 text-sm text-text-secondary">
            {totalCount} result{totalCount !== 1 ? 's' : ''} for &quot;{query}&quot;
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

      {query && isLoading && <LoadingSpinner className="py-24" size="lg" />}

      {query && !isLoading && totalCount === 0 && (
        <div className="flex flex-col items-center justify-center gap-4 rounded-lg border border-border-subtle bg-surface-raised py-24">
          <Search className="h-12 w-12 text-text-disabled" />
          <p className="text-sm text-text-disabled">
            No results found for &quot;{query}&quot;
          </p>
        </div>
      )}

      {query && !isLoading && totalCount > 0 && (
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
      )}
    </div>
  );
}
