import { useEffect, useRef, useCallback } from 'react';
import { Timeline } from 'vis-timeline/standalone';
import { DataSet } from 'vis-data';
import 'vis-timeline/styles/vis-timeline-graph2d.min.css';
import './timeline-dark.css';
import type { TimelineEvent } from '@/types';
import { useSelectionStore } from '@/stores/useSelectionStore';
import { LoadingSpinner } from '@/components/shared';

interface EventTimelineProps {
  events: TimelineEvent[];
  isLoading: boolean;
  onSelectEvent: (eventId: number) => void;
  onRangeChange: (start: Date, end: Date) => void;
}

interface TimelineItem {
  id: number;
  content: string;
  start: string;
  end?: string;
  type: 'point' | 'range';
  group: string;
  className: string;
  title: string;
}

interface TimelineGroup {
  id: string;
  content: string;
  order: number;
}

const GROUP_CONFIG: TimelineGroup[] = [
  { id: 'meeting', content: 'Meetings', order: 1 },
  { id: 'travel', content: 'Travel', order: 2 },
  { id: 'phone_call', content: 'Calls', order: 3 },
  { id: 'legal_proceeding', content: 'Legal', order: 4 },
  { id: 'financial_transaction', content: 'Financial', order: 5 },
  { id: 'arrest', content: 'Arrests', order: 6 },
  { id: 'testimony', content: 'Testimony', order: 7 },
  { id: 'party', content: 'Social', order: 8 },
  { id: 'other', content: 'Other', order: 9 },
];

function resolveGroup(eventType: string): string {
  const match = GROUP_CONFIG.find((g) => g.id === eventType);
  return match ? match.id : 'other';
}

function buildTooltip(event: TimelineEvent): string {
  const parts: string[] = [];
  if (event.title) parts.push(`<strong>${escapeHtml(event.title)}</strong>`);
  parts.push(`Type: ${escapeHtml(event.eventType.replace(/_/g, ' '))}`);
  if (event.eventDate) parts.push(`Date: ${escapeHtml(event.eventDate)}`);
  if (event.locationName) parts.push(`Location: ${escapeHtml(event.locationName)}`);
  if (event.participantNames && event.participantNames.length > 0) {
    parts.push(`Participants: ${event.participantNames.map(escapeHtml).join(', ')}`);
  }
  if (event.confidenceLevel) parts.push(`Confidence: ${escapeHtml(event.confidenceLevel)}`);
  return parts.join('<br/>');
}

function escapeHtml(str: string): string {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

function transformEvents(events: TimelineEvent[]): TimelineItem[] {
  return events
    .filter((e) => e.eventDate)
    .map((e) => ({
      id: e.eventId,
      content: e.title ?? e.eventType.replace(/_/g, ' '),
      start: e.eventDate,
      end: e.endDate ?? undefined,
      type: e.endDate ? ('range' as const) : ('point' as const),
      group: resolveGroup(e.eventType),
      className: `event-${e.eventType}`,
      title: buildTooltip(e),
    }));
}

function getUsedGroups(events: TimelineEvent[]): TimelineGroup[] {
  const usedTypes = new Set(events.map((e) => resolveGroup(e.eventType)));
  return GROUP_CONFIG.filter((g) => usedTypes.has(g.id));
}

export function EventTimeline({
  events,
  isLoading,
  onSelectEvent,
  onRangeChange,
}: EventTimelineProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const timelineRef = useRef<Timeline | null>(null);
  const itemsRef = useRef<DataSet<TimelineItem> | null>(null);
  const groupsRef = useRef<DataSet<TimelineGroup> | null>(null);
  const selectEntity = useSelectionStore((s) => s.selectEntity);

  const initTimeline = useCallback(() => {
    if (!containerRef.current) return;

    if (timelineRef.current) {
      timelineRef.current.destroy();
    }

    const items = new DataSet<TimelineItem>([]);
    const groups = new DataSet<TimelineGroup>([]);

    itemsRef.current = items;
    groupsRef.current = groups;

    const options = {
      height: '400px',
      start: new Date(2000, 0, 1),
      end: new Date(2025, 0, 1),
      zoomMin: 1000 * 60 * 60 * 24 * 30,
      zoomMax: 1000 * 60 * 60 * 24 * 365 * 30,
      orientation: { axis: 'top' as const },
      showCurrentTime: false,
      stack: true,
      stackSubgroups: true,
      margin: { item: { horizontal: 5, vertical: 5 } },
      tooltip: { followMouse: true, overflowMethod: 'cap' as const },
      selectable: true,
      multiselect: false,
      snap: null,
      groupOrder: 'order',
    };

    const timeline = new Timeline(containerRef.current, items, groups, options);

    timeline.on('select', (properties: { items: number[] }) => {
      if (properties.items.length > 0) {
        const eventId = properties.items[0];
        onSelectEvent(eventId);
        selectEntity(String(eventId), 'event');
      }
    });

    timeline.on('rangechanged', (properties: { start: Date; end: Date; byUser: boolean }) => {
      if (properties.byUser) {
        onRangeChange(properties.start, properties.end);
      }
    });

    timelineRef.current = timeline;
  }, [onSelectEvent, onRangeChange, selectEntity]);

  useEffect(() => {
    initTimeline();
    return () => {
      timelineRef.current?.destroy();
      timelineRef.current = null;
      itemsRef.current = null;
      groupsRef.current = null;
    };
  }, [initTimeline]);

  useEffect(() => {
    if (!itemsRef.current || !groupsRef.current) return;

    const items = itemsRef.current;
    const groups = groupsRef.current;

    items.clear();
    groups.clear();

    if (events.length > 0) {
      const transformedItems = transformEvents(events);
      const usedGroups = getUsedGroups(events);

      groups.add(usedGroups);
      items.add(transformedItems);

      if (timelineRef.current && transformedItems.length > 0) {
        timelineRef.current.fit({ animation: { duration: 500, easingFunction: 'easeInOutQuad' } });
      }
    }
  }, [events]);

  return (
    <div className="relative rounded-lg border border-border-subtle bg-surface-raised overflow-hidden">
      {isLoading && (
        <div className="absolute inset-0 z-10 flex items-center justify-center bg-surface-base/60 backdrop-blur-sm">
          <LoadingSpinner size="lg" />
        </div>
      )}
      {!isLoading && events.length === 0 && (
        <div className="flex flex-col items-center justify-center gap-3 py-24">
          <svg
            className="h-10 w-10 text-text-disabled"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={1.5}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5"
            />
          </svg>
          <p className="text-sm text-text-disabled">No events found matching your filters</p>
        </div>
      )}
      <div
        ref={containerRef}
        className={events.length === 0 && !isLoading ? 'hidden' : ''}
      />
    </div>
  );
}
