import { useState, useCallback, useMemo } from 'react';
import Map, {
  Marker,
  Popup,
  NavigationControl,
} from 'react-map-gl/maplibre';
import 'maplibre-gl/dist/maplibre-gl.css';
import type { Location } from '@/api/endpoints/locations';

interface LocationMapProps {
  locations: Location[];
  onLocationSelect?: (location: Location) => void;
  sizeByActivity?: boolean;
}

const MAP_STYLE =
  'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json';

export function LocationMap({
  locations,
  onLocationSelect,
  sizeByActivity = true,
}: LocationMapProps) {
  const [selectedLocation, setSelectedLocation] = useState<Location | null>(
    null
  );

  // Only show locations that have GPS coordinates
  const geoLocated = useMemo(
    () => locations.filter((l) => l.gpsLatitude != null && l.gpsLongitude != null),
    [locations]
  );

  // Compute max activity for scaling
  const maxActivity = useMemo(() => {
    let max = 1;
    for (const loc of geoLocated) {
      const activity = loc.totalActivity ?? 0;
      if (activity > max) max = activity;
    }
    return max;
  }, [geoLocated]);

  // Compute the initial centroid from geolocated points
  const centroid = computeCentroid(geoLocated);

  const handleMarkerClick = useCallback(
    (loc: Location) => {
      setSelectedLocation(loc);
      onLocationSelect?.(loc);
    },
    [onLocationSelect]
  );

  const handlePopupClose = useCallback(() => {
    setSelectedLocation(null);
  }, []);

  return (
    <Map
      initialViewState={{
        longitude: centroid.lng,
        latitude: centroid.lat,
        zoom: centroid.zoom,
      }}
      style={{ width: '100%', height: '100%' }}
      mapStyle={MAP_STYLE}
    >
      <NavigationControl position="top-right" />

      {geoLocated.map((loc) => {
        const activity = loc.totalActivity ?? 0;
        const size = sizeByActivity ? getMarkerSize(activity, maxActivity) : 12;
        const color = sizeByActivity
          ? getActivityColor(activity, maxActivity)
          : markerColor(loc.locationType);

        return (
          <Marker
            key={loc.locationId}
            longitude={loc.gpsLongitude!}
            latitude={loc.gpsLatitude!}
            anchor="center"
            onClick={(e) => {
              e.originalEvent.stopPropagation();
              handleMarkerClick(loc);
            }}
          >
            <div
              className="rounded-full border-2 cursor-pointer transition-all hover:scale-125"
              style={{
                width: size,
                height: size,
                backgroundColor: color,
                borderColor: '#1A1A2E',
                opacity: 0.85,
                boxShadow: activity > 0 ? `0 0 ${Math.min(activity, 20)}px ${color}40` : 'none',
              }}
              title={`${loc.locationName}: ${activity} activities`}
            />
          </Marker>
        );
      })}

      {selectedLocation &&
        selectedLocation.gpsLatitude != null &&
        selectedLocation.gpsLongitude != null && (
          <Popup
            longitude={selectedLocation.gpsLongitude}
            latitude={selectedLocation.gpsLatitude}
            onClose={handlePopupClose}
            closeButton={true}
            closeOnClick={false}
            offset={15}
            maxWidth="300px"
          >
            <div className="p-3 min-w-[220px]">
              <h3 className="text-sm font-semibold" style={{ color: '#E8E8F0' }}>
                {selectedLocation.locationName}
              </h3>
              {selectedLocation.locationType && (
                <span
                  className="inline-flex mt-1 items-center rounded-sm border px-1.5 py-0.5 text-[10px]"
                  style={{ borderColor: '#3A3A4E', color: '#A0A0B8' }}
                >
                  {selectedLocation.locationType}
                </span>
              )}
              <p className="text-xs mt-2" style={{ color: '#6B6B80' }}>
                {[
                  selectedLocation.address,
                  selectedLocation.city,
                  selectedLocation.stateProvince,
                  selectedLocation.country,
                ]
                  .filter(Boolean)
                  .join(', ')}
              </p>

              {/* Activity Stats */}
              <div className="mt-3 pt-2 border-t" style={{ borderColor: '#3A3A4E' }}>
                <div className="grid grid-cols-3 gap-2 text-center">
                  <div>
                    <p className="text-lg font-semibold" style={{ color: '#4A9EFF' }}>
                      {selectedLocation.eventCount ?? 0}
                    </p>
                    <p className="text-[10px]" style={{ color: '#6B6B80' }}>Events</p>
                  </div>
                  <div>
                    <p className="text-lg font-semibold" style={{ color: '#A855F7' }}>
                      {selectedLocation.mediaCount ?? 0}
                    </p>
                    <p className="text-[10px]" style={{ color: '#6B6B80' }}>Media</p>
                  </div>
                  <div>
                    <p className="text-lg font-semibold" style={{ color: '#FFB020' }}>
                      {selectedLocation.evidenceCount ?? 0}
                    </p>
                    <p className="text-[10px]" style={{ color: '#6B6B80' }}>Evidence</p>
                  </div>
                </div>
              </div>

              {selectedLocation.owner && (
                <p className="text-xs mt-2" style={{ color: '#A0A0B8' }}>
                  Owner: {selectedLocation.owner}
                </p>
              )}
              {selectedLocation.description && (
                <p className="text-xs mt-2" style={{ color: '#6B6B80' }}>
                  {selectedLocation.description}
                </p>
              )}
            </div>
          </Popup>
        )}
    </Map>
  );
}

/* ------------------------------------------------------------------ */
/* Marker Sizing & Coloring                                            */
/* ------------------------------------------------------------------ */

function getMarkerSize(activity: number, maxActivity: number): number {
  const minSize = 20;
  const maxSize = 72;

  if (activity === 0) return minSize;

  // Use sqrt scaling for better visual distribution
  const normalized = Math.sqrt(activity) / Math.sqrt(maxActivity);
  return minSize + (maxSize - minSize) * normalized;
}

function getActivityColor(activity: number, maxActivity: number): string {
  if (activity === 0) return '#22C55E'; // Green for no activity

  const normalized = activity / maxActivity;

  // Gradient: Blue (low) -> Purple (medium) -> Red/Orange (high)
  if (normalized < 0.33) {
    return '#4A9EFF'; // Blue
  } else if (normalized < 0.66) {
    return '#A855F7'; // Purple
  } else {
    return '#F97316'; // Orange/Red
  }
}

/* ------------------------------------------------------------------ */
/* Helpers                                                             */
/* ------------------------------------------------------------------ */

function markerColor(locationType?: string): string {
  if (!locationType) return '#22C55E';
  const lower = locationType.toLowerCase();
  if (lower.includes('residence') || lower.includes('home'))
    return '#4A9EFF';
  if (lower.includes('office') || lower.includes('business'))
    return '#A855F7';
  if (lower.includes('island') || lower.includes('ranch'))
    return '#FFB020';
  return '#22C55E';
}

function computeCentroid(locations: Location[]): {
  lat: number;
  lng: number;
  zoom: number;
} {
  if (locations.length === 0) {
    return { lat: 40.7484, lng: -73.9857, zoom: 3 };
  }

  let sumLat = 0;
  let sumLng = 0;
  let minLat = Infinity;
  let maxLat = -Infinity;
  let minLng = Infinity;
  let maxLng = -Infinity;

  for (const loc of locations) {
    const lat = loc.gpsLatitude!;
    const lng = loc.gpsLongitude!;
    sumLat += lat;
    sumLng += lng;
    if (lat < minLat) minLat = lat;
    if (lat > maxLat) maxLat = lat;
    if (lng < minLng) minLng = lng;
    if (lng > maxLng) maxLng = lng;
  }

  const avgLat = sumLat / locations.length;
  const avgLng = sumLng / locations.length;

  // Rough zoom calculation based on the bounding box span
  const latSpan = maxLat - minLat;
  const lngSpan = maxLng - minLng;
  const maxSpan = Math.max(latSpan, lngSpan);

  let zoom = 3;
  if (maxSpan < 0.01) zoom = 14;
  else if (maxSpan < 0.1) zoom = 11;
  else if (maxSpan < 1) zoom = 8;
  else if (maxSpan < 10) zoom = 5;
  else if (maxSpan < 50) zoom = 4;
  else zoom = 2;

  return { lat: avgLat, lng: avgLng, zoom };
}
