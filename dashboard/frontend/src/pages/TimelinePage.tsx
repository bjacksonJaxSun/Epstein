import { useState, useCallback, useRef, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Calendar,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  ChevronUp,
  AlertCircle,
  Clock,
  MapPin,
  Users,
  FileText,
  Search,
  X,
  Filter,
} from 'lucide-react';
import { format } from 'date-fns';
import { eventsApi } from '@/api/endpoints/events';
import { searchApi } from '@/api/endpoints/search';
import { LoadingSpinner, ConfidenceBadge } from '@/components/shared';
import { EventTimeline } from '@/components/timeline/EventTimeline';
import { cn } from '@/lib/utils';
import type { TimelineEvent, EntitySearchResult } from '@/types';

const EVENT_TYPES = [
  'meeting',
  'travel',
  'phone_call',
  'legal_proceeding',
  'financial_transaction',
  'arrest',
  'testimony',
  'party',
  'other',
];

function formatDate(dateStr: string | undefined): string {
  if (!dateStr) return '--';
  try {
    return format(new Date(dateStr), 'MMMM d, yyyy');
  } catch {
    return dateStr;
  }
}

function formatDuration(minutes: number | undefined): string {
  if (!minutes) return '';
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;
  return mins > 0 ? `${hours}h ${mins}m` : `${hours}h`;
}

function EventTypeBadge({ type }: { type: string }) {
  const colors: Record<string, string> = {
    meeting: 'bg-accent-blue/15 text-accent-blue border-accent-blue/30',
    travel: 'bg-accent-green/15 text-accent-green border-accent-green/30',
    phone_call: 'bg-accent-amber/15 text-accent-amber border-accent-amber/30',
    legal_proceeding: 'bg-accent-purple/15 text-accent-purple border-accent-purple/30',
    financial_transaction: 'bg-entity-financial/15 text-entity-financial border-entity-financial/30',
    arrest: 'bg-accent-red/15 text-accent-red border-accent-red/30',
    testimony: 'bg-accent-orange/15 text-accent-orange border-accent-orange/30',
    party: 'bg-accent-pink/15 text-accent-pink border-accent-pink/30',
  };
  const style = colors[type] ?? 'bg-border-subtle text-text-secondary border-border-default';

  return (
    <span
      className={cn(
        'inline-flex items-center rounded-sm border px-1.5 py-0.5 text-xs font-medium',
        style
      )}
    >
      {type.replace(/_/g, ' ')}
    </span>
  );
}

export function TimelinePage() {
  const [page, setPage] = useState(1);
  const [selectedTypes, setSelectedTypes] = useState<string[]>([]);
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [expandedEvents, setExpandedEvents] = useState<Set<number>>(new Set());
  const [selectedTimelineEventId, setSelectedTimelineEventId] = useState<number | null>(null);
  const [personSearchQuery, setPersonSearchQuery] = useState('');
  const [selectedPersonIds, setSelectedPersonIds] = useState<number[]>([]);
  const [selectedPersonNames, setSelectedPersonNames] = useState<Map<number, string>>(new Map());
  const [showPersonDropdown, setShowPersonDropdown] = useState(false);
  const [_visibleRange, setVisibleRange] = useState<{ start: Date; end: Date } | null>(null);

  const personSearchRef = useRef<HTMLInputElement>(null);
  const personDropdownRef = useRef<HTMLDivElement>(null);
  const eventCardRefs = useRef<Map<number, HTMLDivElement>>(new Map());

  // Timeline event data (large batch for vis-timeline)
  const {
    data: timelineData,
    isLoading: isTimelineLoading,
  } = useQuery({
    queryKey: ['timeline-events', selectedTypes, dateFrom, dateTo, selectedPersonIds],
    queryFn: () =>
      eventsApi.list({
        pageSize: 500,
        page: 1,
        dateFrom: dateFrom || undefined,
        dateTo: dateTo || undefined,
        eventType: selectedTypes.length === 1 ? selectedTypes[0] : undefined,
      }),
  });

  // Paginated event list below timeline
  const { data: listData, isLoading: isListLoading, isError: isListError } = useQuery({
    queryKey: ['events', page, selectedTypes, dateFrom, dateTo],
    queryFn: () =>
      eventsApi.list({
        page,
        pageSize: 20,
        dateFrom: dateFrom || undefined,
        dateTo: dateTo || undefined,
        eventType: selectedTypes.length === 1 ? selectedTypes[0] : undefined,
      }),
  });

  // Person search
  const { data: personResults, isLoading: isPersonSearching } = useQuery({
    queryKey: ['person-search', personSearchQuery],
    queryFn: () => searchApi.entities({ query: personSearchQuery, types: 'person' }),
    enabled: personSearchQuery.length >= 2,
    staleTime: 30_000,
  });

  const timelineEvents = timelineData?.items ?? [];
  const events = listData?.items ?? [];
  const pagination = listData;

  function toggleType(type: string) {
    setSelectedTypes((prev) =>
      prev.includes(type) ? prev.filter((t) => t !== type) : [...prev, type]
    );
    setPage(1);
  }

  function toggleExpanded(eventId: number) {
    setExpandedEvents((prev) => {
      const next = new Set(prev);
      if (next.has(eventId)) {
        next.delete(eventId);
      } else {
        next.add(eventId);
      }
      return next;
    });
  }

  function clearFilters() {
    setSelectedTypes([]);
    setDateFrom('');
    setDateTo('');
    setSelectedPersonIds([]);
    setSelectedPersonNames(new Map());
    setPersonSearchQuery('');
    setPage(1);
  }

  const hasFilters =
    selectedTypes.length > 0 ||
    dateFrom !== '' ||
    dateTo !== '' ||
    selectedPersonIds.length > 0;

  const handleTimelineSelect = useCallback((eventId: number) => {
    setSelectedTimelineEventId(eventId);
    setExpandedEvents((prev) => {
      const next = new Set(prev);
      next.add(eventId);
      return next;
    });
    // Scroll to event card if visible
    setTimeout(() => {
      const ref = eventCardRefs.current.get(eventId);
      if (ref) {
        ref.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }, 100);
  }, []);

  const handleRangeChange = useCallback((start: Date, end: Date) => {
    setVisibleRange({ start, end });
  }, []);

  const addPersonFilter = useCallback((person: EntitySearchResult) => {
    setSelectedPersonIds((prev) =>
      prev.includes(person.id) ? prev : [...prev, person.id]
    );
    setSelectedPersonNames((prev) => {
      const next = new Map(prev);
      next.set(person.id, person.name);
      return next;
    });
    setPersonSearchQuery('');
    setShowPersonDropdown(false);
    setPage(1);
  }, []);

  const removePersonFilter = useCallback((personId: number) => {
    setSelectedPersonIds((prev) => prev.filter((id) => id !== personId));
    setSelectedPersonNames((prev) => {
      const next = new Map(prev);
      next.delete(personId);
      return next;
    });
    setPage(1);
  }, []);

  // Close person dropdown on outside click
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      const target = event.target as Node;
      if (
        personDropdownRef.current &&
        !personDropdownRef.current.contains(target) &&
        personSearchRef.current &&
        !personSearchRef.current.contains(target)
      ) {
        setShowPersonDropdown(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div>
        <h2 className="text-xl font-semibold text-text-primary">Event Timeline</h2>
        <p className="mt-1 text-sm text-text-secondary">
          Chronological timeline of events extracted from the document corpus.
        </p>
      </div>

      {/* Filter Controls */}
      <div className="flex flex-wrap items-start gap-4 rounded-lg border border-border-subtle bg-surface-raised px-4 py-3">
        {/* Event Type Multi-Select */}
        <div className="flex flex-col gap-2">
          <span className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-text-tertiary">
            <Filter className="h-3 w-3" />
            Event Types
          </span>
          <div className="flex flex-wrap gap-1.5">
            {EVENT_TYPES.map((type) => (
              <button
                key={type}
                type="button"
                onClick={() => toggleType(type)}
                className={cn(
                  'rounded-md border px-2.5 py-1 text-xs font-medium transition-colors',
                  selectedTypes.includes(type)
                    ? 'border-accent-blue bg-accent-blue/15 text-accent-blue'
                    : 'border-border-subtle bg-surface-sunken text-text-secondary hover:bg-surface-overlay'
                )}
              >
                {type.replace(/_/g, ' ')}
              </button>
            ))}
          </div>
        </div>

        {/* Date Range */}
        <div className="flex flex-col gap-2">
          <span className="text-xs font-semibold uppercase tracking-wider text-text-tertiary">
            Date Range
          </span>
          <div className="flex items-center gap-1.5">
            <input
              type="date"
              value={dateFrom}
              onChange={(e) => { setDateFrom(e.target.value); setPage(1); }}
              className="rounded-md border border-border-subtle bg-surface-sunken px-2 py-1.5 text-xs text-text-primary focus:border-accent-blue focus:outline-none [color-scheme:dark]"
            />
            <span className="text-xs text-text-tertiary">to</span>
            <input
              type="date"
              value={dateTo}
              onChange={(e) => { setDateTo(e.target.value); setPage(1); }}
              className="rounded-md border border-border-subtle bg-surface-sunken px-2 py-1.5 text-xs text-text-primary focus:border-accent-blue focus:outline-none [color-scheme:dark]"
            />
          </div>
        </div>

        {/* Person Filter */}
        <div className="flex flex-col gap-2">
          <span className="text-xs font-semibold uppercase tracking-wider text-text-tertiary">
            Person Filter
          </span>
          <div className="relative">
            <Search className="absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-text-tertiary" />
            <input
              ref={personSearchRef}
              type="text"
              value={personSearchQuery}
              onChange={(e) => {
                setPersonSearchQuery(e.target.value);
                setShowPersonDropdown(e.target.value.length >= 2);
              }}
              onFocus={() => {
                if (personSearchQuery.length >= 2) setShowPersonDropdown(true);
              }}
              placeholder="Filter by person..."
              className="w-48 rounded-md border border-border-subtle bg-surface-sunken py-1.5 pl-7 pr-3 text-xs text-text-primary placeholder:text-text-disabled focus:border-accent-blue focus:outline-none"
            />
            {showPersonDropdown && (
              <div
                ref={personDropdownRef}
                className="absolute left-0 top-full z-30 mt-1 w-64 rounded-md border border-border-subtle bg-surface-overlay shadow-lg"
              >
                {isPersonSearching && (
                  <div className="flex items-center gap-2 px-3 py-2.5">
                    <div className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-accent-blue border-t-transparent" />
                    <span className="text-xs text-text-tertiary">Searching...</span>
                  </div>
                )}
                {!isPersonSearching && personResults && personResults.length === 0 && (
                  <div className="px-3 py-2.5 text-xs text-text-disabled">No results</div>
                )}
                {!isPersonSearching &&
                  personResults &&
                  personResults.length > 0 &&
                  personResults.slice(0, 8).map((r) => (
                    <button
                      key={r.id}
                      type="button"
                      onClick={() => addPersonFilter(r)}
                      disabled={selectedPersonIds.includes(r.id)}
                      className={cn(
                        'flex w-full items-center gap-2 px-3 py-2 text-left text-xs transition-colors',
                        selectedPersonIds.includes(r.id)
                          ? 'text-text-disabled cursor-not-allowed'
                          : 'text-text-primary hover:bg-surface-elevated'
                      )}
                    >
                      <span className="inline-block h-2 w-2 shrink-0 rounded-full bg-accent-blue" />
                      <span className="truncate">{r.name}</span>
                    </button>
                  ))}
              </div>
            )}
          </div>
          {/* Selected person chips */}
          {selectedPersonIds.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {selectedPersonIds.map((id) => (
                <span
                  key={id}
                  className="inline-flex items-center gap-1 rounded-md border border-accent-blue/30 bg-accent-blue/10 px-2 py-0.5 text-xs text-accent-blue"
                >
                  {selectedPersonNames.get(id) ?? `Person ${id}`}
                  <button
                    type="button"
                    onClick={() => removePersonFilter(id)}
                    className="ml-0.5 rounded-sm hover:bg-accent-blue/20"
                  >
                    <X className="h-3 w-3" />
                  </button>
                </span>
              ))}
            </div>
          )}
        </div>

        {/* Reset Filters */}
        {hasFilters && (
          <div className="flex flex-col gap-2">
            <span className="text-xs font-semibold uppercase tracking-wider text-transparent">
              Reset
            </span>
            <button
              type="button"
              onClick={clearFilters}
              className="rounded-md border border-border-subtle bg-surface-sunken px-3 py-1.5 text-xs font-medium text-text-secondary transition-colors hover:bg-surface-overlay hover:text-text-primary"
            >
              Reset Filters
            </button>
          </div>
        )}
      </div>

      {/* vis-timeline Visualization */}
      <EventTimeline
        events={timelineEvents}
        isLoading={isTimelineLoading}
        onSelectEvent={handleTimelineSelect}
        onRangeChange={handleRangeChange}
      />

      {/* Event List */}
      <div className="flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-text-primary">Event Details</h3>
          {pagination && (
            <span className="text-xs text-text-tertiary">
              {pagination.totalCount.toLocaleString()} total events
            </span>
          )}
        </div>

        {isListLoading && <LoadingSpinner className="py-24" />}

        {isListError && (
          <div className="flex flex-col items-center justify-center gap-3 rounded-lg border border-accent-red/30 bg-accent-red/5 py-12">
            <AlertCircle className="h-8 w-8 text-accent-red" />
            <p className="text-sm text-accent-red">Failed to load events.</p>
          </div>
        )}

        {!isListLoading && !isListError && events.length === 0 && (
          <div className="flex flex-col items-center justify-center gap-3 rounded-lg border border-border-subtle bg-surface-raised py-16">
            <Calendar className="h-10 w-10 text-text-disabled" />
            <p className="text-sm text-text-disabled">No events found.</p>
          </div>
        )}

        {!isListLoading && !isListError && events.length > 0 && (
          <div className="relative">
            {/* Vertical timeline line */}
            <div className="absolute left-[7.5rem] top-0 bottom-0 w-px bg-border-subtle" />

            <div className="flex flex-col gap-3">
              {events.map((event) => (
                <EventCard
                  key={event.eventId}
                  event={event}
                  isExpanded={expandedEvents.has(event.eventId)}
                  isHighlighted={selectedTimelineEventId === event.eventId}
                  onToggle={() => toggleExpanded(event.eventId)}
                  onRef={(el) => {
                    if (el) {
                      eventCardRefs.current.set(event.eventId, el);
                    } else {
                      eventCardRefs.current.delete(event.eventId);
                    }
                  }}
                />
              ))}
            </div>
          </div>
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

function EventCard({
  event,
  isExpanded,
  isHighlighted,
  onToggle,
  onRef,
}: {
  event: TimelineEvent;
  isExpanded: boolean;
  isHighlighted: boolean;
  onToggle: () => void;
  onRef: (el: HTMLDivElement | null) => void;
}) {
  return (
    <div className="flex gap-4 pl-2" ref={onRef}>
      {/* Date Column */}
      <div className="w-24 shrink-0 pt-3 text-right">
        <div className="text-sm font-semibold text-text-primary">
          {formatDate(event.eventDate)}
        </div>
        {event.eventTime && (
          <div className="text-xs text-text-tertiary">{event.eventTime}</div>
        )}
      </div>

      {/* Timeline dot */}
      <div className="relative z-10 mt-4 h-3 w-3 shrink-0 rounded-full border-2 border-accent-blue bg-surface-base" />

      {/* Event Card */}
      <div
        className={cn(
          'flex-1 rounded-lg border transition-colors',
          isHighlighted
            ? 'border-accent-blue bg-accent-blue/5'
            : 'border-border-subtle bg-surface-raised hover:border-border-default'
        )}
      >
        <button
          type="button"
          onClick={onToggle}
          className="w-full p-4 text-left"
        >
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2 mb-1">
                <EventTypeBadge type={event.eventType} />
                {event.confidenceLevel && (
                  <ConfidenceBadge level={event.confidenceLevel} />
                )}
                {event.durationMinutes !== undefined && event.durationMinutes > 0 && (
                  <span className="flex items-center gap-1 text-xs text-text-tertiary">
                    <Clock className="h-3 w-3" />
                    {formatDuration(event.durationMinutes)}
                  </span>
                )}
              </div>
              <h4 className="text-sm font-medium text-text-primary">
                {event.title ?? (event.description ? (event.description.length > 100 ? event.description.substring(0, 97) + '...' : event.description) : 'Untitled Event')}
              </h4>
              {event.locationName && (
                <div className="mt-1 flex items-center gap-1 text-xs text-text-secondary">
                  <MapPin className="h-3 w-3 text-entity-location" />
                  {event.locationName}
                </div>
              )}
            </div>
            <div className="shrink-0 text-text-tertiary">
              {isExpanded ? (
                <ChevronUp className="h-4 w-4" />
              ) : (
                <ChevronDown className="h-4 w-4" />
              )}
            </div>
          </div>
        </button>

        {/* Expanded Details */}
        {isExpanded && (
          <div className="border-t border-border-subtle px-4 pb-4 pt-3">
            {event.description && (
              <div className="mb-3">
                <div className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-text-tertiary mb-1">
                  <FileText className="h-3 w-3" />
                  Description
                </div>
                <p className="text-sm text-text-secondary leading-relaxed">
                  {event.description}
                </p>
              </div>
            )}

            {event.participantNames && event.participantNames.length > 0 && (
              <div className="mb-3">
                <div className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-text-tertiary mb-1.5">
                  <Users className="h-3 w-3" />
                  Participants ({event.participantNames.length})
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {event.participantNames.map((name) => (
                    <span
                      key={name}
                      className="inline-flex items-center rounded-md border border-border-subtle bg-surface-overlay px-2 py-0.5 text-xs text-text-secondary"
                    >
                      {name}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {event.endDate && (
              <div className="text-xs text-text-tertiary">
                End date: {formatDate(event.endDate)}
                {event.endTime && ` at ${event.endTime}`}
              </div>
            )}

            {event.verificationStatus && (
              <div className="mt-2 text-xs text-text-tertiary">
                Verification: <span className="capitalize">{event.verificationStatus}</span>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
