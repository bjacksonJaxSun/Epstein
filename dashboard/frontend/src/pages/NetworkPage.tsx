import { useState, useCallback, useRef, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Search,
  Maximize2,
  RotateCcw,
  Info,
  ChevronDown,
  AlertCircle,
  Network,
  CircleDot,
} from 'lucide-react';
import { NetworkGraph } from '@/components/network/NetworkGraph';
import { NetworkLegend } from '@/components/network/NetworkLegend';
import { HeatMap, type FrequencyMetric } from '@/components/network/HeatMap';
import { useNetworkGraph, useEntitySearch } from '@/hooks/useNetwork';
import { peopleApi } from '@/api/endpoints/people';
import { cn } from '@/lib/utils';
import type { EntitySearchResult } from '@/types';

type ViewMode = 'network' | 'heatmap';

const DEPTH_OPTIONS = [1, 2, 3] as const;

const LAYOUT_OPTIONS = [
  { value: 'cose', label: 'Force-Directed' },
  { value: 'breadthfirst', label: 'Hierarchical' },
  { value: 'circle', label: 'Circular' },
  { value: 'grid', label: 'Grid' },
] as const;

const METRIC_OPTIONS: { value: FrequencyMetric; label: string }[] = [
  { value: 'total', label: 'Total Mentions' },
  { value: 'documents', label: 'Documents' },
  { value: 'events', label: 'Events' },
  { value: 'relationships', label: 'Relationships' },
  { value: 'financialCount', label: 'Financial Transactions' },
  { value: 'financialTotal', label: 'Financial Amount' },
  { value: 'media', label: 'Media' },
];

// Default to Jeffrey Epstein to show data on initial load
const DEFAULT_PERSON: EntitySearchResult = {
  id: 3,
  name: 'Jeffrey Epstein',
  entityType: 'person',
};

export function NetworkPage() {
  const [viewMode, setViewMode] = useState<ViewMode>('heatmap');
  const [searchQuery, setSearchQuery] = useState(DEFAULT_PERSON.name);
  const [selectedPerson, setSelectedPerson] = useState<EntitySearchResult | null>(DEFAULT_PERSON);
  const [depth, setDepth] = useState(2);
  const [layoutName, setLayoutName] = useState('cose');
  const [metric, setMetric] = useState<FrequencyMetric>('total');
  const [showLegend, setShowLegend] = useState(false);
  const [showLayoutDropdown, setShowLayoutDropdown] = useState(false);
  const [showMetricDropdown, setShowMetricDropdown] = useState(false);
  const [showSearchResults, setShowSearchResults] = useState(false);

  const searchInputRef = useRef<HTMLInputElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const metricDropdownRef = useRef<HTMLDivElement>(null);
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

  const {
    data: frequencyData,
    isLoading: isLoadingFrequencies,
    isError: isFrequencyError,
  } = useQuery({
    queryKey: ['frequencies'],
    queryFn: () => peopleApi.getFrequencies(500),
    enabled: viewMode === 'heatmap',
  });

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
    (nodeId: string, nodeType: string, label: string) => {
      if (nodeType === 'person') {
        const numericId = parseInt(nodeId, 10);
        if (!isNaN(numericId)) {
          setSelectedPerson({ id: numericId, name: label, entityType: 'person' });
          setSearchQuery(label);
        }
      }
    },
    []
  );

  const handleHeatMapNodeClick = useCallback((id: number, name: string) => {
    setSelectedPerson({ id, name, entityType: 'person' });
    setSearchQuery(name);
    setViewMode('network');
  }, []);

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
      if (metricDropdownRef.current && !metricDropdownRef.current.contains(target)) {
        setShowMetricDropdown(false);
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
  const currentMetric = METRIC_OPTIONS.find((m) => m.value === metric);

  return (
    <div className="flex h-full flex-col gap-4">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-xl font-semibold text-text-primary">
            {viewMode === 'network' ? 'Network Graph' : 'Heat Map'}
          </h2>
          <p className="mt-1 text-sm text-text-secondary">
            {viewMode === 'network'
              ? 'Interactive relationship network visualization powered by Cytoscape.js'
              : 'Entity frequency visualization - circle size represents frequency count'}
          </p>
        </div>

        {/* View Mode Toggle */}
        <div className="flex rounded-lg border border-border-subtle p-0.5 bg-surface-sunken">
          <button
            type="button"
            onClick={() => setViewMode('heatmap')}
            className={cn(
              'flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors',
              viewMode === 'heatmap'
                ? 'bg-accent-blue text-white'
                : 'text-text-secondary hover:text-text-primary'
            )}
          >
            <CircleDot className="h-3.5 w-3.5" />
            Heat Map
          </button>
          <button
            type="button"
            onClick={() => setViewMode('network')}
            className={cn(
              'flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors',
              viewMode === 'network'
                ? 'bg-accent-blue text-white'
                : 'text-text-secondary hover:text-text-primary'
            )}
          >
            <Network className="h-3.5 w-3.5" />
            Network
          </button>
        </div>
      </div>

      {/* Controls Bar */}
      <div className="flex flex-wrap items-center gap-3 rounded-lg border border-border-subtle bg-surface-raised px-4 py-3">
        {viewMode === 'network' && (
          <>
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
          </>
        )}

        {viewMode === 'heatmap' && (
          <>
            {/* Metric Selector */}
            <div className="flex items-center gap-1.5">
              <span className="text-xs font-medium text-text-tertiary">Size by:</span>
              <div className="relative" ref={metricDropdownRef}>
                <button
                  type="button"
                  onClick={() => setShowMetricDropdown((v) => !v)}
                  className="flex items-center gap-1.5 rounded-md border border-border-subtle bg-surface-sunken px-2.5 py-1.5 text-xs font-medium text-text-secondary transition-colors hover:bg-surface-overlay"
                >
                  <span>{currentMetric?.label ?? 'Select Metric'}</span>
                  <ChevronDown className="h-3.5 w-3.5" />
                </button>
                {showMetricDropdown && (
                  <div className="absolute left-0 top-full z-30 mt-1 min-w-[200px] rounded-md border border-border-subtle bg-surface-overlay shadow-lg">
                    {METRIC_OPTIONS.map((option) => (
                      <button
                        key={option.value}
                        type="button"
                        onClick={() => {
                          setMetric(option.value);
                          setShowMetricDropdown(false);
                        }}
                        className={cn(
                          'flex w-full items-center px-3 py-2 text-left text-xs transition-colors',
                          metric === option.value
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
            </div>

            {/* Separator */}
            <div className="hidden h-6 w-px bg-border-subtle sm:block" />

            {/* Info text */}
            <span className="text-xs text-text-tertiary">
              Click a circle to view network connections
            </span>
          </>
        )}
      </div>

      {/* Error state */}
      {viewMode === 'network' && isNetworkError && (
        <div className="flex items-center gap-3 rounded-lg border border-accent-red/30 bg-accent-red/5 px-4 py-3">
          <AlertCircle className="h-5 w-5 shrink-0 text-accent-red" />
          <p className="text-sm text-accent-red">
            Failed to load network data. Please try again or select a different person.
          </p>
        </div>
      )}

      {viewMode === 'heatmap' && isFrequencyError && (
        <div className="flex items-center gap-3 rounded-lg border border-accent-red/30 bg-accent-red/5 px-4 py-3">
          <AlertCircle className="h-5 w-5 shrink-0 text-accent-red" />
          <p className="text-sm text-accent-red">
            Failed to load frequency data. Please try again.
          </p>
        </div>
      )}

      {/* Graph/HeatMap Canvas */}
      <div className="relative flex-1" style={{ minHeight: '500px' }}>
        {viewMode === 'network' && (
          <>
            <NetworkLegend visible={showLegend} />
            <NetworkGraph
              data={networkData}
              isLoading={isLoadingNetwork}
              layoutName={layoutName}
              onDoubleClickNode={handleDoubleClickNode}
            />
          </>
        )}

        {viewMode === 'heatmap' && (
          <HeatMap
            data={frequencyData}
            isLoading={isLoadingFrequencies}
            metric={metric}
            onNodeClick={handleHeatMapNodeClick}
          />
        )}
      </div>
    </div>
  );
}
