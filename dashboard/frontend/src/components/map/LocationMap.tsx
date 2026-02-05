import { useState, useCallback } from 'react';
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
}

const MAP_STYLE =
  'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json';

export function LocationMap({
  locations,
  onLocationSelect,
}: LocationMapProps) {
  const [selectedLocation, setSelectedLocation] = useState<Location | null>(
    null
  );

  // Only show locations that have GPS coordinates
  const geoLocated = locations.filter(
    (l) => l.gpsLatitude != null && l.gpsLongitude != null
  );

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

      {geoLocated.map((loc) => (
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
            className="w-3 h-3 rounded-full border-2 cursor-pointer transition-transform hover:scale-150"
            style={{
              backgroundColor: markerColor(loc.locationType),
              borderColor: '#1A1A2E',
            }}
          />
        </Marker>
      ))}

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
            maxWidth="280px"
          >
            <div className="p-3 min-w-[200px]">
              <h3 className="text-sm font-semibold" style={{ color: '#E8E8F0' }}>
                {selectedLocation.locationName}
              </h3>
              {selectedLocation.locationType && (
                <p className="text-xs mt-1" style={{ color: '#A0A0B8' }}>
                  {selectedLocation.locationType}
                </p>
              )}
              <p className="text-xs mt-1" style={{ color: '#6B6B80' }}>
                {[
                  selectedLocation.address,
                  selectedLocation.city,
                  selectedLocation.stateProvince,
                  selectedLocation.country,
                ]
                  .filter(Boolean)
                  .join(', ')}
              </p>
              {selectedLocation.owner && (
                <p className="text-xs mt-1" style={{ color: '#A0A0B8' }}>
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
