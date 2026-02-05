import { useState, useCallback, useRef, useEffect } from 'react';
import {
  Search,
  Maximize2,
  RotateCcw,
  Info,
  ChevronDown,
  AlertCircle,
} from 'lucide-react';
import { NetworkGraph } from '@/components/network/NetworkGraph';
import { NetworkLegend } from '@/components/network/NetworkLegend';
import { useNetworkGraph, useEntitySearch } from '@/hooks/useNetwork';
import { cn } from '@/lib/utils';
import type { EntitySearchResult } from '@/types';

const DEPTH_OPTIONS = [1, 2, 3] as const;

const LAYOUT_OPTIONS = [
  { value: 'cose', label: 'Force-Directed' },
  { value: 'breadthfirst', label: 'Hierarchical' },
  { value: 'circle', label: 'Circular' },
  { value: 'grid', label: 'Grid' },
] as const;

export function NetworkPage() {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedPerson, setSelectedPerson] = useState<EntitySearchResult | null>(null);
  const [depth, setDepth] = useState(2);
  const [layoutName, setLayoutName] = useState('cose');
  const [showLegend, setShowLegend] = useState(false);
  const [showLayoutDropdown, setShowLayoutDropdown] = useState(false);
  const [showSearchResults, setShowSearchResults] = useState(false);

  const searchInputRef = useRef<HTMLInputElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const searchDropdownRef = useRef<HTMLDivElement>(null);

  const {
    data: searchResults,
    isLoading: isSearching,
  } = useEntitySearch(searchQuery);

  const {
    data: networkData,
    isLoading: isLoadingNetwork,
    isError: isNetworkError,
  } = useNetworkGraph(selectedPerson?.id ?? null, depth);

  const handleSearchChange = useCallback((value: string) => {
    setSearchQuery(value);
    setShowSearchResults(value.length >= 2);
  }, []);

  const handleSelectPerson = useCallback((result: EntitySearchResult) => {
    setSelectedPerson(result);
    setSearchQuery(result.name);
    setShowSearchResults(false);
  }, []);

  const handleDoubleClickNode = useCallback(
    (nodeId: string, nodeType: string) => {
      if (nodeType === 'person') {
        const numericId = parseInt(nodeId, 10);
        if (!isNaN(numericId)) {
          setSelectedPerson({ id: numericId, name: nodeId, entityType: 'person' });
          setSearchQuery(nodeId);
        }
      }
    },
    []
  );

  const handleFit = useCallback(() => {
    window.dispatchEvent(new Event('network-fit'));
  }, []);

  const handleReset = useCallback(() => {
    window.dispatchEvent(new Event('network-reset'));
  }, []);

  // Close dropdowns when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      const target = event.target as Node;
      if (dropdownRef.current && !dropdownRef.current.contains(target)) {
        setShowLayoutDropdown(false);
      }
      if (
        searchDropdownRef.current &&
        !searchDropdownRef.current.contains(target) &&
        searchInputRef.current &&
        !searchInputRef.current.contains(target)
      ) {
        setShowSearchResults(false);
      }
    }

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const currentLayout = LAYOUT_OPTIONS.find((l) => l.value === layoutName);

  return (
    <div className="flex h-full flex-col gap-4">
      {/* Header */}
      <div>
        <h2 className="text-xl font-semibold text-text-primary">Network Graph</h2>
        <p className="mt-1 text-sm text-text-secondary">
          Interactive relationship network visualization powered by Cytoscape.js
        </p>
      </div>

      {/* Controls Bar */}
      <div className="flex flex-wrap items-center gap-3 rounded-lg border border-border-subtle bg-surface-raised px-4 py-3">
        {/* Person Search */}
        <div className="relative min-w-[240px] flex-1 max-w-md">
          <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-text-tertiary" />
          <input
            ref={searchInputRef}
            type="text"
            value={searchQuery}
            onChange={(e) => handleSearchChange(e.target.value)}
            onFocus={() => {
              if (searchQuery.length >= 2) setShowSearchResults(true);
            }}
            placeholder="Search for a person..."
            className="w-full rounded-md border border-border-subtle bg-surface-sunken py-1.5 pl-8 pr-3 text-sm text-text-primary placeholder:text-text-disabled focus:border-accent-blue focus:outline-none"
          />
          {/* Search Results Dropdown */}
          {showSearchResults && (
            <div
              ref={searchDropdownRef}
              className="absolute left-0 top-full z-30 mt-1 w-full rounded-md border border-border-subtle bg-surface-overlay shadow-lg"
            >
              {isSearching && (
                <div className="flex items-center gap-2 px-3 py-2.5">
                  <div className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-accent-blue border-t-transparent" />
                  <span className="text-xs text-text-tertiary">Searching...</span>
                </div>
              )}
              {!isSearching && searchResults && searchResults.length === 0 && (
                <div className="px-3 py-2.5 text-xs text-text-disabled">
                  No results found
                </div>
              )}
              {!isSearching &&
                searchResults &&
                searchResults.length > 0 &&
                searchResults.slice(0, 10).map((result) => (
                  <button
                    key={result.id}
                    type="button"
                    onClick={() => handleSelectPerson(result)}
                    className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-text-primary transition-colors hover:bg-surface-elevated"
                  >
                    <span
                      className="inline-block h-2 w-2 shrink-0 rounded-full"
                      style={{
                        backgroundColor:
                          result.entityType === 'person'
                            ? '#4A9EFF'
                            : result.entityType === 'organization'
                              ? '#A855F7'
                              : '#6B6B80',
                      }}
                    />
                    <span className="truncate">{result.name}</span>
                    {result.subtitle && (
                      <span className="ml-auto shrink-0 text-xs text-text-tertiary">
                        {result.subtitle}
                      </span>
                    )}
                  </button>
                ))}
            </div>
          )}
        </div>

        {/* Separator */}
        <div className="hidden h-6 w-px bg-border-subtle sm:block" />

        {/* Depth Selector */}
        <div className="flex items-center gap-1.5">
          <span className="text-xs font-medium text-text-tertiary">Depth:</span>
          <div className="flex rounded-md border border-border-subtle">
            {DEPTH_OPTIONS.map((d) => (
              <button
                key={d}
                type="button"
                onClick={() => setDepth(d)}
                className={cn(
                  'px-2.5 py-1 text-xs font-medium transition-colors',
                  'first:rounded-l-md last:rounded-r-md',
                  depth === d
                    ? 'bg-accent-blue text-surface-base'
                    : 'bg-surface-sunken text-text-secondary hover:bg-surface-overlay'
                )}
              >
                {d}
              </button>
            ))}
          </div>
        </div>

        {/* Separator */}
        <div className="hidden h-6 w-px bg-border-subtle sm:block" />

        {/* Layout Dropdown */}
        <div className="relative" ref={dropdownRef}>
          <button
            type="button"
            onClick={() => setShowLayoutDropdown((v) => !v)}
            className="flex items-center gap-1.5 rounded-md border border-border-subtle bg-surface-sunken px-2.5 py-1.5 text-xs font-medium text-text-secondary transition-colors hover:bg-surface-overlay"
          >
            <span>{currentLayout?.label ?? 'Layout'}</span>
            <ChevronDown className="h-3.5 w-3.5" />
          </button>
          {showLayoutDropdown && (
            <div className="absolute left-0 top-full z-30 mt-1 min-w-[160px] rounded-md border border-border-subtle bg-surface-overlay shadow-lg">
              {LAYOUT_OPTIONS.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => {
                    setLayoutName(option.value);
                    setShowLayoutDropdown(false);
                  }}
                  className={cn(
                    'flex w-full items-center px-3 py-2 text-left text-xs transition-colors',
                    layoutName === option.value
                      ? 'bg-accent-blue/10 text-accent-blue'
                      : 'text-text-secondary hover:bg-surface-elevated'
                  )}
                >
                  {option.label}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Separator */}
        <div className="hidden h-6 w-px bg-border-subtle sm:block" />

        {/* Action Buttons */}
        <div className="flex items-center gap-1.5">
          <button
            type="button"
            onClick={handleFit}
            title="Fit to viewport"
            className="rounded-md border border-border-subtle bg-surface-sunken p-1.5 text-text-secondary transition-colors hover:bg-surface-overlay hover:text-text-primary"
          >
            <Maximize2 className="h-3.5 w-3.5" />
          </button>
          <button
            type="button"
            onClick={handleReset}
            title="Reset graph"
            className="rounded-md border border-border-subtle bg-surface-sunken p-1.5 text-text-secondary transition-colors hover:bg-surface-overlay hover:text-text-primary"
          >
            <RotateCcw className="h-3.5 w-3.5" />
          </button>
          <button
            type="button"
            onClick={() => setShowLegend((v) => !v)}
            title="Toggle legend"
            className={cn(
              'rounded-md border border-border-subtle p-1.5 transition-colors',
              showLegend
                ? 'bg-accent-blue/15 text-accent-blue border-accent-blue/30'
                : 'bg-surface-sunken text-text-secondary hover:bg-surface-overlay hover:text-text-primary'
            )}
          >
            <Info className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      {/* Error state */}
      {isNetworkError && (
        <div className="flex items-center gap-3 rounded-lg border border-accent-red/30 bg-accent-red/5 px-4 py-3">
          <AlertCircle className="h-5 w-5 shrink-0 text-accent-red" />
          <p className="text-sm text-accent-red">
            Failed to load network data. Please try again or select a different person.
          </p>
        </div>
      )}

      {/* Graph Canvas */}
      <div className="relative flex-1" style={{ minHeight: '500px' }}>
        <NetworkLegend visible={showLegend} />
        <NetworkGraph
          data={networkData}
          isLoading={isLoadingNetwork}
          layoutName={layoutName}
          onDoubleClickNode={handleDoubleClickNode}
        />
      </div>
    </div>
  );
}
