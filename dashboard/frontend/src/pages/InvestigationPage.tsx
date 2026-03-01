import { useState, useCallback, useMemo, useRef, useEffect } from 'react';
import MapGL, { Marker, Popup, NavigationControl } from 'react-map-gl/maplibre';
import 'maplibre-gl/dist/maplibre-gl.css';
import {
  Search,
  X,
  UserPlus,
  MapPin,
  Calendar,
  DollarSign,
  Users,
  ChevronRight,
  ChevronDown,
  AlertCircle,
  Crosshair,
  Link2,
  Activity,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import {
  usePersonSearch,
  useGeoTimeline,
  usePersonConnections,
  useSharedPresence,
  useFinancialNetwork,
} from '@/hooks/useInvestigation';
import type { GeoTimelineEntry, PersonSearchResult } from '@/hooks/useInvestigation';
import { LoadingSpinner } from '@/components/shared';

const MAP_STYLE = 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json';

// Color palette for different subjects
const SUBJECT_COLORS = [
  '#3b82f6', // blue
  '#ef4444', // red
  '#22c55e', // green
  '#f59e0b', // amber
  '#8b5cf6', // violet
  '#ec4899', // pink
  '#06b6d4', // cyan
  '#f97316', // orange
];

interface InvestigationSubject {
  personId: number;
  personName: string;
  primaryRole?: string;
  epsteinRelationship?: string;
  color: string;
}

interface SelectedMapLocation {
  locationId: number;
  locationName: string;
  latitude: number;
  longitude: number;
  entries: GeoTimelineEntry[];
}

// ─── Person search dropdown ───────────────────────────────────────────────────
function PersonSearchDropdown({
  onAdd,
  existingIds,
}: {
  onAdd: (p: PersonSearchResult) => void;
  existingIds: Set<number>;
}) {
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);
  const { data: results = [], isLoading } = usePersonSearch(query);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  return (
    <div ref={ref} className="relative">
      <div className="flex items-center gap-2 rounded-md border border-border-subtle bg-surface-raised px-3 py-2">
        <Search className="h-4 w-4 shrink-0 text-text-muted" />
        <input
          data-testid="person-search-input"
          className="flex-1 bg-transparent text-sm text-text-primary placeholder:text-text-muted outline-none"
          placeholder="Add person to investigation..."
          value={query}
          onChange={(e) => { setQuery(e.target.value); setOpen(true); }}
          onFocus={() => setOpen(true)}
        />
        {isLoading && <LoadingSpinner size="sm" />}
      </div>

      {open && query.length >= 2 && (
        <div
          data-testid="person-search-results"
          className="absolute z-50 mt-1 w-full rounded-md border border-border-subtle bg-surface-raised shadow-lg"
        >
          {results.length === 0 ? (
            <div className="px-3 py-2 text-sm text-text-muted">No results for "{query}"</div>
          ) : (
            <ul className="max-h-64 overflow-y-auto">
              {results.map((r) => {
                const already = existingIds.has(r.personId);
                return (
                  <li key={r.personId}>
                    <button
                      disabled={already}
                      onClick={() => { onAdd(r); setQuery(''); setOpen(false); }}
                      className={cn(
                        'flex w-full items-start gap-2 px-3 py-2 text-left text-sm transition-colors',
                        already
                          ? 'cursor-not-allowed opacity-40'
                          : 'hover:bg-surface-overlay'
                      )}
                    >
                      <UserPlus className="mt-0.5 h-4 w-4 shrink-0 text-text-muted" />
                      <div>
                        <div className="font-medium text-text-primary">{r.personName}</div>
                        <div className="text-xs text-text-muted">
                          {r.primaryRole ?? 'Unknown role'} &bull; {r.placementCount} placements
                          {r.epsteinRelationship ? ` · ${r.epsteinRelationship}` : ''}
                        </div>
                      </div>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Subject chip ─────────────────────────────────────────────────────────────
function SubjectChip({
  subject,
  selected,
  onClick,
  onRemove,
}: {
  subject: InvestigationSubject;
  selected: boolean;
  onClick: () => void;
  onRemove: () => void;
}) {
  return (
    <div
      data-testid={`subject-chip-${subject.personId}`}
      className={cn(
        'flex items-center gap-1.5 rounded-full px-3 py-1 text-sm font-medium cursor-pointer transition-all',
        selected ? 'ring-2 ring-white/40' : 'opacity-80 hover:opacity-100'
      )}
      style={{ backgroundColor: subject.color + '33', borderColor: subject.color, border: `1px solid ${subject.color}` }}
      onClick={onClick}
    >
      <div className="h-2 w-2 rounded-full" style={{ backgroundColor: subject.color }} />
      <span className="text-text-primary max-w-32 truncate">{subject.personName}</span>
      <button
        onClick={(e) => { e.stopPropagation(); onRemove(); }}
        className="ml-0.5 rounded-full p-0.5 hover:bg-white/20"
      >
        <X className="h-3 w-3 text-text-muted" />
      </button>
    </div>
  );
}

// ─── Collapsible section ──────────────────────────────────────────────────────
function Section({ title, count, children, defaultOpen = true }: {
  title: string;
  count?: number;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="border-b border-border-subtle last:border-0">
      <button
        onClick={() => setOpen(!open)}
        className="flex w-full items-center justify-between px-4 py-2.5 text-sm font-medium text-text-secondary hover:text-text-primary"
      >
        <span className="flex items-center gap-2">
          {title}
          {count !== undefined && (
            <span className="rounded-full bg-surface-overlay px-1.5 py-0.5 text-xs text-text-muted">{count}</span>
          )}
        </span>
        {open ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
      </button>
      {open && <div className="pb-2">{children}</div>}
    </div>
  );
}

// ─── Main page ────────────────────────────────────────────────────────────────
export function InvestigationPage() {
  const [subjects, setSubjects] = useState<InvestigationSubject[]>([]);
  const [selectedSubjectId, setSelectedSubjectId] = useState<number | null>(null);
  const [selectedMapLocation, setSelectedMapLocation] = useState<SelectedMapLocation | null>(null);
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [activeTab, setActiveTab] = useState<'connections' | 'shared' | 'financial'>('connections');

  const subjectIds = useMemo(() => subjects.map((s) => s.personId), [subjects]);
  const existingIdSet = useMemo(() => new Set(subjectIds), [subjectIds]);

  const colorForSubject = useCallback(
    (personId: number) => subjects.find((s) => s.personId === personId)?.color ?? '#94a3b8',
    [subjects]
  );

  // ── Data fetching ──
  // Geo timeline: placements for all subjects
  const { data: geoEntries = [], isLoading: geoLoading } = useGeoTimeline({
    dateFrom: dateFrom || undefined,
    dateTo: dateTo || undefined,
    limit: 3000,
  });

  // Filter to only subjects
  const subjectEntries = useMemo(() => {
    if (subjects.length === 0) return geoEntries;
    const nameSet = new Set(subjects.map((s) => s.personName.toLowerCase()));
    const idSet = new Set(subjectIds);
    return geoEntries.filter(
      (e) => idSet.has(e.personId ?? -1) || nameSet.has(e.personName.toLowerCase())
    );
  }, [geoEntries, subjects, subjectIds]);

  // Selected subject connections
  const { data: connections, isLoading: connLoading } = usePersonConnections(
    selectedSubjectId,
    { dateFrom: dateFrom || undefined, dateTo: dateTo || undefined }
  );

  // Shared presence (hotspots)
  const { data: sharedPresence = [], isLoading: sharedLoading } = useSharedPresence(
    subjectIds,
    { dateFrom: dateFrom || undefined, dateTo: dateTo || undefined }
  );

  // Financial network
  const { data: financialTxns = [], isLoading: financialLoading } = useFinancialNetwork(
    subjectIds,
    { dateFrom: dateFrom || undefined, dateTo: dateTo || undefined }
  );

  // ── Map markers grouped by location ──
  const locationGroups = useMemo((): SelectedMapLocation[] => {
    const groupMap = new Map<number, SelectedMapLocation>();
    for (const e of subjectEntries) {
      if (e.latitude == null || e.longitude == null) continue;
      if (!groupMap.has(e.locationId)) {
        groupMap.set(e.locationId, {
          locationId: e.locationId,
          locationName: e.locationName,
          latitude: e.latitude,
          longitude: e.longitude,
          entries: [],
        });
      }
      groupMap.get(e.locationId)!.entries.push(e);
    }
    return Array.from(groupMap.values());
  }, [subjectEntries]);

  // Shared presence location IDs for highlighting
  const sharedLocationIds = useMemo(
    () => new Set(sharedPresence.map((sp) => sp.locationId)),
    [sharedPresence]
  );

  const addSubject = useCallback((p: PersonSearchResult) => {
    const color = SUBJECT_COLORS[subjects.length % SUBJECT_COLORS.length];
    setSubjects((prev) => [
      ...prev,
      { personId: p.personId, personName: p.personName, primaryRole: p.primaryRole, epsteinRelationship: p.epsteinRelationship, color },
    ]);
    setSelectedSubjectId(p.personId);
  }, [subjects.length]);

  const removeSubject = useCallback((id: number) => {
    setSubjects((prev) => prev.filter((s) => s.personId !== id));
    setSelectedSubjectId((prev) => (prev === id ? null : prev));
  }, []);

  const handleMarkerClick = useCallback((loc: SelectedMapLocation) => {
    setSelectedMapLocation(loc);
  }, []);

  return (
    <div data-testid="investigation-page" className="flex h-full flex-col gap-0 -m-4">
      {/* ── Top toolbar ── */}
      <div className="flex flex-wrap items-center gap-3 border-b border-border-subtle bg-surface-raised px-4 py-3">
        {/* Title */}
        <div className="flex items-center gap-2 shrink-0">
          <Crosshair className="h-5 w-5 text-accent-blue" />
          <span className="text-sm font-semibold text-text-primary">Investigation Workbench</span>
        </div>

        <div className="w-px h-5 bg-border-subtle shrink-0" />

        {/* Person search */}
        <div className="w-72">
          <PersonSearchDropdown onAdd={addSubject} existingIds={existingIdSet} />
        </div>

        {/* Subject chips */}
        {subjects.map((s) => (
          <SubjectChip
            key={s.personId}
            subject={s}
            selected={selectedSubjectId === s.personId}
            onClick={() => setSelectedSubjectId(s.personId === selectedSubjectId ? null : s.personId)}
            onRemove={() => removeSubject(s.personId)}
          />
        ))}

        <div className="ml-auto flex items-center gap-2">
          {/* Date range */}
          <div className="flex items-center gap-1.5 text-sm text-text-muted">
            <Calendar className="h-4 w-4" />
            <input
              data-testid="date-from-input"
              type="date"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
              className="rounded border border-border-subtle bg-surface-base px-2 py-1 text-xs text-text-primary outline-none focus:border-accent-blue"
              placeholder="From"
            />
            <span>–</span>
            <input
              data-testid="date-to-input"
              type="date"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
              className="rounded border border-border-subtle bg-surface-base px-2 py-1 text-xs text-text-primary outline-none focus:border-accent-blue"
              placeholder="To"
            />
            {(dateFrom || dateTo) && (
              <button onClick={() => { setDateFrom(''); setDateTo(''); }} className="text-text-muted hover:text-text-primary">
                <X className="h-3.5 w-3.5" />
              </button>
            )}
          </div>
          {geoLoading && <LoadingSpinner size="sm" />}
          <span className="text-xs text-text-muted">
            {subjectEntries.length} placements
          </span>
        </div>
      </div>

      {/* ── Main layout: map + side panel ── */}
      <div className="flex flex-1 min-h-0">
        {/* ── Map ── */}
        <div
          data-testid="investigation-map"
          className="flex-1 relative"
          style={{ minWidth: 0 }}
        >
          {subjects.length === 0 && (
            <div className="absolute inset-0 z-10 flex flex-col items-center justify-center bg-surface-base/80 pointer-events-none">
              <Crosshair className="h-12 w-12 text-text-muted mb-3" />
              <p className="text-text-secondary font-medium">Add people to start investigating</p>
              <p className="text-text-muted text-sm mt-1">Search for a person above to see their location history</p>
            </div>
          )}
          <MapGL
            initialViewState={{ longitude: -80, latitude: 30, zoom: 3 }}
            style={{ width: '100%', height: '100%' }}
            mapStyle={MAP_STYLE}
          >
            <NavigationControl position="top-right" />

            {locationGroups.map((loc) => {
              const isShared = sharedLocationIds.has(loc.locationId);
              const isSelected = selectedMapLocation?.locationId === loc.locationId;
              // Determine which subjects are here
              const presentSubjectIds = new Set(loc.entries.map((e) => e.personId).filter(Boolean));
              const primaryColor = subjects.find((s) => presentSubjectIds.has(s.personId))?.color ?? '#94a3b8';
              const size = Math.min(8 + loc.entries.length * 2, 30);

              return (
                <Marker
                  key={loc.locationId}
                  longitude={loc.longitude}
                  latitude={loc.latitude}
                  onClick={(e) => {
                    e.originalEvent.stopPropagation();
                    handleMarkerClick(loc);
                  }}
                >
                  <div
                    title={loc.locationName}
                    className="cursor-pointer transition-transform hover:scale-125"
                    style={{
                      width: size,
                      height: size,
                      borderRadius: '50%',
                      backgroundColor: isShared ? '#f59e0b' : primaryColor,
                      border: isSelected ? '3px solid white' : `2px solid ${isShared ? '#fbbf24' : primaryColor}`,
                      boxShadow: isShared ? '0 0 12px #f59e0baa' : undefined,
                      opacity: 0.9,
                    }}
                  />
                </Marker>
              );
            })}

            {selectedMapLocation && (
              <Popup
                longitude={selectedMapLocation.longitude}
                latitude={selectedMapLocation.latitude}
                onClose={() => setSelectedMapLocation(null)}
                closeButton
                anchor="bottom"
                maxWidth="340px"
              >
                <div className="p-0 text-sm" data-testid="map-popup">
                  <div className="font-semibold text-gray-900 mb-2 border-b pb-1">
                    {selectedMapLocation.locationName}
                  </div>
                  <div className="max-h-48 overflow-y-auto space-y-1">
                    {selectedMapLocation.entries
                      .sort((a, b) => (a.placementDate ?? '') > (b.placementDate ?? '') ? -1 : 1)
                      .map((e) => {
                        const color = colorForSubject(e.personId ?? -1);
                        return (
                          <div key={e.placementId} className="flex items-start gap-1.5 py-0.5">
                            <div className="mt-1 h-2 w-2 rounded-full shrink-0" style={{ backgroundColor: color }} />
                            <div>
                              <span className="font-medium text-gray-800">{e.personName}</span>
                              {e.placementDate && (
                                <span className="ml-1.5 text-gray-500 text-xs">
                                  {e.placementDate.slice(0, 10)}
                                </span>
                              )}
                              {e.activityType && (
                                <span className="ml-1 text-xs text-gray-500">· {e.activityType.replace('_', ' ')}</span>
                              )}
                            </div>
                          </div>
                        );
                      })}
                  </div>
                </div>
              </Popup>
            )}
          </MapGL>

          {/* Map legend */}
          {subjects.length > 0 && (
            <div className="absolute bottom-4 left-4 rounded-lg border border-border-subtle bg-surface-raised/90 px-3 py-2 backdrop-blur-sm">
              {subjects.map((s) => (
                <div key={s.personId} className="flex items-center gap-2 text-xs text-text-secondary">
                  <div className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: s.color }} />
                  <span className="truncate max-w-36">{s.personName}</span>
                </div>
              ))}
              {sharedPresence.length > 0 && (
                <div className="flex items-center gap-2 text-xs text-amber-400 mt-1 pt-1 border-t border-border-subtle">
                  <div className="h-2.5 w-2.5 rounded-full bg-amber-400" />
                  <span>Shared location ({sharedPresence.length})</span>
                </div>
              )}
            </div>
          )}
        </div>

        {/* ── Right panel ── */}
        <div className="w-96 shrink-0 flex flex-col border-l border-border-subtle bg-surface-raised overflow-hidden">
          {/* Tab bar */}
          <div className="flex border-b border-border-subtle shrink-0">
            {([
              { key: 'connections', label: 'Connections', icon: Link2 },
              { key: 'shared', label: 'Hot Spots', icon: Crosshair },
              { key: 'financial', label: 'Financial', icon: DollarSign },
            ] as const).map(({ key, label, icon: Icon }) => (
              <button
                key={key}
                data-testid={`tab-${key}`}
                onClick={() => setActiveTab(key)}
                className={cn(
                  'flex-1 flex items-center justify-center gap-1.5 py-2.5 text-xs font-medium transition-colors',
                  activeTab === key
                    ? 'border-b-2 border-accent-blue text-accent-blue'
                    : 'text-text-muted hover:text-text-secondary'
                )}
              >
                <Icon className="h-3.5 w-3.5" />
                {label}
              </button>
            ))}
          </div>

          {/* Panel content */}
          <div className="flex-1 overflow-y-auto">
            {/* ── Connections tab ── */}
            {activeTab === 'connections' && (
              <div data-testid="connections-panel">
                {subjects.length === 0 ? (
                  <EmptyState icon={Users} message="Add subjects to see connections" />
                ) : selectedSubjectId == null ? (
                  <EmptyState icon={Users} message="Click a subject chip to view their connections" />
                ) : connLoading ? (
                  <div className="flex justify-center py-8"><LoadingSpinner /></div>
                ) : connections ? (
                  <div data-testid="connections-data">
                    {/* Person header */}
                    <div className="px-4 py-3 border-b border-border-subtle">
                      <div className="flex items-center gap-2">
                        <div
                          className="h-3 w-3 rounded-full"
                          style={{ backgroundColor: colorForSubject(selectedSubjectId) }}
                        />
                        <span className="font-semibold text-text-primary">{connections.personName}</span>
                      </div>
                      {connections.primaryRole && (
                        <div className="text-xs text-text-muted mt-0.5">{connections.primaryRole}</div>
                      )}
                      {connections.epsteinRelationship && (
                        <div className="mt-1 inline-flex rounded-full bg-red-500/20 px-2 py-0.5 text-xs text-red-400">
                          {connections.epsteinRelationship}
                        </div>
                      )}
                    </div>

                    {/* Locations */}
                    <Section title="Locations Visited" count={connections.locations.length}>
                      {connections.locations.length === 0 ? (
                        <p className="px-4 py-2 text-xs text-text-muted">No locations found</p>
                      ) : (
                        <ul className="divide-y divide-border-subtle">
                          {connections.locations.map((loc) => (
                            <li
                              key={loc.locationId}
                              data-testid={`location-item-${loc.locationId}`}
                              className="flex items-start gap-2 px-4 py-2 hover:bg-surface-overlay cursor-pointer"
                              onClick={() => {
                                // Highlight location on map
                                const found = locationGroups.find((g) => g.locationId === loc.locationId);
                                if (found) setSelectedMapLocation(found);
                              }}
                            >
                              <MapPin className="mt-0.5 h-3.5 w-3.5 shrink-0 text-text-muted" />
                              <div className="min-w-0">
                                <div className="text-sm font-medium text-text-primary truncate">
                                  {loc.locationName}
                                </div>
                                <div className="text-xs text-text-muted">
                                  {[loc.city, loc.country].filter(Boolean).join(', ')}
                                  {loc.visitCount > 0 && ` · ${loc.visitCount} visit${loc.visitCount !== 1 ? 's' : ''}`}
                                </div>
                                {(loc.firstVisit || loc.lastVisit) && (
                                  <div className="text-xs text-text-muted">
                                    {loc.firstVisit?.slice(0, 10)} – {loc.lastVisit?.slice(0, 10)}
                                  </div>
                                )}
                              </div>
                            </li>
                          ))}
                        </ul>
                      )}
                    </Section>

                    {/* Related people */}
                    <Section title="Connected People" count={connections.relatedPeople.length}>
                      {connections.relatedPeople.length === 0 ? (
                        <p className="px-4 py-2 text-xs text-text-muted">No connections found</p>
                      ) : (
                        <ul className="divide-y divide-border-subtle">
                          {connections.relatedPeople.slice(0, 30).map((p, idx) => (
                            <li
                              key={`${p.personId}-${idx}`}
                              data-testid={`connected-person-${p.personId}`}
                              className="flex items-start gap-2 px-4 py-2 hover:bg-surface-overlay"
                            >
                              <Users className="mt-0.5 h-3.5 w-3.5 shrink-0 text-text-muted" />
                              <div className="min-w-0 flex-1">
                                <div className="flex items-center gap-1.5">
                                  <span className="text-sm font-medium text-text-primary truncate">
                                    {p.personName}
                                  </span>
                                  {existingIdSet.has(p.personId) && (
                                    <span className="shrink-0 rounded-full bg-accent-blue/20 px-1.5 text-xs text-accent-blue">
                                      subject
                                    </span>
                                  )}
                                </div>
                                <div className="text-xs text-text-muted flex gap-1.5">
                                  <span className="capitalize">{p.source?.replace('-', ' ')}</span>
                                  {p.relationshipType && <span>· {p.relationshipType}</span>}
                                  {p.sharedCount > 1 && <span>· {p.sharedCount}×</span>}
                                </div>
                              </div>
                            </li>
                          ))}
                        </ul>
                      )}
                    </Section>

                    {/* Co-presences */}
                    <Section title="Co-Presences (±30 days)" count={connections.coPresences.length} defaultOpen={false}>
                      {connections.coPresences.length === 0 ? (
                        <p className="px-4 py-2 text-xs text-text-muted">No co-presences found</p>
                      ) : (
                        <ul className="divide-y divide-border-subtle">
                          {connections.coPresences.slice(0, 30).map((cp, idx) => (
                            <li
                              key={idx}
                              data-testid={`co-presence-item`}
                              className="px-4 py-2 hover:bg-surface-overlay"
                            >
                              <div className="flex items-center gap-1.5">
                                <Activity className="h-3.5 w-3.5 shrink-0 text-amber-400" />
                                <span className="text-sm font-medium text-text-primary">{cp.otherPersonName}</span>
                              </div>
                              <div className="mt-0.5 text-xs text-text-muted pl-5">
                                {cp.locationName}
                                {cp.subjectDate && ` · ${cp.subjectDate.slice(0, 10)}`}
                                {cp.overlapDays === 0 ? ' (same day)' : ` (±${cp.overlapDays}d)`}
                              </div>
                            </li>
                          ))}
                        </ul>
                      )}
                    </Section>

                    {/* Events */}
                    <Section title="Events" count={connections.events.length} defaultOpen={false}>
                      {connections.events.length === 0 ? (
                        <p className="px-4 py-2 text-xs text-text-muted">No events found</p>
                      ) : (
                        <ul className="divide-y divide-border-subtle">
                          {connections.events.map((ev) => (
                            <li key={ev.eventId} className="px-4 py-2 hover:bg-surface-overlay">
                              <div className="text-sm font-medium text-text-primary">
                                {ev.title || ev.eventType || `Event #${ev.eventId}`}
                              </div>
                              <div className="text-xs text-text-muted">
                                {ev.eventDate?.slice(0, 10)}
                                {ev.locationName && ` · ${ev.locationName}`}
                                {ev.participationRole && ` · ${ev.participationRole}`}
                              </div>
                            </li>
                          ))}
                        </ul>
                      )}
                    </Section>

                    {/* Financial */}
                    <Section title="Financial Transactions" count={connections.financialTransactions.length} defaultOpen={false}>
                      {connections.financialTransactions.length === 0 ? (
                        <p className="px-4 py-2 text-xs text-text-muted">No transactions found</p>
                      ) : (
                        <ul className="divide-y divide-border-subtle">
                          {connections.financialTransactions.map((tx) => (
                            <li
                              key={tx.transactionId}
                              data-testid={`financial-item-${tx.transactionId}`}
                              className="px-4 py-2 hover:bg-surface-overlay"
                            >
                              <div className="flex items-center gap-2">
                                <DollarSign className={cn('h-3.5 w-3.5 shrink-0', tx.direction === 'sent' ? 'text-red-400' : 'text-green-400')} />
                                <span className="text-sm font-medium text-text-primary">
                                  {tx.direction === 'sent' ? '→ ' : '← '}
                                  {tx.counterpartyName ?? 'Unknown'}
                                </span>
                                {tx.amount != null && (
                                  <span className={cn('ml-auto text-sm font-semibold', tx.direction === 'sent' ? 'text-red-400' : 'text-green-400')}>
                                    {tx.direction === 'sent' ? '-' : '+'}{tx.currency ?? '$'}{Number(tx.amount).toLocaleString()}
                                  </span>
                                )}
                              </div>
                              <div className="text-xs text-text-muted pl-5">
                                {tx.transactionDate?.slice(0, 10)}
                                {tx.purpose && ` · ${tx.purpose}`}
                              </div>
                            </li>
                          ))}
                        </ul>
                      )}
                    </Section>
                  </div>
                ) : null}
              </div>
            )}

            {/* ── Hot Spots tab ── */}
            {activeTab === 'shared' && (
              <div data-testid="shared-presence-panel">
                {subjects.length < 2 ? (
                  <EmptyState icon={Crosshair} message="Add at least 2 subjects to find shared locations" />
                ) : sharedLoading ? (
                  <div className="flex justify-center py-8"><LoadingSpinner /></div>
                ) : sharedPresence.length === 0 ? (
                  <EmptyState icon={AlertCircle} message="No shared locations found for these subjects" />
                ) : (
                  <div data-testid="shared-presence-data">
                    <div className="px-4 py-2 text-xs text-text-muted border-b border-border-subtle">
                      {sharedPresence.length} location{sharedPresence.length !== 1 ? 's' : ''} where subjects overlapped
                    </div>
                    <ul className="divide-y divide-border-subtle">
                      {sharedPresence.map((sp) => (
                        <li
                          key={sp.locationId}
                          data-testid={`shared-location-${sp.locationId}`}
                          className="px-4 py-3 hover:bg-surface-overlay cursor-pointer"
                          onClick={() => {
                            const found = locationGroups.find((g) => g.locationId === sp.locationId);
                            if (found) setSelectedMapLocation(found);
                          }}
                        >
                          <div className="flex items-start gap-2">
                            <div className="mt-0.5 rounded-full bg-amber-400/20 p-1">
                              <Crosshair className="h-3 w-3 text-amber-400" />
                            </div>
                            <div className="min-w-0">
                              <div className="font-medium text-text-primary truncate">{sp.locationName}</div>
                              <div className="text-xs text-text-muted">{[sp.city, sp.country].filter(Boolean).join(', ')}</div>
                              <div className="mt-1 flex flex-wrap gap-1">
                                {sp.personNames.slice(0, 5).map((name) => {
                                  const subj = subjects.find((s) => s.personName === name);
                                  return (
                                    <span
                                      key={name}
                                      className="rounded-full px-2 py-0.5 text-xs"
                                      style={{
                                        backgroundColor: (subj?.color ?? '#94a3b8') + '33',
                                        color: subj?.color ?? '#94a3b8',
                                      }}
                                    >
                                      {name}
                                    </span>
                                  );
                                })}
                                {sp.personNames.length > 5 && (
                                  <span className="text-xs text-text-muted">+{sp.personNames.length - 5} more</span>
                                )}
                              </div>
                              {(sp.earliestDate || sp.latestDate) && (
                                <div className="mt-1 text-xs text-text-muted">
                                  {sp.earliestDate?.slice(0, 10)} – {sp.latestDate?.slice(0, 10)}
                                </div>
                              )}
                            </div>
                          </div>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}

            {/* ── Financial tab ── */}
            {activeTab === 'financial' && (
              <div data-testid="financial-panel">
                {subjects.length === 0 ? (
                  <EmptyState icon={DollarSign} message="Add subjects to see financial connections" />
                ) : financialLoading ? (
                  <div className="flex justify-center py-8"><LoadingSpinner /></div>
                ) : financialTxns.length === 0 ? (
                  <EmptyState icon={DollarSign} message="No financial transactions found" />
                ) : (
                  <div data-testid="financial-data">
                    <div className="px-4 py-2 text-xs text-text-muted border-b border-border-subtle">
                      {financialTxns.length} transaction{financialTxns.length !== 1 ? 's' : ''} involving subjects
                    </div>
                    <ul className="divide-y divide-border-subtle">
                      {financialTxns.map((tx, idx) => (
                        <li
                          key={`${tx.transactionId}-${idx}`}
                          data-testid={`financial-txn-${tx.transactionId}`}
                          className="px-4 py-2.5 hover:bg-surface-overlay"
                        >
                          <div className="flex items-center gap-2">
                            <DollarSign className={cn('h-3.5 w-3.5 shrink-0', tx.direction === 'sent' ? 'text-red-400' : 'text-green-400')} />
                            <span className="text-sm font-medium text-text-primary truncate flex-1">
                              {tx.counterpartyName ?? 'Unknown'}
                            </span>
                            {tx.amount != null && (
                              <span className={cn('shrink-0 text-sm font-semibold', tx.direction === 'sent' ? 'text-red-400' : 'text-green-400')}>
                                {tx.currency ?? '$'}{Number(tx.amount).toLocaleString()}
                              </span>
                            )}
                          </div>
                          <div className="pl-5 text-xs text-text-muted">
                            {tx.transactionDate?.slice(0, 10)}
                            {tx.purpose && ` · ${tx.purpose}`}
                          </div>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Panel stats footer */}
          {subjects.length > 0 && (
            <div className="shrink-0 border-t border-border-subtle bg-surface-base px-4 py-2 flex items-center gap-4 text-xs text-text-muted">
              <span data-testid="stat-locations" className="flex items-center gap-1">
                <MapPin className="h-3.5 w-3.5" />
                {locationGroups.length} locations
              </span>
              <span data-testid="stat-placements" className="flex items-center gap-1">
                <Activity className="h-3.5 w-3.5" />
                {subjectEntries.length} placements
              </span>
              {sharedPresence.length > 0 && (
                <span data-testid="stat-hotspots" className="flex items-center gap-1 text-amber-400">
                  <Crosshair className="h-3.5 w-3.5" />
                  {sharedPresence.length} hot spots
                </span>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function EmptyState({ icon: Icon, message }: { icon: typeof AlertCircle; message: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-12 px-4 text-center">
      <Icon className="h-8 w-8 text-text-muted mb-2" />
      <p className="text-sm text-text-muted">{message}</p>
    </div>
  );
}
