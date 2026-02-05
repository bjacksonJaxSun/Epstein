import { useState } from 'react';
import { useParams, useNavigate } from 'react-router';
import {
  User,
  ArrowLeft,
  GitBranch,
  Calendar,
  FileText,
  DollarSign,
  MessageSquare,
  Image,
  AlertTriangle,
} from 'lucide-react';
import {
  ConfidenceBadge,
  LoadingSpinner,
  DataTable,
} from '@/components/shared';
import {
  usePersonDetail,
  usePersonRelationships,
  usePersonEvents,
  usePersonDocuments,
  usePersonFinancials,
  usePersonMedia,
} from '@/hooks';
import { cn } from '@/lib/utils';
import type { Column } from '@/components/shared';
import type {
  Relationship,
  TimelineEvent,
  Document,
  FinancialTransaction,
  MediaFile,
} from '@/types';

type TabId =
  | 'overview'
  | 'relationships'
  | 'events'
  | 'documents'
  | 'financial'
  | 'communications'
  | 'media';

const tabs: Array<{ id: TabId; label: string; icon: typeof User }> = [
  { id: 'overview', label: 'Overview', icon: User },
  { id: 'relationships', label: 'Relationships', icon: GitBranch },
  { id: 'events', label: 'Events', icon: Calendar },
  { id: 'documents', label: 'Documents', icon: FileText },
  { id: 'financial', label: 'Financial', icon: DollarSign },
  { id: 'communications', label: 'Communications', icon: MessageSquare },
  { id: 'media', label: 'Media', icon: Image },
];

function formatDate(dateStr: string | undefined): string {
  if (!dateStr) return '--';
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

function formatCurrency(amount: number, currency?: string): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: currency ?? 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(amount);
}

function formatFileSize(bytes: number | undefined): string {
  if (!bytes) return '--';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function InfoRow({
  label,
  value,
}: {
  label: string;
  value: string | undefined;
}) {
  return (
    <div className="flex items-start gap-4 py-2">
      <span className="w-32 shrink-0 text-xs font-medium uppercase tracking-wider text-text-tertiary">
        {label}
      </span>
      <span className="text-sm text-text-primary">{value ?? '--'}</span>
    </div>
  );
}

/* ----------------------------------------------------------------
 * Tab Content Components
 * ---------------------------------------------------------------- */

function OverviewTab({ personId }: { personId: number }) {
  const { data: person } = usePersonDetail(personId);
  if (!person) return null;

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
      {/* Key Information */}
      <div className="rounded-lg border border-border-subtle bg-surface-raised p-5">
        <h4 className="mb-3 text-sm font-semibold uppercase tracking-wider text-text-tertiary">
          Key Information
        </h4>
        <div className="flex flex-col divide-y divide-border-subtle">
          <InfoRow label="Nationality" value={person.nationality} />
          <InfoRow label="Occupation" value={person.occupation} />
          <InfoRow
            label="Date of Birth"
            value={formatDate(person.dateOfBirth)}
          />
          <InfoRow label="Primary Role" value={person.primaryRole} />
          <InfoRow
            label="Redacted"
            value={person.isRedacted ? 'Yes' : 'No'}
          />
          {person.victimIdentifier && (
            <InfoRow
              label="Victim ID"
              value={person.victimIdentifier}
            />
          )}
        </div>
      </div>

      {/* Additional Details */}
      <div className="flex flex-col gap-6">
        {/* Name Variations */}
        {person.nameVariations && person.nameVariations.length > 0 && (
          <div className="rounded-lg border border-border-subtle bg-surface-raised p-5">
            <h4 className="mb-3 text-sm font-semibold uppercase tracking-wider text-text-tertiary">
              Name Variations / Aliases
            </h4>
            <div className="flex flex-wrap gap-2">
              {person.nameVariations.map((name) => (
                <span
                  key={name}
                  className="rounded-md bg-surface-overlay px-2.5 py-1 text-xs text-text-secondary"
                >
                  {name}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Roles */}
        {person.roles && person.roles.length > 0 && (
          <div className="rounded-lg border border-border-subtle bg-surface-raised p-5">
            <h4 className="mb-3 text-sm font-semibold uppercase tracking-wider text-text-tertiary">
              Known Roles
            </h4>
            <div className="flex flex-wrap gap-2">
              {person.roles.map((role) => (
                <span
                  key={role}
                  className="rounded-md bg-accent-blue/10 px-2.5 py-1 text-xs text-accent-blue"
                >
                  {role}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Contact Information */}
        {((person.emailAddresses && person.emailAddresses.length > 0) ||
          (person.phoneNumbers && person.phoneNumbers.length > 0) ||
          (person.addresses && person.addresses.length > 0)) && (
          <div className="rounded-lg border border-border-subtle bg-surface-raised p-5">
            <h4 className="mb-3 text-sm font-semibold uppercase tracking-wider text-text-tertiary">
              Contact Information
            </h4>
            <div className="flex flex-col divide-y divide-border-subtle">
              {person.emailAddresses?.map((email) => (
                <InfoRow key={email} label="Email" value={email} />
              ))}
              {person.phoneNumbers?.map((phone) => (
                <InfoRow key={phone} label="Phone" value={phone} />
              ))}
              {person.addresses?.map((addr) => (
                <InfoRow key={addr} label="Address" value={addr} />
              ))}
            </div>
          </div>
        )}

        {/* Notes */}
        {person.notes && (
          <div className="rounded-lg border border-border-subtle bg-surface-raised p-5">
            <h4 className="mb-3 text-sm font-semibold uppercase tracking-wider text-text-tertiary">
              Notes
            </h4>
            <p className="whitespace-pre-wrap text-sm leading-relaxed text-text-secondary">
              {person.notes}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

function RelationshipsTab({ personId }: { personId: number }) {
  const navigate = useNavigate();
  const { data, isLoading, isError } = usePersonRelationships(personId);

  const columns: Column<Relationship>[] = [
    {
      key: 'relatedPerson',
      header: 'Related Person',
      render: (rel) => {
        const otherId =
          rel.person1Id === personId ? rel.person2Id : rel.person1Id;
        const otherName =
          rel.person1Id === personId ? rel.person2Name : rel.person1Name;
        return (
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              navigate(`/people/${otherId}`);
            }}
            className="font-medium text-accent-blue transition-colors hover:text-accent-blue/80 hover:underline"
          >
            {otherName}
          </button>
        );
      },
    },
    {
      key: 'relationshipType',
      header: 'Type',
      render: (rel) => (
        <span className="rounded bg-surface-overlay px-2 py-0.5 text-xs text-text-secondary">
          {rel.relationshipType}
        </span>
      ),
    },
    {
      key: 'relationshipDescription',
      header: 'Description',
      render: (rel) => (
        <span className="text-text-secondary">
          {rel.relationshipDescription ?? '--'}
        </span>
      ),
    },
    {
      key: 'confidenceLevel',
      header: 'Confidence',
      width: '120px',
      render: (rel) =>
        rel.confidenceLevel ? (
          <ConfidenceBadge level={rel.confidenceLevel} />
        ) : (
          <span className="text-text-disabled">--</span>
        ),
    },
    {
      key: 'dates',
      header: 'Period',
      width: '160px',
      render: (rel) => (
        <span className="text-xs text-text-tertiary">
          {rel.startDate ? formatDate(rel.startDate) : '--'}
          {rel.endDate ? ` - ${formatDate(rel.endDate)}` : ''}
          {rel.isCurrent ? ' (Current)' : ''}
        </span>
      ),
    },
  ];

  if (isError) {
    return (
      <div className="flex items-center justify-center py-12 text-sm text-text-disabled">
        Failed to load relationships.
      </div>
    );
  }

  return (
    <DataTable<Relationship>
      data={data ?? []}
      columns={columns}
      loading={isLoading}
      emptyMessage="No relationships recorded for this person."
      keyExtractor={(rel) => rel.relationshipId}
    />
  );
}

function EventsTab({ personId }: { personId: number }) {
  const { data, isLoading, isError } = usePersonEvents(personId);

  const columns: Column<TimelineEvent>[] = [
    {
      key: 'eventDate',
      header: 'Date',
      width: '130px',
      render: (event) => (
        <span className="text-xs text-text-tertiary">
          {formatDate(event.eventDate)}
        </span>
      ),
    },
    {
      key: 'title',
      header: 'Title',
      render: (event) => (
        <span className="font-medium text-text-primary">
          {event.title ?? '--'}
        </span>
      ),
    },
    {
      key: 'eventType',
      header: 'Type',
      width: '140px',
      render: (event) => (
        <span className="rounded bg-surface-overlay px-2 py-0.5 text-xs text-text-secondary">
          {event.eventType}
        </span>
      ),
    },
    {
      key: 'locationName',
      header: 'Location',
      render: (event) => (
        <span className="text-text-secondary">
          {event.locationName ?? '--'}
        </span>
      ),
    },
    {
      key: 'participants',
      header: 'Participants',
      render: (event) => (
        <span className="text-xs text-text-secondary">
          {event.participantNames && event.participantNames.length > 0
            ? event.participantNames.join(', ')
            : '--'}
        </span>
      ),
    },
  ];

  if (isError) {
    return (
      <div className="flex items-center justify-center py-12 text-sm text-text-disabled">
        Failed to load events.
      </div>
    );
  }

  return (
    <DataTable<TimelineEvent>
      data={data ?? []}
      columns={columns}
      loading={isLoading}
      emptyMessage="No events recorded for this person."
      keyExtractor={(event) => event.eventId}
    />
  );
}

function DocumentsTab({ personId }: { personId: number }) {
  const { data, isLoading, isError } = usePersonDocuments(personId);

  const columns: Column<Document>[] = [
    {
      key: 'eftaNumber',
      header: 'EFTA #',
      width: '120px',
      render: (doc) => (
        <span className="font-mono text-xs text-text-primary">
          {doc.eftaNumber}
        </span>
      ),
    },
    {
      key: 'documentTitle',
      header: 'Title',
      render: (doc) => (
        <span className="text-text-primary">
          {doc.documentTitle ?? doc.subject ?? '--'}
        </span>
      ),
    },
    {
      key: 'documentType',
      header: 'Type',
      width: '120px',
      render: (doc) => (
        <span className="rounded bg-surface-overlay px-2 py-0.5 text-xs text-text-secondary">
          {doc.documentType ?? '--'}
        </span>
      ),
    },
    {
      key: 'documentDate',
      header: 'Date',
      width: '130px',
      render: (doc) => (
        <span className="text-xs text-text-tertiary">
          {formatDate(doc.documentDate)}
        </span>
      ),
    },
    {
      key: 'pageCount',
      header: 'Pages',
      width: '80px',
      render: (doc) => (
        <span className="text-text-secondary">
          {doc.pageCount ?? '--'}
        </span>
      ),
    },
  ];

  if (isError) {
    return (
      <div className="flex items-center justify-center py-12 text-sm text-text-disabled">
        Failed to load documents.
      </div>
    );
  }

  return (
    <DataTable<Document>
      data={data ?? []}
      columns={columns}
      loading={isLoading}
      emptyMessage="No documents reference this person."
      keyExtractor={(doc) => doc.documentId}
    />
  );
}

function FinancialTab({ personId }: { personId: number }) {
  const { data, isLoading, isError } = usePersonFinancials(personId);

  const columns: Column<FinancialTransaction>[] = [
    {
      key: 'transactionDate',
      header: 'Date',
      width: '130px',
      render: (tx) => (
        <span className="text-xs text-text-tertiary">
          {formatDate(tx.transactionDate)}
        </span>
      ),
    },
    {
      key: 'transactionType',
      header: 'Type',
      width: '120px',
      render: (tx) => (
        <span className="rounded bg-surface-overlay px-2 py-0.5 text-xs text-text-secondary">
          {tx.transactionType ?? '--'}
        </span>
      ),
    },
    {
      key: 'amount',
      header: 'Amount',
      width: '140px',
      render: (tx) => (
        <span className="font-medium text-text-primary">
          {formatCurrency(tx.amount, tx.currency)}
        </span>
      ),
    },
    {
      key: 'fromName',
      header: 'From',
      render: (tx) => (
        <span className="text-text-secondary">{tx.fromName ?? '--'}</span>
      ),
    },
    {
      key: 'toName',
      header: 'To',
      render: (tx) => (
        <span className="text-text-secondary">{tx.toName ?? '--'}</span>
      ),
    },
    {
      key: 'purpose',
      header: 'Purpose',
      render: (tx) => (
        <span className="text-text-secondary">{tx.purpose ?? '--'}</span>
      ),
    },
  ];

  if (isError) {
    return (
      <div className="flex items-center justify-center py-12 text-sm text-text-disabled">
        Failed to load financial data.
      </div>
    );
  }

  return (
    <DataTable<FinancialTransaction>
      data={data ?? []}
      columns={columns}
      loading={isLoading}
      emptyMessage="No financial transactions for this person."
      keyExtractor={(tx) => tx.transactionId}
    />
  );
}

function CommunicationsTab() {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-lg border border-border-subtle bg-surface-raised py-16">
      <MessageSquare className="h-10 w-10 text-text-disabled" />
      <p className="text-sm text-text-disabled">
        Communications data will be available in a future update.
      </p>
    </div>
  );
}

function MediaTab({ personId }: { personId: number }) {
  const { data, isLoading, isError } = usePersonMedia(personId);

  const columns: Column<MediaFile>[] = [
    {
      key: 'fileName',
      header: 'File Name',
      render: (file) => (
        <span className="font-medium text-text-primary">{file.fileName}</span>
      ),
    },
    {
      key: 'mediaType',
      header: 'Type',
      width: '100px',
      render: (file) => (
        <span className="rounded bg-surface-overlay px-2 py-0.5 text-xs capitalize text-text-secondary">
          {file.mediaType}
        </span>
      ),
    },
    {
      key: 'fileFormat',
      header: 'Format',
      width: '100px',
      render: (file) => (
        <span className="font-mono text-xs text-text-tertiary">
          {file.fileFormat ?? '--'}
        </span>
      ),
    },
    {
      key: 'fileSizeBytes',
      header: 'Size',
      width: '100px',
      render: (file) => (
        <span className="text-xs text-text-tertiary">
          {formatFileSize(file.fileSizeBytes)}
        </span>
      ),
    },
    {
      key: 'dateTaken',
      header: 'Date',
      width: '130px',
      render: (file) => (
        <span className="text-xs text-text-tertiary">
          {formatDate(file.dateTaken)}
        </span>
      ),
    },
    {
      key: 'caption',
      header: 'Caption',
      render: (file) => (
        <span className="truncate text-text-secondary">
          {file.caption ?? '--'}
        </span>
      ),
    },
  ];

  if (isError) {
    return (
      <div className="flex items-center justify-center py-12 text-sm text-text-disabled">
        Failed to load media files.
      </div>
    );
  }

  return (
    <DataTable<MediaFile>
      data={data ?? []}
      columns={columns}
      loading={isLoading}
      emptyMessage="No media files associated with this person."
      keyExtractor={(file) => file.mediaFileId}
    />
  );
}

/* ----------------------------------------------------------------
 * Main PersonDetailPage
 * ---------------------------------------------------------------- */

export function PersonDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<TabId>('overview');

  const personId = Number(id);
  const { data: person, isLoading, isError } = usePersonDetail(personId);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-24">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  if (isError || !person) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 py-24">
        <AlertTriangle className="h-12 w-12 text-accent-red" />
        <h2 className="text-lg font-semibold text-text-primary">
          Person Not Found
        </h2>
        <p className="text-sm text-text-secondary">
          Could not load person with ID {id}. They may not exist or the API may
          be unavailable.
        </p>
        <button
          type="button"
          onClick={() => navigate('/people')}
          className="rounded-md bg-accent-blue px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-accent-blue/80"
        >
          Back to People
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      {/* Back button */}
      <button
        type="button"
        onClick={() => navigate('/people')}
        className="flex w-fit items-center gap-1.5 text-sm text-text-secondary transition-colors hover:text-text-primary"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to People
      </button>

      {/* Header Section */}
      <div className="rounded-lg border border-border-subtle bg-surface-raised p-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div className="flex items-start gap-4">
            <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-full bg-entity-person/15 text-entity-person">
              <User className="h-7 w-7" />
            </div>
            <div className="flex flex-col gap-1">
              <h2 className="text-2xl font-semibold text-text-primary">
                {person.fullName}
              </h2>
              {person.primaryRole && (
                <p className="text-sm text-text-secondary">
                  {person.primaryRole}
                </p>
              )}
              <ConfidenceBadge level={person.confidenceLevel} />
            </div>
          </div>
        </div>

        {/* Quick stats */}
        <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-5">
          <QuickStat
            icon={GitBranch}
            label="Relationships"
            value={person.relationshipCount ?? 0}
          />
          <QuickStat
            icon={Calendar}
            label="Events"
            value={person.eventCount ?? 0}
          />
          <QuickStat
            icon={FileText}
            label="Documents"
            value={person.documentCount ?? 0}
          />
          <QuickStat
            icon={DollarSign}
            label="Financial"
            value={person.financialTransactionCount ?? 0}
          />
          <QuickStat
            icon={Image}
            label="Media"
            value={person.mediaCount ?? 0}
          />
        </div>
      </div>

      {/* Tab Navigation */}
      <div className="border-b border-border-subtle">
        <nav className="-mb-px flex gap-0 overflow-x-auto" aria-label="Person detail tabs">
          {tabs.map((tab) => {
            const TabIcon = tab.icon;
            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveTab(tab.id)}
                className={cn(
                  'flex shrink-0 items-center gap-2 border-b-2 px-4 py-3 text-sm font-medium transition-colors',
                  activeTab === tab.id
                    ? 'border-accent-blue text-text-primary'
                    : 'border-transparent text-text-secondary hover:text-text-primary'
                )}
                aria-selected={activeTab === tab.id}
                role="tab"
              >
                <TabIcon className="h-4 w-4" />
                {tab.label}
              </button>
            );
          })}
        </nav>
      </div>

      {/* Tab Content */}
      <div>
        {activeTab === 'overview' && <OverviewTab personId={personId} />}
        {activeTab === 'relationships' && (
          <RelationshipsTab personId={personId} />
        )}
        {activeTab === 'events' && <EventsTab personId={personId} />}
        {activeTab === 'documents' && <DocumentsTab personId={personId} />}
        {activeTab === 'financial' && <FinancialTab personId={personId} />}
        {activeTab === 'communications' && <CommunicationsTab />}
        {activeTab === 'media' && <MediaTab personId={personId} />}
      </div>
    </div>
  );
}

/* ----------------------------------------------------------------
 * Small helper component for the header quick stats
 * ---------------------------------------------------------------- */

function QuickStat({
  icon: Icon,
  label,
  value,
}: {
  icon: typeof User;
  label: string;
  value: number;
}) {
  return (
    <div className="flex items-center gap-2 rounded-md bg-surface-overlay px-3 py-2">
      <Icon className="h-4 w-4 text-text-tertiary" />
      <div className="flex flex-col">
        <span className="text-lg font-semibold text-text-primary">
          {value.toLocaleString()}
        </span>
        <span className="text-xs text-text-tertiary">{label}</span>
      </div>
    </div>
  );
}
