import { useState, useMemo, useCallback } from 'react';
import {
  MapPin,
  AlertCircle,
  Globe,
  Navigation,
  PanelRightClose,
  PanelRightOpen,
  ChevronDown,
  Search,
  Calendar,
  Image,
  FileBox,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  FileText,
  ChevronLeft,
  ExternalLink,
} from 'lucide-react';
import { LocationMap } from '@/components/map/LocationMap';
import {
  useLocations,
  useLocationTypesList,
  useLocationCountries,
  useGeoLocatedCount,
  useLocationDocuments,
} from '@/hooks/useLocations';
import { LoadingSpinner, StatCard } from '@/components/shared';
import { cn } from '@/lib/utils';
import type { Location } from '@/api/endpoints/locations';

type SortField = 'locationName' | 'totalActivity' | 'eventCount' | 'mediaCount' | 'country';
type SortDirection = 'asc' | 'desc';

export function MapPage() {
  const [locationTypeFilter, setLocationTypeFilter] = useState<string>('');
  const [countryFilter, setCountryFilter] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [panelOpen, setPanelOpen] = useState(true);
  const [selectedLocation, setSelectedLocation] = useState<Location | null>(null);
  const [sortField, setSortField] = useState<SortField>('totalActivity');
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc');

  const { data, isLoading, isError } = useLocations({
    pageSize: 500,
    locationType: locationTypeFilter || undefined,
    country: countryFilter || undefined,
    sortBy: sortField,
    sortDirection,
  });

  const { data: locationTypes = [] } = useLocationTypesList();
  const { data: countries = [] } = useLocationCountries();

  const allLocations = data?.items ?? [];
  const stats = useGeoLocatedCount(allLocations);

  // Client-side search filtering
  const filteredLocations = useMemo(() => {
    if (!searchQuery.trim()) return allLocations;
    const query = searchQuery.toLowerCase();
    return allLocations.filter(
      (l) =>
        l.locationName.toLowerCase().includes(query) ||
        l.city?.toLowerCase().includes(query) ||
        l.country?.toLowerCase().includes(query) ||
        l.description?.toLowerCase().includes(query)
    );
  }, [allLocations, searchQuery]);

  const geoLocated = useMemo(
    () => filteredLocations.filter((l) => l.gpsLatitude != null && l.gpsLongitude != null),
    [filteredLocations]
  );

  const handleLocationSelect = useCallback(
    (loc: Location) => {
      setSelectedLocation(loc);
      if (!panelOpen) setPanelOpen(true);
    },
    [panelOpen]
  );

  const handleSort = useCallback((field: SortField) => {
    setSortField((current) => {
      if (current === field) {
        setSortDirection((dir) => (dir === 'asc' ? 'desc' : 'asc'));
        return current;
      }
      setSortDirection('desc');
      return field;
    });
  }, []);

  return (
    <div className="flex flex-col gap-4 h-full">
      {/* Header */}
      <div>
        <h2 className="text-xl font-semibold text-text-primary">Map View</h2>
        <p className="mt-1 text-sm text-text-secondary">
          Geographic visualization of locations mentioned in documents. Marker size indicates
          activity level.
        </p>
      </div>

      {/* Stats Row */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-5">
        <StatCard
          label="Total Locations"
          value={stats.total}
          icon={MapPin}
          iconColor="text-entity-location"
        />
        <StatCard
          label="Mapped"
          value={stats.geoLocated}
          icon={Navigation}
          iconColor="text-accent-cyan"
          trend={
            stats.total > 0
              ? `${Math.round((stats.geoLocated / stats.total) * 100)}%`
              : undefined
          }
        />
        <StatCard
          label="Countries"
          value={stats.countries}
          icon={Globe}
          iconColor="text-accent-amber"
        />
        <StatCard
          label="Total Events"
          value={stats.totalEvents}
          icon={Calendar}
          iconColor="text-accent-blue"
        />
        <StatCard
          label="Total Media"
          value={stats.totalMedia}
          icon={Image}
          iconColor="text-accent-purple"
        />
      </div>

      {/* Filter Bar */}
      <div className="flex flex-wrap items-center gap-3 rounded-lg border border-border-subtle bg-surface-raised p-3">
        {/* Search */}
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-text-tertiary" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search locations..."
            className="w-full rounded-md border border-border-subtle bg-surface-overlay py-1.5 pl-8 pr-3 text-xs text-text-primary placeholder:text-text-disabled focus:border-accent-blue focus:outline-none"
          />
        </div>

        {/* Location Type Filter */}
        <div className="relative">
          <select
            value={locationTypeFilter}
            onChange={(e) => setLocationTypeFilter(e.target.value)}
            className="appearance-none rounded-md border border-border-subtle bg-surface-overlay px-3 py-1.5 pr-8 text-xs text-text-primary focus:border-accent-blue focus:outline-none"
          >
            <option value="">All Types</option>
            {locationTypes.map((type) => (
              <option key={type} value={type}>
                {type}
              </option>
            ))}
          </select>
          <ChevronDown className="pointer-events-none absolute right-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-text-tertiary" />
        </div>

        {/* Country Filter */}
        <div className="relative">
          <select
            value={countryFilter}
            onChange={(e) => setCountryFilter(e.target.value)}
            className="appearance-none rounded-md border border-border-subtle bg-surface-overlay px-3 py-1.5 pr-8 text-xs text-text-primary focus:border-accent-blue focus:outline-none"
          >
            <option value="">All Countries</option>
            {countries.map((country) => (
              <option key={country} value={country}>
                {country}
              </option>
            ))}
          </select>
          <ChevronDown className="pointer-events-none absolute right-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-text-tertiary" />
        </div>

        <div className="ml-auto">
          <button
            type="button"
            onClick={() => setPanelOpen((v) => !v)}
            className="flex items-center gap-1.5 rounded-md border border-border-subtle px-2.5 py-1.5 text-xs text-text-secondary transition-colors hover:bg-surface-overlay"
          >
            {panelOpen ? (
              <>
                <PanelRightClose className="h-3.5 w-3.5" />
                Hide Panel
              </>
            ) : (
              <>
                <PanelRightOpen className="h-3.5 w-3.5" />
                Show Panel
              </>
            )}
          </button>
        </div>
      </div>

      {/* Map + Location Panel */}
      {isLoading && <LoadingSpinner className="py-24" />}

      {isError && (
        <div className="flex flex-col items-center justify-center gap-3 py-16">
          <AlertCircle className="h-8 w-8 text-accent-red" />
          <p className="text-sm text-accent-red">Failed to load location data.</p>
        </div>
      )}

      {!isLoading && !isError && geoLocated.length === 0 && (
        <div className="flex flex-col items-center justify-center gap-3 rounded-lg border border-border-subtle bg-surface-raised py-16">
          <MapPin className="h-10 w-10 text-text-disabled" />
          <p className="text-sm text-text-disabled">No geolocated data available.</p>
          <p className="text-xs text-text-disabled max-w-md text-center">
            Locations without GPS coordinates cannot be displayed on the map.
            {filteredLocations.length > 0 &&
              ` ${filteredLocations.length} locations exist without coordinates.`}
          </p>
        </div>
      )}

      {!isLoading && !isError && geoLocated.length > 0 && (
        <div className="flex flex-1 gap-0 rounded-lg border border-border-subtle bg-surface-raised overflow-hidden min-h-[500px]">
          {/* Map */}
          <div className={cn('flex-1 relative', panelOpen ? '' : 'w-full')}>
            <LocationMap
              locations={filteredLocations}
              onLocationSelect={handleLocationSelect}
              sizeByActivity={true}
            />

            {/* Legend */}
            <div className="absolute bottom-4 left-4 rounded-lg border border-border-subtle bg-surface-overlay/90 p-3 backdrop-blur-sm">
              <p className="text-[10px] font-medium text-text-tertiary uppercase tracking-wider mb-2">
                Activity Level
              </p>
              <div className="flex items-center gap-3">
                <div className="flex items-center gap-1.5">
                  <div
                    className="w-5 h-5 rounded-full"
                    style={{ backgroundColor: '#22C55E' }}
                  />
                  <span className="text-[10px] text-text-tertiary">None</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <div
                    className="w-6 h-6 rounded-full"
                    style={{ backgroundColor: '#4A9EFF' }}
                  />
                  <span className="text-[10px] text-text-tertiary">Low</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <div
                    className="w-8 h-8 rounded-full"
                    style={{ backgroundColor: '#A855F7' }}
                  />
                  <span className="text-[10px] text-text-tertiary">Medium</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <div
                    className="w-10 h-10 rounded-full"
                    style={{ backgroundColor: '#F97316' }}
                  />
                  <span className="text-[10px] text-text-tertiary">High</span>
                </div>
              </div>
            </div>
          </div>

          {/* Side Panel */}
          {panelOpen && (
            <div className="w-96 flex-shrink-0 border-l border-border-subtle bg-surface-raised overflow-hidden flex flex-col">
              {selectedLocation ? (
                <LocationDetailPanel
                  location={selectedLocation}
                  onBack={() => setSelectedLocation(null)}
                />
              ) : (
                <>
                  {/* Panel Header with Sort Options */}
                  <div className="border-b border-border-subtle px-4 py-3 flex-shrink-0">
                    <div className="flex items-center justify-between">
                      <h3 className="text-xs font-semibold uppercase tracking-wider text-text-tertiary">
                        Locations ({geoLocated.length})
                      </h3>
                    </div>

                    {/* Sort buttons */}
                    <div className="flex flex-wrap gap-1 mt-2">
                      <SortButton
                        label="Name"
                        field="locationName"
                        currentField={sortField}
                        direction={sortDirection}
                        onClick={() => handleSort('locationName')}
                      />
                      <SortButton
                        label="Activity"
                        field="totalActivity"
                        currentField={sortField}
                        direction={sortDirection}
                        onClick={() => handleSort('totalActivity')}
                      />
                      <SortButton
                        label="Events"
                        field="eventCount"
                        currentField={sortField}
                        direction={sortDirection}
                        onClick={() => handleSort('eventCount')}
                      />
                      <SortButton
                        label="Media"
                        field="mediaCount"
                        currentField={sortField}
                        direction={sortDirection}
                        onClick={() => handleSort('mediaCount')}
                      />
                    </div>
                  </div>

                  {/* Scrollable location list */}
                  <div className="flex-1 overflow-y-auto divide-y divide-border-subtle">
                    {geoLocated.map((loc) => (
                      <LocationListItem
                        key={loc.locationId}
                        location={loc}
                        isSelected={false}
                        onClick={() => handleLocationSelect(loc)}
                      />
                    ))}
                  </div>
                </>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Sub-components                                                      */
/* ------------------------------------------------------------------ */

function SortButton({
  label,
  field,
  currentField,
  direction,
  onClick,
}: {
  label: string;
  field: SortField;
  currentField: SortField;
  direction: SortDirection;
  onClick: () => void;
}) {
  const isActive = field === currentField;

  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'flex items-center gap-1 rounded px-2 py-1 text-[10px] transition-colors',
        isActive
          ? 'bg-accent-blue/20 text-accent-blue'
          : 'text-text-tertiary hover:bg-surface-overlay'
      )}
    >
      {label}
      {isActive ? (
        direction === 'asc' ? (
          <ArrowUp className="h-2.5 w-2.5" />
        ) : (
          <ArrowDown className="h-2.5 w-2.5" />
        )
      ) : (
        <ArrowUpDown className="h-2.5 w-2.5 opacity-40" />
      )}
    </button>
  );
}

function LocationDetailPanel({
  location,
  onBack,
}: {
  location: Location;
  onBack: () => void;
}) {
  const { data: documents, isLoading } = useLocationDocuments(location.locationId);

  const addressParts = [
    location.city,
    location.stateProvince,
    location.country,
  ].filter(Boolean);

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="border-b border-border-subtle px-4 py-3 flex-shrink-0">
        <button
          type="button"
          onClick={onBack}
          className="flex items-center gap-1 text-xs text-text-secondary hover:text-text-primary mb-2"
        >
          <ChevronLeft className="h-3.5 w-3.5" />
          Back to list
        </button>
        <h3 className="text-sm font-semibold text-text-primary">
          {location.locationName}
        </h3>
        {location.locationType && (
          <span className="inline-flex mt-1 items-center rounded-sm border border-border-subtle bg-surface-sunken px-1.5 py-0.5 text-[10px] text-text-tertiary">
            {location.locationType}
          </span>
        )}
        {addressParts.length > 0 && (
          <p className="mt-1 text-xs text-text-tertiary">
            {addressParts.join(', ')}
          </p>
        )}
        {location.description && (
          <p className="mt-2 text-xs text-text-secondary line-clamp-3">
            {location.description}
          </p>
        )}
      </div>

      {/* Stats */}
      <div className="px-4 py-3 border-b border-border-subtle flex-shrink-0">
        <div className="grid grid-cols-3 gap-2 text-center">
          <div>
            <p className="text-lg font-semibold text-accent-blue">
              {location.eventCount ?? 0}
            </p>
            <p className="text-[10px] text-text-tertiary">Events</p>
          </div>
          <div>
            <p className="text-lg font-semibold text-accent-purple">
              {location.mediaCount ?? 0}
            </p>
            <p className="text-[10px] text-text-tertiary">Media</p>
          </div>
          <div>
            <p className="text-lg font-semibold text-accent-amber">
              {location.evidenceCount ?? 0}
            </p>
            <p className="text-[10px] text-text-tertiary">Evidence</p>
          </div>
        </div>
      </div>

      {/* Documents */}
      <div className="flex-1 overflow-y-auto">
        <div className="px-4 py-2 border-b border-border-subtle bg-surface-sunken sticky top-0">
          <div className="flex items-center gap-1.5">
            <FileText className="h-3.5 w-3.5 text-text-tertiary" />
            <h4 className="text-xs font-medium text-text-secondary">
              Related Documents
              {documents && ` (${documents.length})`}
            </h4>
          </div>
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <LoadingSpinner />
          </div>
        ) : documents && documents.length > 0 ? (
          <div className="divide-y divide-border-subtle">
            {documents.map((doc) => (
              <a
                key={doc.documentId}
                href={`/api/documents/${doc.documentId}/file`}
                target="_blank"
                rel="noopener noreferrer"
                className="block px-4 py-3 hover:bg-surface-overlay transition-colors group"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-medium text-text-primary truncate group-hover:text-accent-blue">
                      {doc.documentTitle || doc.eftaNumber || `Document ${doc.documentId}`}
                    </p>
                    {doc.documentType && (
                      <span className="inline-flex mt-1 items-center rounded-sm border border-border-subtle bg-surface-sunken px-1.5 py-0.5 text-[9px] text-text-tertiary">
                        {doc.documentType}
                      </span>
                    )}
                    {doc.documentDate && (
                      <p className="mt-1 text-[10px] text-text-tertiary">
                        {new Date(doc.documentDate).toLocaleDateString()}
                      </p>
                    )}
                    {doc.subject && (
                      <p className="mt-1 text-[10px] text-text-tertiary line-clamp-2">
                        {doc.subject}
                      </p>
                    )}
                  </div>
                  <ExternalLink className="h-3.5 w-3.5 text-text-disabled group-hover:text-accent-blue flex-shrink-0" />
                </div>
              </a>
            ))}
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center py-8 text-text-disabled">
            <FileText className="h-8 w-8 mb-2" />
            <p className="text-xs">No documents found</p>
          </div>
        )}
      </div>
    </div>
  );
}

function LocationListItem({
  location,
  isSelected,
  onClick,
}: {
  location: Location;
  isSelected: boolean;
  onClick: () => void;
}) {
  const addressParts = [location.city, location.stateProvince, location.country].filter(
    Boolean
  );

  const eventCount = location.eventCount ?? 0;
  const mediaCount = location.mediaCount ?? 0;
  const evidenceCount = location.evidenceCount ?? 0;
  const totalActivity = location.totalActivity ?? 0;

  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'w-full text-left px-4 py-3 transition-colors',
        isSelected
          ? 'bg-surface-overlay border-l-2 border-l-accent-blue'
          : 'hover:bg-surface-overlay'
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <p className="text-xs font-medium text-text-primary truncate">
            {location.locationName}
          </p>
          {location.locationType && (
            <span className="inline-flex mt-1 items-center rounded-sm border border-border-subtle bg-surface-sunken px-1.5 py-0.5 text-[10px] text-text-tertiary">
              {location.locationType}
            </span>
          )}
          {addressParts.length > 0 && (
            <p className="mt-1 text-[11px] text-text-tertiary truncate">
              {addressParts.join(', ')}
            </p>
          )}
        </div>

        {/* Activity indicator */}
        {totalActivity > 0 && (
          <div className="flex-shrink-0 text-right">
            <p className="text-sm font-semibold text-text-primary">{totalActivity}</p>
            <p className="text-[9px] text-text-tertiary">activity</p>
          </div>
        )}
      </div>

      {/* Stats row */}
      {totalActivity > 0 && (
        <div className="flex gap-3 mt-2 pt-2 border-t border-border-subtle">
          {eventCount > 0 && (
            <div className="flex items-center gap-1">
              <Calendar className="h-3 w-3 text-accent-blue" />
              <span className="text-[10px] text-text-tertiary">{eventCount}</span>
            </div>
          )}
          {mediaCount > 0 && (
            <div className="flex items-center gap-1">
              <Image className="h-3 w-3 text-accent-purple" />
              <span className="text-[10px] text-text-tertiary">{mediaCount}</span>
            </div>
          )}
          {evidenceCount > 0 && (
            <div className="flex items-center gap-1">
              <FileBox className="h-3 w-3 text-accent-amber" />
              <span className="text-[10px] text-text-tertiary">{evidenceCount}</span>
            </div>
          )}
        </div>
      )}
    </button>
  );
}
