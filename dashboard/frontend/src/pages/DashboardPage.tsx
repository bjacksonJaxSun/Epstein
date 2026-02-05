import { useNavigate } from 'react-router';
import {
  FileText,
  Users,
  Building2,
  Calendar,
  MapPin,
  DollarSign,
  Image,
  GitBranch,
  ArrowRight,
  Network,
  Clock,
  BarChart3,
  AlertTriangle,
} from 'lucide-react';
import { StatCard, ConfidenceBadge, LoadingSpinner } from '@/components/shared';
import { useDashboardStats, useTopPeople, useRecentEvents } from '@/hooks';
import { useSelectionStore } from '@/stores/useSelectionStore';
import { cn } from '@/lib/utils';
import type { DashboardStats } from '@/types';

function formatEventDate(dateStr: string): string {
  try {
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  } catch {
    return dateStr;
  }
}

const statConfig: Array<{
  key: keyof DashboardStats;
  label: string;
  icon: typeof FileText;
  iconColor: string;
}> = [
  { key: 'totalDocuments', label: 'Documents', icon: FileText, iconColor: 'text-entity-document' },
  { key: 'totalPeople', label: 'People', icon: Users, iconColor: 'text-entity-person' },
  { key: 'totalOrganizations', label: 'Organizations', icon: Building2, iconColor: 'text-entity-organization' },
  { key: 'totalEvents', label: 'Events', icon: Calendar, iconColor: 'text-entity-event' },
  { key: 'totalLocations', label: 'Locations', icon: MapPin, iconColor: 'text-entity-location' },
  { key: 'totalFinancialTransactions', label: 'Transactions', icon: DollarSign, iconColor: 'text-entity-financial' },
  { key: 'totalMediaFiles', label: 'Media Files', icon: Image, iconColor: 'text-accent-pink' },
  { key: 'totalRelationships', label: 'Relationships', icon: GitBranch, iconColor: 'text-accent-cyan' },
];

const quickActions = [
  { label: 'Network Graph', path: '/network', icon: Network },
  { label: 'Timeline', path: '/timeline', icon: Clock },
  { label: 'Financial', path: '/financial', icon: BarChart3 },
  { label: 'Documents', path: '/documents', icon: FileText },
];

function StatsLoadingSkeleton() {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {Array.from({ length: 8 }).map((_, i) => (
        <div
          key={i}
          className="rounded-lg border border-border-subtle bg-surface-raised p-4"
        >
          <div className="flex items-start justify-between">
            <div className="flex flex-col gap-2">
              <div className="h-3 w-20 animate-pulse rounded bg-surface-overlay" />
              <div className="h-7 w-16 animate-pulse rounded bg-surface-overlay" />
            </div>
            <div className="h-10 w-10 animate-pulse rounded-lg bg-surface-overlay" />
          </div>
        </div>
      ))}
    </div>
  );
}

function ErrorMessage({ message }: { message: string }) {
  return (
    <div className="flex items-center gap-3 rounded-lg border border-accent-red/30 bg-accent-red/10 p-4">
      <AlertTriangle className="h-5 w-5 shrink-0 text-accent-red" />
      <p className="text-sm text-text-secondary">{message}</p>
    </div>
  );
}

export function DashboardPage() {
  const navigate = useNavigate();
  const selectEntity = useSelectionStore((s) => s.selectEntity);
  const statsQuery = useDashboardStats();
  const topPeopleQuery = useTopPeople(10);
  const recentEventsQuery = useRecentEvents(10);

  return (
    <div className="flex flex-col gap-6">
      {/* Page header */}
      <div>
        <h2 className="text-xl font-semibold text-text-primary">Overview</h2>
        <p className="mt-1 text-sm text-text-secondary">
          Investigative analysis dashboard -- summary of all extracted data.
        </p>
      </div>

      {/* Stats grid */}
      {statsQuery.isLoading ? (
        <StatsLoadingSkeleton />
      ) : statsQuery.isError ? (
        <ErrorMessage message="Failed to load dashboard statistics. Check API connection." />
      ) : statsQuery.data ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {statConfig.map((stat) => (
            <StatCard
              key={stat.key}
              label={stat.label}
              value={statsQuery.data[stat.key]}
              icon={stat.icon}
              iconColor={stat.iconColor}
            />
          ))}
        </div>
      ) : null}

      {/* Two-column section: Top People + Recent Events */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {/* Most Connected People */}
        <div className="rounded-lg border border-border-subtle bg-surface-raised p-6">
          <div className="mb-4 flex items-center justify-between">
            <h3 className="text-sm font-semibold uppercase tracking-wider text-text-tertiary">
              Most Connected People
            </h3>
            <button
              type="button"
              onClick={() => navigate('/people')}
              className="flex items-center gap-1 text-xs text-accent-blue transition-colors hover:text-accent-blue/80"
            >
              View all <ArrowRight className="h-3 w-3" />
            </button>
          </div>

          {topPeopleQuery.isLoading ? (
            <LoadingSpinner className="py-12" />
          ) : topPeopleQuery.isError ? (
            <div className="flex items-center justify-center py-12 text-sm text-text-disabled">
              Unable to load people data.
            </div>
          ) : !topPeopleQuery.data?.items?.length ? (
            <div className="flex items-center justify-center py-12 text-sm text-text-disabled">
              No people data available yet.
            </div>
          ) : (
            <div className="flex flex-col">
              {topPeopleQuery.data.items.map((person, idx) => (
                <button
                  key={person.personId}
                  type="button"
                  onClick={() => navigate(`/people/${person.personId}`)}
                  className={cn(
                    'flex items-center gap-3 px-3 py-2.5 text-left transition-colors hover:bg-surface-overlay rounded-md',
                    idx < topPeopleQuery.data.items.length - 1 && 'border-b border-border-subtle'
                  )}
                >
                  <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-surface-overlay text-xs font-medium text-text-tertiary">
                    {idx + 1}
                  </span>
                  <div className="flex flex-1 flex-col min-w-0">
                    <span className="truncate text-sm font-medium text-text-primary">
                      {person.fullName}
                    </span>
                    {person.primaryRole && (
                      <span className="truncate text-xs text-text-tertiary">
                        {person.primaryRole}
                      </span>
                    )}
                  </div>
                  <ConfidenceBadge level={person.confidenceLevel} />
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Recent Events */}
        <div className="rounded-lg border border-border-subtle bg-surface-raised p-6">
          <div className="mb-4 flex items-center justify-between">
            <h3 className="text-sm font-semibold uppercase tracking-wider text-text-tertiary">
              Recent Events
            </h3>
            <button
              type="button"
              onClick={() => navigate('/timeline')}
              className="flex items-center gap-1 text-xs text-accent-blue transition-colors hover:text-accent-blue/80"
            >
              View all <ArrowRight className="h-3 w-3" />
            </button>
          </div>

          {recentEventsQuery.isLoading ? (
            <LoadingSpinner className="py-12" />
          ) : recentEventsQuery.isError ? (
            <div className="flex items-center justify-center py-12 text-sm text-text-disabled">
              Unable to load events data.
            </div>
          ) : !recentEventsQuery.data?.items?.length ? (
            <div className="flex items-center justify-center py-12 text-sm text-text-disabled">
              No events data available yet.
            </div>
          ) : (
            <div className="flex flex-col">
              {recentEventsQuery.data.items.map((event, idx) => (
                <button
                  key={event.eventId}
                  type="button"
                  onClick={() =>
                    selectEntity(String(event.eventId), 'event')
                  }
                  className={cn(
                    'flex items-start gap-3 px-3 py-3 text-left transition-colors hover:bg-surface-overlay rounded-md',
                    idx < recentEventsQuery.data.items.length - 1 && 'border-b border-border-subtle'
                  )}
                >
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-entity-event/15 text-entity-event">
                    <Calendar className="h-4 w-4" />
                  </div>
                  <div className="flex flex-1 flex-col gap-1 min-w-0">
                    <span className="truncate text-sm font-medium text-text-primary">
                      {event.title ?? event.eventType}
                    </span>
                    <div className="flex items-center gap-2 text-xs text-text-tertiary">
                      <span>{formatEventDate(event.eventDate)}</span>
                      <span className="rounded bg-surface-overlay px-1.5 py-0.5 text-text-secondary">
                        {event.eventType}
                      </span>
                    </div>
                    {event.participantNames && event.participantNames.length > 0 && (
                      <span className="truncate text-xs text-text-secondary">
                        {event.participantNames.slice(0, 3).join(', ')}
                        {event.participantNames.length > 3 &&
                          ` +${event.participantNames.length - 3} more`}
                      </span>
                    )}
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Quick Actions */}
      <div className="rounded-lg border border-border-subtle bg-surface-raised p-4">
        <h3 className="mb-3 text-sm font-semibold uppercase tracking-wider text-text-tertiary">
          Quick Actions
        </h3>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {quickActions.map((action) => (
            <button
              key={action.path}
              type="button"
              onClick={() => navigate(action.path)}
              className="flex items-center gap-3 rounded-lg border border-border-subtle bg-surface-base p-3 transition-colors hover:border-accent-blue/50 hover:bg-surface-overlay"
            >
              <action.icon className="h-5 w-5 text-accent-blue" />
              <span className="text-sm font-medium text-text-primary">
                {action.label}
              </span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
