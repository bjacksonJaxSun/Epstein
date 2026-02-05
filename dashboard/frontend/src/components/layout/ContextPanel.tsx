import { useEffect, useRef } from 'react';
import { useNavigate } from 'react-router';
import {
  X,
  User,
  Building2,
  MapPin,
  Calendar,
  FileText,
  DollarSign,
  ExternalLink,
  Bookmark,
} from 'lucide-react';
import { useSelectionStore } from '@/stores/useSelectionStore';
import { useBookmarkStore } from '@/stores/useBookmarkStore';
import { usePersonDetail, usePersonDocuments } from '@/hooks';
import { ConfidenceBadge, LoadingSpinner } from '@/components/shared';
import { cn } from '@/lib/utils';

const typeConfig: Record<
  string,
  { icon: typeof User; label: string; colorClass: string }
> = {
  person: {
    icon: User,
    label: 'Person',
    colorClass: 'text-entity-person bg-entity-person/15',
  },
  organization: {
    icon: Building2,
    label: 'Organization',
    colorClass: 'text-entity-organization bg-entity-organization/15',
  },
  location: {
    icon: MapPin,
    label: 'Location',
    colorClass: 'text-entity-location bg-entity-location/15',
  },
  event: {
    icon: Calendar,
    label: 'Event',
    colorClass: 'text-entity-event bg-entity-event/15',
  },
  document: {
    icon: FileText,
    label: 'Document',
    colorClass: 'text-entity-document bg-entity-document/15',
  },
  financial: {
    icon: DollarSign,
    label: 'Financial',
    colorClass: 'text-entity-financial bg-entity-financial/15',
  },
};

function InfoRow({
  label,
  value,
}: {
  label: string;
  value: string | undefined | null;
}) {
  if (!value) return null;
  return (
    <div className="flex flex-col gap-0.5 py-1.5">
      <span className="text-xs font-medium uppercase tracking-wider text-text-tertiary">
        {label}
      </span>
      <span className="text-sm text-text-primary">{value}</span>
    </div>
  );
}

function PersonContextContent({ personId }: { personId: number }) {
  const navigate = useNavigate();
  const { data: person, isLoading, isError } = usePersonDetail(personId);
  const { data: documents, isLoading: isLoadingDocs } = usePersonDocuments(personId);

  if (isLoading) {
    return <LoadingSpinner className="py-12" />;
  }

  if (isError || !person) {
    return (
      <div className="flex items-center justify-center py-12 text-sm text-text-disabled">
        Unable to load person details.
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Name and role */}
      <div className="flex flex-col gap-1">
        <h3 className="text-lg font-semibold text-text-primary">
          {person.fullName}
        </h3>
        {person.primaryRole && (
          <p className="text-sm text-text-secondary">{person.primaryRole}</p>
        )}
        <ConfidenceBadge level={person.confidenceLevel} className="mt-1 w-fit" />
      </div>

      {/* Quick stats */}
      <div className="grid grid-cols-3 gap-2">
        <div className="flex flex-col items-center rounded-md bg-surface-overlay px-2 py-2">
          <span className="text-sm font-semibold text-text-primary">
            {person.relationshipCount}
          </span>
          <span className="text-xs text-text-tertiary">Relations</span>
        </div>
        <div className="flex flex-col items-center rounded-md bg-surface-overlay px-2 py-2">
          <span className="text-sm font-semibold text-text-primary">
            {person.eventCount}
          </span>
          <span className="text-xs text-text-tertiary">Events</span>
        </div>
        <div className="flex flex-col items-center rounded-md bg-surface-overlay px-2 py-2">
          <span className="text-sm font-semibold text-text-primary">
            {person.documentCount}
          </span>
          <span className="text-xs text-text-tertiary">Docs</span>
        </div>
      </div>

      {/* Key properties */}
      <div className="flex flex-col divide-y divide-border-subtle rounded-lg border border-border-subtle bg-surface-base p-3">
        <InfoRow label="Nationality" value={person.nationality} />
        <InfoRow label="Occupation" value={person.occupation} />
        <InfoRow label="Date of Birth" value={person.dateOfBirth} />
        <InfoRow
          label="Redacted"
          value={person.isRedacted ? 'Yes' : 'No'}
        />
        {person.notes && <InfoRow label="Notes" value={person.notes} />}
      </div>

      {/* Related Documents */}
      {(documents && documents.length > 0) && (
        <div className="flex flex-col gap-2">
          <h4 className="text-xs font-medium uppercase tracking-wider text-text-tertiary">
            Related Documents ({documents.length})
          </h4>
          <div className="flex flex-col gap-1.5 max-h-48 overflow-y-auto rounded-lg border border-border-subtle bg-surface-base p-2">
            {documents.slice(0, 10).map((doc: any) => (
              <a
                key={doc.documentId}
                href={`/api/documents/${doc.documentId}/file`}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-2 rounded px-2 py-1.5 text-xs text-text-secondary hover:bg-surface-overlay hover:text-text-primary transition-colors"
              >
                <FileText className="h-3.5 w-3.5 shrink-0 text-accent-blue" />
                <span className="truncate flex-1">{doc.eftaNumber}</span>
                {doc.documentType && (
                  <span className="shrink-0 text-text-disabled">{doc.documentType}</span>
                )}
              </a>
            ))}
            {documents.length > 10 && (
              <p className="text-xs text-text-disabled text-center py-1">
                +{documents.length - 10} more documents
              </p>
            )}
          </div>
        </div>
      )}
      {isLoadingDocs && (
        <div className="flex items-center gap-2 text-xs text-text-tertiary">
          <div className="h-3 w-3 animate-spin rounded-full border-2 border-accent-blue border-t-transparent" />
          Loading documents...
        </div>
      )}

      {/* View Full Detail button */}
      <button
        type="button"
        onClick={() => navigate(`/people/${person.personId}`)}
        className="flex items-center justify-center gap-2 rounded-lg bg-accent-blue px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-accent-blue/80"
      >
        <ExternalLink className="h-4 w-4" />
        View Full Detail
      </button>
    </div>
  );
}

function GenericContextContent({
  entityId,
  entityType,
}: {
  entityId: string;
  entityType: string;
}) {
  const config = typeConfig[entityType] ?? typeConfig.document;
  const Icon = config.icon;

  return (
    <div className="flex flex-col items-center justify-center gap-3 py-12 text-center">
      <div className="flex h-16 w-16 items-center justify-center rounded-full bg-surface-overlay">
        <Icon className="h-8 w-8 text-text-disabled" />
      </div>
      <p className="text-sm text-text-secondary">
        {config.label} details panel
      </p>
      <p className="text-xs text-text-tertiary">
        ID: {entityId} | Type: {entityType}
      </p>
      <p className="mt-2 text-xs text-text-disabled">
        Full detail view for this entity type will be available in a future
        update.
      </p>
    </div>
  );
}

export function ContextPanel() {
  const { selectedEntityId, selectedEntityType, clearSelection } =
    useSelectionStore();
  const { isBookmarked, addBookmark, bookmarks, removeBookmark } =
    useBookmarkStore();
  const panelRef = useRef<HTMLElement>(null);

  const config = typeConfig[selectedEntityType ?? ''] ?? typeConfig.document;
  const Icon = config.icon;

  const entityIdNum = selectedEntityId != null ? Number(selectedEntityId) : 0;
  const entityType = selectedEntityType ?? 'document';
  const bookmarked = isBookmarked(entityIdNum, entityType);

  const handleToggleBookmark = () => {
    if (bookmarked) {
      const existing = bookmarks.find(
        (b) => b.entityId === entityIdNum && b.entityType === entityType
      );
      if (existing) {
        removeBookmark(existing.id);
      }
    } else {
      addBookmark({
        entityId: entityIdNum,
        entityType,
        label: `${config.label} #${selectedEntityId}`,
        tags: [],
      });
    }
  };

  // Close on click outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (
        panelRef.current &&
        !panelRef.current.contains(event.target as Node)
      ) {
        clearSelection();
      }
    }

    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [clearSelection]);

  // Close on Escape key
  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        clearSelection();
      }
    }
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [clearSelection]);

  const isPerson =
    selectedEntityType === 'person' && selectedEntityId != null;

  return (
    <aside
      ref={panelRef}
      className="flex h-full w-[400px] shrink-0 flex-col border-l border-border-subtle bg-surface-raised"
    >
      {/* Panel header */}
      <div className="flex h-14 items-center justify-between border-b border-border-subtle px-4">
        <div className="flex items-center gap-3">
          <div
            className={cn(
              'flex h-8 w-8 items-center justify-center rounded-md',
              config.colorClass
            )}
          >
            <Icon className="h-4 w-4" />
          </div>
          <div className="flex flex-col">
            <span className="text-sm font-medium text-text-primary">
              {config.label} #{selectedEntityId}
            </span>
            <span className="text-xs text-text-tertiary">{config.label}</span>
          </div>
        </div>
        <div className="flex items-center gap-1">
          {/* Bookmark toggle */}
          <button
            type="button"
            onClick={handleToggleBookmark}
            className={cn(
              'flex h-7 w-7 items-center justify-center rounded-md transition-colors',
              bookmarked
                ? 'text-accent-amber hover:bg-surface-overlay'
                : 'text-text-secondary hover:bg-surface-overlay hover:text-text-primary'
            )}
            aria-label={bookmarked ? 'Remove bookmark' : 'Add bookmark'}
          >
            <Bookmark
              className="h-4 w-4"
              fill={bookmarked ? 'currentColor' : 'none'}
            />
          </button>
          {/* Close */}
          <button
            type="button"
            onClick={clearSelection}
            className="flex h-7 w-7 items-center justify-center rounded-md text-text-secondary transition-colors hover:bg-surface-overlay hover:text-text-primary"
            aria-label="Close panel"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Panel content */}
      <div className="flex-1 overflow-y-auto p-4">
        {isPerson ? (
          <PersonContextContent personId={Number(selectedEntityId)} />
        ) : (
          <GenericContextContent
            entityId={selectedEntityId ?? ''}
            entityType={selectedEntityType ?? 'document'}
          />
        )}
      </div>
    </aside>
  );
}
