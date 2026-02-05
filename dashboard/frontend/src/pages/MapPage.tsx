import { useState, useMemo, useCallback } from 'react';
import {
  MapPin,
  AlertCircle,
  Globe,
  Navigation,
  PanelRightClose,
  PanelRightOpen,
  ChevronDown,
} from 'lucide-react';
import { LocationMap } from '@/components/map/LocationMap';
import {
  useLocations,
  useLocationTypes,
  useGeoLocatedCount,
} from '@/hooks/useLocations';
import { LoadingSpinner, StatCard } from '@/components/shared';
import { cn } from '@/lib/utils';
import type { Location } from '@/api/endpoints/locations';

export function MapPage() {
  const [locationTypeFilter, setLocationTypeFilter] = useState<string>('');
  const [panelOpen, setPanelOpen] = useState(true);
  const [selectedLocation, setSelectedLocation] = useState<Location | null>(
    null
  );

  const { data, isLoading, isError } = useLocations({
    pageSize: 500,
    locationType: locationTypeFilter || undefined,
  });

  const allLocations = data?.items ?? [];
  const locationTypes = useLocationTypes(allLocations);
  const stats = useGeoLocatedCount(allLocations);

  const geoLocated = useMemo(
    () =>
      allLocations.filter(
        (l) => l.gpsLatitude != null && l.gpsLongitude != null
      ),
    [allLocations]
  );

  const handleLocationSelect = useCallback((loc: Location) => {
    setSelectedLocation(loc);
    if (!panelOpen) setPanelOpen(true);
  }, [panelOpen]);

  return (
    <div className="flex flex-col gap-4 h-full">
      {/* Header */}
      <div>
        <h2 className="text-xl font-semibold text-text-primary">Map View</h2>
        <p className="mt-1 text-sm text-text-secondary">
          Geographic visualization of locations mentioned in documents.
        </p>
      </div>

      {/* Stats Row */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatCard
          label="Total Locations"
          value={stats.total}
          icon={MapPin}
          iconColor="text-entity-location"
        />
        <StatCard
          label="With GPS Coordinates"
          value={stats.geoLocated}
          icon={Navigation}
          iconColor="text-accent-cyan"
          trend={
            stats.total > 0
              ? `${Math.round((stats.geoLocated / stats.total) * 100)}% mapped`
              : undefined
          }
        />
        <StatCard
          label="Countries"
          value={stats.countries}
          icon={Globe}
          iconColor="text-accent-amber"
        />
      </div>

      {/* Filter Bar */}
      <div className="flex items-center gap-3 rounded-lg border border-border-subtle bg-surface-raised p-3">
        <div className="relative">
          <select
            value={locationTypeFilter}
            onChange={(e) => setLocationTypeFilter(e.target.value)}
            className="appearance-none rounded-md border border-border-subtle bg-surface-overlay px-3 py-1.5 pr-8 text-xs text-text-primary focus:border-accent-blue focus:outline-none"
          >
            <option value="">All Location Types</option>
            {locationTypes.map((type) => (
              <option key={type} value={type}>
                {type}
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
          <p className="text-sm text-accent-red">
            Failed to load location data.
          </p>
        </div>
      )}

      {!isLoading && !isError && geoLocated.length === 0 && (
        <div className="flex flex-col items-center justify-center gap-3 rounded-lg border border-border-subtle bg-surface-raised py-16">
          <MapPin className="h-10 w-10 text-text-disabled" />
          <p className="text-sm text-text-disabled">
            No geolocated data available.
          </p>
          <p className="text-xs text-text-disabled max-w-md text-center">
            Locations without GPS coordinates cannot be displayed on the map.
            {allLocations.length > 0 &&
              ` ${allLocations.length} locations exist without coordinates.`}
          </p>
        </div>
      )}

      {!isLoading && !isError && geoLocated.length > 0 && (
        <div className="flex flex-1 gap-0 rounded-lg border border-border-subtle bg-surface-raised overflow-hidden min-h-[500px]">
          {/* Map */}
          <div className={cn('flex-1 relative', panelOpen ? '' : 'w-full')}>
            <LocationMap
              locations={allLocations}
              onLocationSelect={handleLocationSelect}
            />
          </div>

          {/* Side Panel */}
          {panelOpen && (
            <div className="w-80 flex-shrink-0 border-l border-border-subtle bg-surface-raised overflow-y-auto">
              <div className="border-b border-border-subtle px-4 py-3">
                <h3 className="text-xs font-semibold uppercase tracking-wider text-text-tertiary">
                  Locations ({geoLocated.length})
                </h3>
              </div>
              <div className="divide-y divide-border-subtle">
                {geoLocated.map((loc) => (
                  <LocationListItem
                    key={loc.locationId}
                    location={loc}
                    isSelected={
                      selectedLocation?.locationId === loc.locationId
                    }
                    onClick={() => handleLocationSelect(loc)}
                  />
                ))}
              </div>
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

function LocationListItem({
  location,
  isSelected,
  onClick,
}: {
  location: Location;
  isSelected: boolean;
  onClick: () => void;
}) {
  const addressParts = [
    location.city,
    location.stateProvince,
    location.country,
  ].filter(Boolean);

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
    </button>
  );
}
