import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  MapPin,
  Search,
  ChevronLeft,
  ChevronRight,
  AlertCircle,
  X,
  Globe,
  Navigation,
} from 'lucide-react';
import { locationsApi } from '@/api/endpoints/locations';
import type { Location } from '@/api/endpoints/locations';
import { LoadingSpinner } from '@/components/shared';
import { useSelectionStore } from '@/stores/useSelectionStore';
import { cn } from '@/lib/utils';

export function LocationsPage() {
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [selectedLocation, setSelectedLocation] = useState<Location | null>(null);
  const selectEntity = useSelectionStore((s) => s.selectEntity);

  const { data, isLoading, isError } = useQuery({
    queryKey: ['locations', page, search],
    queryFn: () =>
      locationsApi.list({
        page,
        pageSize: 20,
        search: search || undefined,
      }),
  });

  const locations = data?.items ?? [];
  const pagination = data;

  function handleSearch(value: string) {
    setSearch(value);
    setPage(1);
  }

  function handleSelectLocation(loc: Location) {
    setSelectedLocation(loc);
    selectEntity(String(loc.locationId), 'location');
  }

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div>
        <h2 className="text-xl font-semibold text-text-primary">Locations</h2>
        <p className="mt-1 text-sm text-text-secondary">
          Properties, addresses, and locations referenced in the documents.
        </p>
      </div>

      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-tertiary" />
        <input
          type="text"
          value={search}
          onChange={(e) => handleSearch(e.target.value)}
          placeholder="Search locations..."
          className="w-full rounded-lg border border-border-subtle bg-surface-raised py-2.5 pl-10 pr-10 text-sm text-text-primary placeholder:text-text-disabled focus:border-accent-blue focus:outline-none focus:ring-1 focus:ring-accent-blue"
        />
        {search && (
          <button
            type="button"
            onClick={() => handleSearch('')}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-text-tertiary hover:text-text-primary"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>

      {/* Content */}
      <div className="flex gap-4">
        {/* Table */}
        <div className={cn('flex-1 rounded-lg border border-border-subtle bg-surface-raised overflow-hidden', selectedLocation && 'w-[65%]')}>
          {isLoading && <LoadingSpinner className="py-24" />}

          {isError && (
            <div className="flex flex-col items-center justify-center gap-3 py-12">
              <AlertCircle className="h-8 w-8 text-accent-red" />
              <p className="text-sm text-accent-red">Failed to load locations.</p>
            </div>
          )}

          {!isLoading && !isError && locations.length === 0 && (
            <div className="flex flex-col items-center justify-center gap-3 py-16">
              <MapPin className="h-10 w-10 text-text-disabled" />
              <p className="text-sm text-text-disabled">No locations found.</p>
            </div>
          )}

          {!isLoading && !isError && locations.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border-subtle">
                    <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-text-tertiary">
                      Name
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-text-tertiary">
                      Type
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-text-tertiary">
                      City
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-text-tertiary">
                      Country
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-text-tertiary">
                      Owner
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-text-tertiary">
                      GPS
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border-subtle">
                  {locations.map((loc) => (
                    <tr
                      key={loc.locationId}
                      onClick={() => handleSelectLocation(loc)}
                      className={cn(
                        'cursor-pointer transition-colors',
                        selectedLocation?.locationId === loc.locationId
                          ? 'bg-surface-overlay'
                          : 'hover:bg-surface-overlay'
                      )}
                    >
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <MapPin className="h-4 w-4 text-entity-location shrink-0" />
                          <span className="text-sm font-medium text-text-primary">
                            {loc.locationName}
                          </span>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        {loc.locationType ? (
                          <span className="inline-flex items-center rounded-sm border border-border-subtle bg-surface-overlay px-1.5 py-0.5 text-xs text-text-secondary">
                            {loc.locationType}
                          </span>
                        ) : (
                          <span className="text-xs text-text-disabled">--</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-xs text-text-secondary">
                        {loc.city ?? '--'}
                      </td>
                      <td className="px-4 py-3 text-xs text-text-secondary">
                        {loc.country ?? '--'}
                      </td>
                      <td className="px-4 py-3 text-xs text-text-secondary">
                        {loc.owner ?? '--'}
                      </td>
                      <td className="px-4 py-3 text-xs text-text-tertiary font-mono">
                        {loc.gpsLatitude !== undefined && loc.gpsLongitude !== undefined
                          ? `${loc.gpsLatitude.toFixed(4)}, ${loc.gpsLongitude.toFixed(4)}`
                          : '--'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Context Panel */}
        {selectedLocation && (
          <LocationDetailPanel
            location={selectedLocation}
            onClose={() => setSelectedLocation(null)}
          />
        )}
      </div>

      {/* Pagination */}
      {pagination && pagination.totalPages > 1 && (
        <div className="flex items-center justify-between rounded-lg border border-border-subtle bg-surface-raised p-3">
          <span className="text-xs text-text-tertiary">
            Page {page} of {pagination.totalPages}
            {' '}({pagination.totalCount.toLocaleString()} total)
          </span>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
              className="flex items-center gap-1 rounded-md border border-border-subtle px-2.5 py-1 text-xs text-text-secondary transition-colors hover:bg-surface-overlay disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <ChevronLeft className="h-3.5 w-3.5" />
              Previous
            </button>
            <button
              type="button"
              onClick={() => setPage((p) => Math.min(pagination.totalPages, p + 1))}
              disabled={page >= pagination.totalPages}
              className="flex items-center gap-1 rounded-md border border-border-subtle px-2.5 py-1 text-xs text-text-secondary transition-colors hover:bg-surface-overlay disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Next
              <ChevronRight className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function LocationDetailPanel({
  location: loc,
  onClose,
}: {
  location: Location;
  onClose: () => void;
}) {
  return (
    <div className="w-[35%] shrink-0 rounded-lg border border-border-subtle bg-surface-raised overflow-y-auto">
      <div className="flex items-center justify-between border-b border-border-subtle p-4">
        <h3 className="text-sm font-semibold text-text-primary">Location Details</h3>
        <button
          type="button"
          onClick={onClose}
          className="text-text-tertiary hover:text-text-primary"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      <div className="p-4">
        <div className="flex items-center gap-2 mb-3">
          <MapPin className="h-5 w-5 text-entity-location" />
          <h4 className="text-base font-semibold text-text-primary">
            {loc.locationName}
          </h4>
        </div>

        {loc.locationType && (
          <span className="inline-flex items-center rounded-sm border border-entity-location/30 bg-entity-location/15 px-1.5 py-0.5 text-xs font-medium text-entity-location mb-3">
            {loc.locationType}
          </span>
        )}

        <dl className="flex flex-col gap-3 text-xs mt-4">
          {loc.address && (
            <div>
              <dt className="text-text-tertiary mb-0.5">Address</dt>
              <dd className="text-text-secondary">{loc.address}</dd>
            </div>
          )}
          {(loc.city || loc.stateProvince) && (
            <div>
              <dt className="flex items-center gap-1 text-text-tertiary mb-0.5">
                <Globe className="h-3 w-3" /> City / State
              </dt>
              <dd className="text-text-secondary">
                {[loc.city, loc.stateProvince].filter(Boolean).join(', ')}
              </dd>
            </div>
          )}
          {loc.country && (
            <div>
              <dt className="text-text-tertiary mb-0.5">Country</dt>
              <dd className="text-text-secondary">{loc.country}</dd>
            </div>
          )}
          {loc.owner && (
            <div>
              <dt className="text-text-tertiary mb-0.5">Owner</dt>
              <dd className="text-text-secondary">{loc.owner}</dd>
            </div>
          )}
          {loc.gpsLatitude !== undefined && loc.gpsLongitude !== undefined && (
            <div>
              <dt className="flex items-center gap-1 text-text-tertiary mb-0.5">
                <Navigation className="h-3 w-3" /> GPS Coordinates
              </dt>
              <dd className="text-text-secondary font-mono">
                {loc.gpsLatitude.toFixed(6)}, {loc.gpsLongitude.toFixed(6)}
              </dd>
            </div>
          )}
          {loc.description && (
            <div>
              <dt className="text-text-tertiary mb-0.5">Description</dt>
              <dd className="text-text-secondary leading-relaxed">{loc.description}</dd>
            </div>
          )}
        </dl>
      </div>
    </div>
  );
}
