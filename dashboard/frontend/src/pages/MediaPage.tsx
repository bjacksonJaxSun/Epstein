import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Image,
  Video,
  Film,
  FileAudio,
  FileText,
  ChevronLeft,
  ChevronRight,
  AlertCircle,
  AlertTriangle,
  X,
  MapPin,
  Camera,
  User,
  Calendar,
} from 'lucide-react';
import { format } from 'date-fns';
import { mediaApi } from '@/api/endpoints/media';
import { LoadingSpinner } from '@/components/shared';
import { cn } from '@/lib/utils';
import type { MediaFile } from '@/types';

type MediaTab = 'all' | 'image' | 'video' | 'audio' | 'document';

const TABS: { key: MediaTab; label: string; icon: typeof Image }[] = [
  { key: 'all', label: 'All', icon: Image },
  { key: 'image', label: 'Images', icon: Image },
  { key: 'video', label: 'Video', icon: Video },
  { key: 'audio', label: 'Audio', icon: FileAudio },
  { key: 'document', label: 'Documents', icon: FileText },
];

function getMediaIcon(type: MediaFile['mediaType']) {
  switch (type) {
    case 'image': return Image;
    case 'video': return Film;
    case 'audio': return FileAudio;
    case 'document': return FileText;
    default: return FileText;
  }
}

function formatFileSize(bytes: number | undefined): string {
  if (!bytes) return '--';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(dateStr: string | undefined): string {
  if (!dateStr) return '--';
  try {
    return format(new Date(dateStr), 'MMM d, yyyy');
  } catch {
    return dateStr;
  }
}

function formatDuration(seconds: number | undefined): string {
  if (!seconds) return '--';
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${mins}:${String(secs).padStart(2, '0')}`;
}

function MediaTypeBadge({ type }: { type: MediaFile['mediaType'] }) {
  const colors: Record<string, string> = {
    image: 'bg-accent-blue/15 text-accent-blue border-accent-blue/30',
    video: 'bg-accent-purple/15 text-accent-purple border-accent-purple/30',
    audio: 'bg-accent-amber/15 text-accent-amber border-accent-amber/30',
    document: 'bg-border-subtle text-text-secondary border-border-default',
  };

  return (
    <span
      className={cn(
        'inline-flex items-center rounded-sm border px-1.5 py-0.5 text-xs font-medium',
        colors[type] ?? colors.document
      )}
    >
      {type}
    </span>
  );
}

export function MediaPage() {
  const [activeTab, setActiveTab] = useState<MediaTab>('all');
  const [page, setPage] = useState(1);
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [selectedMedia, setSelectedMedia] = useState<MediaFile | null>(null);

  const { data, isLoading, isError } = useQuery({
    queryKey: ['media', activeTab, page, dateFrom, dateTo],
    queryFn: () =>
      mediaApi.list({
        page,
        pageSize: 24,
        mediaType: activeTab !== 'all' ? activeTab : undefined,
      }),
  });

  const items = data?.items ?? [];
  const pagination = data;

  function handleTabChange(tab: MediaTab) {
    setActiveTab(tab);
    setPage(1);
  }

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div>
        <h2 className="text-xl font-semibold text-text-primary">Media Gallery</h2>
        <p className="mt-1 text-sm text-text-secondary">
          Browse images, videos, and other media files with metadata and tagging.
        </p>
      </div>

      {/* Filter Bar */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        {/* Media Type Tabs */}
        <div className="flex items-center rounded-lg border border-border-subtle bg-surface-raised p-0.5">
          {TABS.map(({ key, label, icon: Icon }) => (
            <button
              key={key}
              type="button"
              onClick={() => handleTabChange(key)}
              className={cn(
                'flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors',
                activeTab === key
                  ? 'bg-accent-blue/15 text-accent-blue'
                  : 'text-text-secondary hover:bg-surface-overlay hover:text-text-primary'
              )}
            >
              <Icon className="h-3.5 w-3.5" />
              {label}
            </button>
          ))}
        </div>

        {/* Date Range */}
        <div className="flex items-center gap-1.5">
          <input
            type="date"
            value={dateFrom}
            onChange={(e) => { setDateFrom(e.target.value); setPage(1); }}
            className="rounded-md border border-border-subtle bg-surface-raised px-2 py-1.5 text-xs text-text-primary focus:border-accent-blue focus:outline-none [color-scheme:dark]"
          />
          <span className="text-xs text-text-tertiary">to</span>
          <input
            type="date"
            value={dateTo}
            onChange={(e) => { setDateTo(e.target.value); setPage(1); }}
            className="rounded-md border border-border-subtle bg-surface-raised px-2 py-1.5 text-xs text-text-primary focus:border-accent-blue focus:outline-none [color-scheme:dark]"
          />
        </div>
      </div>

      {/* Content Area */}
      <div className="flex gap-4">
        {/* Gallery Grid */}
        <div className={cn('flex-1', selectedMedia ? 'w-[65%]' : 'w-full')}>
          {isLoading && <LoadingSpinner className="py-24" />}

          {isError && (
            <div className="flex flex-col items-center justify-center gap-3 rounded-lg border border-accent-red/30 bg-accent-red/5 py-12">
              <AlertCircle className="h-8 w-8 text-accent-red" />
              <p className="text-sm text-accent-red">Failed to load media files.</p>
            </div>
          )}

          {!isLoading && !isError && items.length === 0 && (
            <div className="flex flex-col items-center justify-center gap-3 rounded-lg border border-border-subtle bg-surface-raised py-16">
              <Image className="h-10 w-10 text-text-disabled" />
              <p className="text-sm text-text-disabled">No media files found.</p>
            </div>
          )}

          {!isLoading && !isError && items.length > 0 && (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
              {items.map((media) => (
                <MediaCard
                  key={media.mediaFileId}
                  media={media}
                  isSelected={selectedMedia?.mediaFileId === media.mediaFileId}
                  onSelect={() => setSelectedMedia(media)}
                />
              ))}
            </div>
          )}

          {/* Pagination */}
          {pagination && pagination.totalPages > 1 && (
            <div className="mt-4 flex items-center justify-between rounded-lg border border-border-subtle bg-surface-raised p-3">
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

        {/* Detail Sidebar */}
        {selectedMedia && (
          <MediaDetailSidebar
            media={selectedMedia}
            onClose={() => setSelectedMedia(null)}
          />
        )}
      </div>
    </div>
  );
}

function MediaCard({
  media,
  isSelected,
  onSelect,
}: {
  media: MediaFile;
  isSelected: boolean;
  onSelect: () => void;
}) {
  const Icon = getMediaIcon(media.mediaType);

  return (
    <button
      type="button"
      onClick={onSelect}
      className={cn(
        'flex flex-col rounded-lg border text-left transition-colors',
        isSelected
          ? 'border-accent-blue bg-surface-overlay'
          : 'border-border-subtle bg-surface-raised hover:border-border-default'
      )}
    >
      {/* Thumbnail Placeholder */}
      <div className="flex aspect-square items-center justify-center rounded-t-lg bg-surface-sunken">
        <Icon className="h-12 w-12 text-text-disabled" />
      </div>

      {/* Info */}
      <div className="p-3">
        <p className="text-xs font-medium text-text-primary truncate">
          {media.fileName}
        </p>
        <div className="mt-1.5 flex items-center gap-2">
          <MediaTypeBadge type={media.mediaType} />
          {media.fileSizeBytes !== undefined && (
            <span className="text-xs text-text-tertiary">
              {formatFileSize(media.fileSizeBytes)}
            </span>
          )}
        </div>
        {media.dateTaken && (
          <p className="mt-1 text-xs text-text-tertiary">
            {formatDate(media.dateTaken)}
          </p>
        )}

        {/* Warning Badges */}
        <div className="mt-1.5 flex items-center gap-1.5">
          {media.isSensitive && (
            <span className="inline-flex items-center gap-0.5 rounded-sm border border-accent-amber/30 bg-accent-amber/15 px-1.5 py-0.5 text-xs font-medium text-accent-amber">
              <AlertTriangle className="h-3 w-3" />
              Sensitive
            </span>
          )}
          {media.isExplicit && (
            <span className="inline-flex items-center gap-0.5 rounded-sm border border-accent-red/30 bg-accent-red/15 px-1.5 py-0.5 text-xs font-medium text-accent-red">
              <AlertTriangle className="h-3 w-3" />
              Explicit
            </span>
          )}
        </div>
      </div>
    </button>
  );
}

function MediaDetailSidebar({
  media,
  onClose,
}: {
  media: MediaFile;
  onClose: () => void;
}) {
  const Icon = getMediaIcon(media.mediaType);

  return (
    <div className="w-[35%] shrink-0 overflow-y-auto rounded-lg border border-border-subtle bg-surface-raised">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border-subtle p-4">
        <h3 className="text-sm font-semibold text-text-primary">Media Details</h3>
        <button
          type="button"
          onClick={onClose}
          className="text-text-tertiary hover:text-text-primary"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Preview Placeholder */}
      <div className="flex aspect-video items-center justify-center bg-surface-sunken">
        <Icon className="h-16 w-16 text-text-disabled" />
      </div>

      {/* File Info */}
      <div className="border-b border-border-subtle p-4">
        <h4 className="text-sm font-medium text-text-primary break-words">
          {media.fileName}
        </h4>
        <div className="mt-2 flex items-center gap-2">
          <MediaTypeBadge type={media.mediaType} />
          {media.fileFormat && (
            <span className="text-xs text-text-tertiary uppercase">
              {media.fileFormat}
            </span>
          )}
        </div>
        {(media.isSensitive || media.isExplicit) && (
          <div className="mt-2 flex items-center gap-1.5">
            {media.isSensitive && (
              <span className="inline-flex items-center gap-0.5 rounded-sm border border-accent-amber/30 bg-accent-amber/15 px-1.5 py-0.5 text-xs font-medium text-accent-amber">
                <AlertTriangle className="h-3 w-3" />
                Sensitive
              </span>
            )}
            {media.isExplicit && (
              <span className="inline-flex items-center gap-0.5 rounded-sm border border-accent-red/30 bg-accent-red/15 px-1.5 py-0.5 text-xs font-medium text-accent-red">
                <AlertTriangle className="h-3 w-3" />
                Explicit
              </span>
            )}
          </div>
        )}
      </div>

      {/* Full Metadata */}
      <div className="border-b border-border-subtle p-4">
        <h4 className="text-xs font-semibold uppercase tracking-wider text-text-tertiary mb-3">
          Metadata
        </h4>
        <dl className="flex flex-col gap-2 text-xs">
          {media.fileSizeBytes !== undefined && (
            <MetaRow label="File Size" value={formatFileSize(media.fileSizeBytes)} />
          )}
          {media.dateTaken && (
            <MetaRow
              label="Date Taken"
              value={formatDate(media.dateTaken)}
              icon={Calendar}
            />
          )}
          {media.widthPixels !== undefined && media.heightPixels !== undefined && (
            <MetaRow
              label="Dimensions"
              value={`${media.widthPixels} x ${media.heightPixels} px`}
              icon={Camera}
            />
          )}
          {media.durationSeconds !== undefined && (
            <MetaRow
              label="Duration"
              value={formatDuration(media.durationSeconds)}
            />
          )}
          {media.gpsLatitude !== undefined && media.gpsLongitude !== undefined && (
            <MetaRow
              label="GPS"
              value={`${media.gpsLatitude.toFixed(6)}, ${media.gpsLongitude.toFixed(6)}`}
              icon={MapPin}
            />
          )}
        </dl>
      </div>

      {/* AI Analysis */}
      <div className="border-b border-border-subtle p-4">
        <h4 className="text-xs font-semibold uppercase tracking-wider text-text-tertiary mb-3">
          AI Analysis
        </h4>
        {media.caption ? (
          <div className="flex flex-col gap-2">
            <div>
              <span className="text-xs text-text-tertiary">Caption: </span>
              <span className="text-xs text-text-secondary">{media.caption}</span>
            </div>
          </div>
        ) : (
          <p className="text-xs text-text-disabled">No AI analysis available.</p>
        )}
      </div>

      {/* People Identified */}
      <div className="p-4">
        <h4 className="text-xs font-semibold uppercase tracking-wider text-text-tertiary mb-3">
          <div className="flex items-center gap-1.5">
            <User className="h-3 w-3" />
            People Identified
          </div>
        </h4>
        <p className="text-xs text-text-disabled">
          No people identified in this media file.
        </p>
      </div>
    </div>
  );
}

function MetaRow({
  label,
  value,
  icon: Icon,
}: {
  label: string;
  value: string;
  icon?: typeof MapPin;
}) {
  return (
    <div className="flex items-center justify-between">
      <dt className="flex items-center gap-1 text-text-tertiary">
        {Icon && <Icon className="h-3 w-3" />}
        {label}
      </dt>
      <dd className="text-text-secondary">{value}</dd>
    </div>
  );
}
