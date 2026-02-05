import { useState, useCallback, useEffect, useRef, useMemo } from 'react';
import { useNavigate } from 'react-router';
import {
  Search,
  Pin,
  Settings,
  User,
  Building2,
  MapPin,
  Calendar,
  FileText,
  Clock,
  X,
  ArrowRight,
} from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { searchApi } from '@/api/endpoints/search';
import { useBookmarkStore } from '@/stores/useBookmarkStore';
import { cn } from '@/lib/utils';
import type { EntitySearchResult } from '@/types';

const RECENT_SEARCHES_KEY = 'recent-searches';
const MAX_RECENT = 10;

const entityIcons: Record<string, typeof User> = {
  person: User,
  organization: Building2,
  location: MapPin,
  event: Calendar,
  document: FileText,
};

const entityColors: Record<string, string> = {
  person: 'text-entity-person bg-entity-person/15',
  organization: 'text-entity-organization bg-entity-organization/15',
  location: 'text-entity-location bg-entity-location/15',
  event: 'text-entity-event bg-entity-event/15',
  document: 'text-entity-document bg-entity-document/15',
};

function getRecentSearches(): string[] {
  try {
    const stored = localStorage.getItem(RECENT_SEARCHES_KEY);
    if (stored) {
      return JSON.parse(stored) as string[];
    }
  } catch {
    // ignore parse errors
  }
  return [];
}

function addRecentSearch(query: string) {
  const trimmed = query.trim();
  if (!trimmed) return;
  const current = getRecentSearches();
  const filtered = current.filter((s) => s !== trimmed);
  const updated = [trimmed, ...filtered].slice(0, MAX_RECENT);
  localStorage.setItem(RECENT_SEARCHES_KEY, JSON.stringify(updated));
}

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

const typeLabels: Record<string, string> = {
  person: 'People',
  organization: 'Organizations',
  document: 'Documents',
  event: 'Events',
  location: 'Locations',
};

export function Header() {
  const navigate = useNavigate();
  const bookmarkCount = useBookmarkStore((s) => s.bookmarks.length);
  const [focused, setFocused] = useState(false);
  const [searchText, setSearchText] = useState('');
  const [debouncedQuery, setDebouncedQuery] = useState('');
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const [recentSearches, setRecentSearches] = useState<string[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Debounce the search query
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedQuery(searchText.trim());
    }, 200);
    return () => clearTimeout(timer);
  }, [searchText]);

  // Fetch search results
  const { data: searchResults } = useQuery<EntitySearchResult[]>({
    queryKey: ['global-search', debouncedQuery],
    queryFn: () => searchApi.entities({ query: debouncedQuery }),
    enabled: debouncedQuery.length >= 2,
    staleTime: 15_000,
  });

  const grouped = useMemo(() => {
    if (!searchResults || searchResults.length === 0) return {};
    return groupByType(searchResults);
  }, [searchResults]);

  // Build flat list for keyboard navigation
  const flatResults = useMemo(() => {
    const items: EntitySearchResult[] = [];
    for (const type of Object.keys(typeLabels)) {
      if (grouped[type]) {
        items.push(...grouped[type]);
      }
    }
    return items;
  }, [grouped]);

  const hasResults = flatResults.length > 0;
  const showRecent = focused && !searchText && recentSearches.length > 0;
  const showResults = focused && debouncedQuery.length >= 2;

  // Ctrl+K / Cmd+K to focus
  useEffect(() => {
    function handleGlobalKeyDown(e: KeyboardEvent) {
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        inputRef.current?.focus();
      }
    }
    document.addEventListener('keydown', handleGlobalKeyDown);
    return () => document.removeEventListener('keydown', handleGlobalKeyDown);
  }, []);

  // Load recent searches when focused
  useEffect(() => {
    if (focused) {
      setRecentSearches(getRecentSearches());
    }
  }, [focused]);

  // Close dropdown on click outside
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(e.target as Node) &&
        inputRef.current &&
        !inputRef.current.contains(e.target as Node)
      ) {
        setDropdownOpen(false);
        setFocused(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Reset active index on results change
  useEffect(() => {
    setActiveIndex(-1);
  }, [debouncedQuery]);

  const handleFocus = useCallback(() => {
    setFocused(true);
    setDropdownOpen(true);
  }, []);

  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      setSearchText(e.target.value);
      setDropdownOpen(true);
    },
    []
  );

  const navigateToEntity = useCallback(
    (result: EntitySearchResult) => {
      addRecentSearch(result.name);
      setDropdownOpen(false);
      setFocused(false);
      setSearchText('');
      if (result.entityType === 'person') {
        navigate(`/people/${result.id}`);
      } else if (result.entityType === 'document') {
        navigate(`/documents`);
      } else if (result.entityType === 'organization') {
        navigate(`/organizations`);
      } else if (result.entityType === 'event') {
        navigate(`/timeline`);
      } else if (result.entityType === 'location') {
        navigate(`/locations`);
      }
    },
    [navigate]
  );

  const handleViewAll = useCallback(() => {
    if (searchText.trim()) {
      addRecentSearch(searchText.trim());
      navigate(`/search?q=${encodeURIComponent(searchText.trim())}`);
      setDropdownOpen(false);
      setFocused(false);
    }
  }, [searchText, navigate]);

  const handleRecentClick = useCallback(
    (query: string) => {
      setSearchText(query);
      setDropdownOpen(true);
    },
    []
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Escape') {
        setDropdownOpen(false);
        inputRef.current?.blur();
        setFocused(false);
        return;
      }

      if (showRecent) {
        if (e.key === 'ArrowDown') {
          e.preventDefault();
          setActiveIndex((prev) =>
            prev < recentSearches.length - 1 ? prev + 1 : 0
          );
        } else if (e.key === 'ArrowUp') {
          e.preventDefault();
          setActiveIndex((prev) =>
            prev > 0 ? prev - 1 : recentSearches.length - 1
          );
        } else if (e.key === 'Enter' && activeIndex >= 0) {
          e.preventDefault();
          handleRecentClick(recentSearches[activeIndex]);
          setActiveIndex(-1);
        }
        return;
      }

      if (!hasResults) return;

      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setActiveIndex((prev) =>
          prev < flatResults.length - 1 ? prev + 1 : 0
        );
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setActiveIndex((prev) =>
          prev > 0 ? prev - 1 : flatResults.length - 1
        );
      } else if (e.key === 'Enter') {
        e.preventDefault();
        if (activeIndex >= 0 && activeIndex < flatResults.length) {
          navigateToEntity(flatResults[activeIndex]);
        } else {
          handleViewAll();
        }
      }
    },
    [showRecent, hasResults, activeIndex, flatResults, recentSearches, navigateToEntity, handleViewAll, handleRecentClick]
  );

  const showDropdown = dropdownOpen && (showRecent || showResults);

  return (
    <header className="flex h-14 shrink-0 items-center gap-4 border-b border-border-subtle bg-surface-raised px-4">
      {/* App title */}
      <h1 className="hidden text-sm font-semibold uppercase tracking-widest text-text-secondary lg:block">
        Investigative Dashboard
      </h1>

      {/* Spacer */}
      <div className="flex-1" />

      {/* Search */}
      <div className="relative w-full max-w-md">
        <div
          className={cn(
            'relative flex items-center rounded-md border bg-surface-base transition-colors',
            focused ? 'border-accent-blue' : 'border-border-subtle'
          )}
        >
          <Search className="ml-3 h-4 w-4 shrink-0 text-text-tertiary" />
          <input
            ref={inputRef}
            type="text"
            value={searchText}
            onChange={handleChange}
            onFocus={handleFocus}
            onKeyDown={handleKeyDown}
            placeholder="Search documents, people, events..."
            className="w-full bg-transparent px-3 py-2 text-sm text-text-primary placeholder:text-text-disabled focus:outline-none"
            role="combobox"
            aria-expanded={showDropdown}
            aria-haspopup="listbox"
            aria-activedescendant={
              activeIndex >= 0 ? `search-result-${activeIndex}` : undefined
            }
          />
          {searchText ? (
            <button
              type="button"
              onClick={() => {
                setSearchText('');
                inputRef.current?.focus();
              }}
              className="mr-2 flex h-5 w-5 items-center justify-center rounded text-text-tertiary hover:text-text-primary"
              aria-label="Clear search"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          ) : (
            <kbd className="mr-3 hidden rounded border border-border-default bg-surface-overlay px-1.5 py-0.5 text-[10px] font-medium text-text-tertiary sm:inline-block">
              Ctrl+K
            </kbd>
          )}
        </div>

        {/* Search Dropdown */}
        {showDropdown && (
          <div
            ref={dropdownRef}
            className="absolute left-0 right-0 top-full z-50 mt-1 max-h-[420px] overflow-y-auto rounded-lg border border-border-subtle bg-surface-raised shadow-xl"
            role="listbox"
          >
            {/* Recent Searches */}
            {showRecent && (
              <div className="p-2">
                <p className="mb-1 px-2 text-xs font-medium uppercase tracking-wider text-text-tertiary">
                  Recent Searches
                </p>
                {recentSearches.map((query, i) => (
                  <button
                    key={query}
                    id={`search-result-${i}`}
                    type="button"
                    onClick={() => handleRecentClick(query)}
                    className={cn(
                      'flex w-full items-center gap-2.5 rounded-md px-2 py-1.5 text-left text-sm transition-colors',
                      activeIndex === i
                        ? 'bg-surface-overlay text-text-primary'
                        : 'text-text-secondary hover:bg-surface-overlay hover:text-text-primary'
                    )}
                    role="option"
                    aria-selected={activeIndex === i}
                  >
                    <Clock className="h-3.5 w-3.5 shrink-0 text-text-tertiary" />
                    <span className="truncate">{query}</span>
                  </button>
                ))}
              </div>
            )}

            {/* Search Results */}
            {showResults && !hasResults && debouncedQuery.length >= 2 && (
              <div className="flex flex-col items-center gap-2 px-4 py-8">
                <Search className="h-8 w-8 text-text-disabled" />
                <p className="text-sm text-text-disabled">
                  No results found for &quot;{debouncedQuery}&quot;
                </p>
              </div>
            )}

            {showResults && hasResults && (
              <>
                {Object.entries(typeLabels).map(([type, label]) => {
                  const items = grouped[type];
                  if (!items || items.length === 0) return null;
                  const Icon = entityIcons[type] ?? FileText;
                  return (
                    <div key={type} className="p-2">
                      <div className="mb-1 flex items-center gap-2 px-2">
                        <p className="text-xs font-medium uppercase tracking-wider text-text-tertiary">
                          {label}
                        </p>
                        <span className="flex h-4 min-w-[16px] items-center justify-center rounded-full bg-surface-overlay px-1 text-[10px] font-semibold text-text-tertiary">
                          {items.length}
                        </span>
                      </div>
                      {items.map((result) => {
                        const globalIdx = flatResults.indexOf(result);
                        return (
                          <button
                            key={`${result.entityType}-${result.id}`}
                            id={`search-result-${globalIdx}`}
                            type="button"
                            onClick={() => navigateToEntity(result)}
                            className={cn(
                              'flex w-full items-center gap-2.5 rounded-md px-2 py-1.5 text-left text-sm transition-colors',
                              activeIndex === globalIdx
                                ? 'bg-surface-overlay text-text-primary'
                                : 'text-text-secondary hover:bg-surface-overlay hover:text-text-primary'
                            )}
                            role="option"
                            aria-selected={activeIndex === globalIdx}
                          >
                            <div
                              className={cn(
                                'flex h-6 w-6 shrink-0 items-center justify-center rounded',
                                entityColors[type] ?? entityColors.document
                              )}
                            >
                              <Icon className="h-3.5 w-3.5" />
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
                        );
                      })}
                    </div>
                  );
                })}

                {/* View all results */}
                <div className="border-t border-border-subtle p-2">
                  <button
                    type="button"
                    onClick={handleViewAll}
                    className="flex w-full items-center justify-between rounded-md px-2 py-1.5 text-sm font-medium text-accent-blue transition-colors hover:bg-surface-overlay"
                  >
                    <span>View all results</span>
                    <ArrowRight className="h-4 w-4" />
                  </button>
                </div>
              </>
            )}
          </div>
        )}
      </div>

      {/* Spacer */}
      <div className="flex-1" />

      {/* Actions */}
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={() => navigate('/bookmarks')}
          className="relative flex h-8 w-8 items-center justify-center rounded-md text-text-secondary transition-colors hover:bg-surface-overlay hover:text-text-primary"
          aria-label="Bookmarks"
        >
          <Pin className="h-4 w-4" />
          {bookmarkCount > 0 && (
            <span className="absolute -right-0.5 -top-0.5 flex h-4 w-4 items-center justify-center rounded-full bg-accent-blue text-[10px] font-bold text-white">
              {bookmarkCount > 99 ? '99' : bookmarkCount}
            </span>
          )}
        </button>
        <button
          type="button"
          onClick={() => navigate('/settings')}
          className="flex h-8 w-8 items-center justify-center rounded-md text-text-secondary transition-colors hover:bg-surface-overlay hover:text-text-primary"
          aria-label="Settings"
        >
          <Settings className="h-4 w-4" />
        </button>
      </div>
    </header>
  );
}
