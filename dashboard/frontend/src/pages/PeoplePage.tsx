import { useState, useCallback, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router';
import { Search, Users, X } from 'lucide-react';
import { DataTable, ConfidenceBadge } from '@/components/shared';
import { usePeopleList } from '@/hooks';
import type { Column } from '@/components/shared';
import type { Person } from '@/types';

function formatDate(dateStr: string): string {
  try {
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  } catch {
    return dateStr;
  }
}

const PAGE_SIZE = 20;

export function PeoplePage() {
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleSearchChange = useCallback(
    (value: string) => {
      setSearch(value);
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
      debounceTimerRef.current = setTimeout(() => {
        setDebouncedSearch(value);
        setPage(1);
      }, 300);
    },
    []
  );

  useEffect(() => {
    return () => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
    };
  }, []);

  const clearSearch = useCallback(() => {
    setSearch('');
    setDebouncedSearch('');
    setPage(1);
  }, []);

  const peopleQuery = usePeopleList({
    page,
    pageSize: PAGE_SIZE,
    search: debouncedSearch || undefined,
  });

  const columns: Column<Person>[] = [
    {
      key: 'fullName',
      header: 'Full Name',
      width: '25%',
      render: (person) => (
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            navigate(`/people/${person.personId}`);
          }}
          className="font-medium text-accent-blue transition-colors hover:text-accent-blue/80 hover:underline"
        >
          {person.fullName}
        </button>
      ),
    },
    {
      key: 'primaryRole',
      header: 'Primary Role',
      render: (person) => (
        <span className="text-text-secondary">
          {person.primaryRole ?? '--'}
        </span>
      ),
    },
    {
      key: 'nationality',
      header: 'Nationality',
      render: (person) => (
        <span className="text-text-secondary">
          {person.nationality ?? '--'}
        </span>
      ),
    },
    {
      key: 'occupation',
      header: 'Occupation',
      render: (person) => (
        <span className="text-text-secondary">
          {person.occupation ?? '--'}
        </span>
      ),
    },
    {
      key: 'confidenceLevel',
      header: 'Confidence',
      width: '120px',
      render: (person) => (
        <ConfidenceBadge level={person.confidenceLevel} />
      ),
    },
    {
      key: 'createdAt',
      header: 'Created',
      width: '130px',
      render: (person) => (
        <span className="text-xs text-text-tertiary">
          {formatDate(person.createdAt)}
        </span>
      ),
    },
  ];

  return (
    <div className="flex flex-col gap-6">
      {/* Page header */}
      <div>
        <h2 className="text-xl font-semibold text-text-primary">
          People Directory
        </h2>
        <p className="mt-1 text-sm text-text-secondary">
          Browse and search all identified individuals across documents.
        </p>
      </div>

      {/* Search bar */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-tertiary" />
        <input
          type="text"
          placeholder="Search by name, role, or nationality..."
          value={search}
          onChange={(e) => handleSearchChange(e.target.value)}
          className="h-10 w-full rounded-lg border border-border-subtle bg-surface-raised pl-10 pr-10 text-sm text-text-primary placeholder:text-text-disabled focus:border-accent-blue focus:outline-none focus:ring-1 focus:ring-accent-blue"
        />
        {search && (
          <button
            type="button"
            onClick={clearSearch}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-text-tertiary transition-colors hover:text-text-primary"
            aria-label="Clear search"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>

      {/* Error state */}
      {peopleQuery.isError && (
        <div className="flex flex-col items-center justify-center gap-4 rounded-lg border border-accent-red/30 bg-accent-red/10 py-12">
          <Users className="h-10 w-10 text-accent-red" />
          <p className="text-sm text-text-secondary">
            Failed to load people data. Please try again.
          </p>
          <button
            type="button"
            onClick={() => peopleQuery.refetch()}
            className="rounded-md bg-accent-blue px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-accent-blue/80"
          >
            Retry
          </button>
        </div>
      )}

      {/* Data table */}
      {!peopleQuery.isError && (
        <DataTable<Person>
          data={peopleQuery.data?.items ?? []}
          columns={columns}
          loading={peopleQuery.isLoading}
          emptyMessage={
            debouncedSearch
              ? `No people found matching "${debouncedSearch}".`
              : 'No people data available yet.'
          }
          keyExtractor={(person) => person.personId}
          onRowClick={(person) => navigate(`/people/${person.personId}`)}
          pagination={
            peopleQuery.data
              ? {
                  page,
                  pageSize: PAGE_SIZE,
                  totalCount: peopleQuery.data.totalCount,
                  onPageChange: setPage,
                }
              : undefined
          }
        />
      )}
    </div>
  );
}
