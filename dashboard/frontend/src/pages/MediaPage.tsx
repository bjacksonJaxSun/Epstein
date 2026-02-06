import { useState, useRef, useCallback, useEffect, useMemo } from 'react';
import { useInfiniteQuery } from '@tanstack/react-query';
import {
  Image,
  Video,
  Film,
  FileAudio,
  FileText,
  AlertCircle,
  AlertTriangle,
  X,
  MapPin,
  Camera,
  User,
  Calendar,
  Loader2,
  Bookmark,
  ImageIcon,
  ZoomIn,
  ZoomOut,
  RotateCw,
  Maximize2,
  Download,
} from 'lucide-react';
import { format } from 'date-fns';
import { mediaApi } from '@/api/endpoints/media';
import { LoadingSpinner } from '@/components/shared';
import { cn } from '@/lib/utils';
import { useBookmarkStore } from '@/stores/useBookmarkStore';
import type { MediaFile } from '@/types';

type MediaTab = 'all' | 'image' | 'video' | 'audio' | 'document' | 'bookmarked';

const TABS: { key: MediaTab; label: string; icon: typeof Image }[] = [
  { key: 'all', label: 'All', icon: Image },
  { key: 'image', label: 'Images', icon: Image },
  { key: 'video', label: 'Video', icon: Video },
  { key: 'audio', label: 'Audio', icon: FileAudio },
  { key: 'document', label: 'Documents', icon: FileText },
  { key: 'bookmarked', label: 'Bookmarked', icon: Bookmark },
];

const PAGE_SIZE = 48;

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
  const [selectedMedia, setSelectedMedia] = useState<MediaFile | null>(null);
  const [lightboxMedia, setLightboxMedia] = useState<MediaFile | null>(null);
  const loadMoreRef = useRef<HTMLDivElement>(null);

  const { bookmarks, addBookmark, removeBookmark, isBookmarked: checkIsBookmarked, getBookmark } = useBookmarkStore();

  const mediaBookmarks = useMemo(() =>
    bookmarks.filter((b) => b.entityType === 'media'),
    [bookmarks]
  );
  const bookmarkCount = mediaBookmarks.length;

  const isBookmarked = useCallback(
    (mediaId: number) => checkIsBookmarked(mediaId, 'media'),
    [checkIsBookmarked]
  );

  const toggleBookmark = useCallback(
    (media: MediaFile) => {
      if (checkIsBookmarked(media.mediaFileId, 'media')) {
        const bookmark = getBookmark(media.mediaFileId, 'media');
        if (bookmark) {
          removeBookmark(bookmark.id);
        }
      } else {
        addBookmark({
          entityId: media.mediaFileId,
          entityType: 'media',
          label: media.fileName ?? `Media #${media.mediaFileId}`,
          tags: [media.mediaType],
        });
      }
    },
    [checkIsBookmarked, getBookmark, removeBookmark, addBookmark]
  );

  const handleOpenDocument = (documentId: number) => {
    // Open the source PDF in a new tab
    window.open(`/api/documents/${documentId}/file`, '_blank');
  };

  const handleOpenLightbox = (media: MediaFile) => {
    if (media.mediaType === 'image') {
      setLightboxMedia(media);
    } else if (media.sourceDocumentId) {
      handleOpenDocument(media.sourceDocumentId);
    }
  };

  const isBookmarkedTab = activeTab === 'bookmarked';

  // For bookmarked tab, we fetch 'all' and filter client-side
  const queryMediaType = isBookmarkedTab ? undefined : (activeTab !== 'all' ? activeTab : undefined);

  const {
    data,
    isLoading,
    isError,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
  } = useInfiniteQuery({
    queryKey: ['media-infinite', isBookmarkedTab ? 'all' : activeTab],
    queryFn: async ({ pageParam = 1 }) => {
      const result = await mediaApi.list({
        page: pageParam,
        pageSize: PAGE_SIZE,
        mediaType: queryMediaType,
      });
      return result;
    },
    getNextPageParam: (lastPage) => {
      if (lastPage.page < lastPage.totalPages - 1) {
        return lastPage.page + 2; // API uses 0-based pages, we use 1-based
      }
      return undefined;
    },
    initialPageParam: 1,
  });

  // Intersection Observer for infinite scroll
  const handleObserver = useCallback(
    (entries: IntersectionObserverEntry[]) => {
      const [entry] = entries;
      if (entry.isIntersecting && hasNextPage && !isFetchingNextPage) {
        fetchNextPage();
      }
    },
    [fetchNextPage, hasNextPage, isFetchingNextPage]
  );

  useEffect(() => {
    const element = loadMoreRef.current;
    if (!element) return;

    const observer = new IntersectionObserver(handleObserver, {
      root: null,
      rootMargin: '200px',
      threshold: 0,
    });

    observer.observe(element);
    return () => observer.disconnect();
  }, [handleObserver]);

  const allApiItems = data?.pages.flatMap((page) => page.items) ?? [];
  const totalCount = data?.pages[0]?.totalCount ?? 0;

  // For bookmarked tab, we need to fetch all bookmarked items
  // For now, filter from loaded items (user can scroll to load more first)
  const allItems = useMemo(() => {
    if (isBookmarkedTab) {
      return allApiItems.filter((item) => checkIsBookmarked(item.mediaFileId, 'media'));
    }
    return allApiItems;
  }, [isBookmarkedTab, allApiItems, checkIsBookmarked]);

  const displayCount = isBookmarkedTab ? bookmarkCount : totalCount;

  function handleTabChange(tab: MediaTab) {
    setActiveTab(tab);
    setSelectedMedia(null);
  }

  return (
    <div className="flex flex-col gap-6">
      {/* Header with Total Count */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-text-primary">Media Gallery</h2>
          <p className="mt-1 text-sm text-text-secondary">
            Browse images, videos, and other media files
          </p>
        </div>
        {/* Total Count Badge */}
        <div className="flex items-center gap-4">
          {bookmarkCount > 0 && (
            <div className="flex items-center gap-2 rounded-lg border border-accent-amber/30 bg-accent-amber/10 px-3 py-2">
              <Bookmark className="h-4 w-4 text-accent-amber" />
              <span className="text-sm font-medium text-accent-amber">
                {bookmarkCount.toLocaleString()} Bookmarked
              </span>
            </div>
          )}
          <div className="flex items-center gap-2 rounded-lg border border-accent-blue/30 bg-accent-blue/10 px-4 py-2">
            <ImageIcon className="h-5 w-5 text-accent-blue" />
            <div className="flex flex-col">
              <span className="text-lg font-bold text-accent-blue">
                {totalCount.toLocaleString()}
              </span>
              <span className="text-xs text-accent-blue/70">Total Media Files</span>
            </div>
          </div>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="flex flex-wrap items-center gap-4">
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

          {!isLoading && !isError && allItems.length === 0 && (
            <div className="flex flex-col items-center justify-center gap-3 rounded-lg border border-border-subtle bg-surface-raised py-16">
              {isBookmarkedTab ? (
                <>
                  <Bookmark className="h-10 w-10 text-text-disabled" />
                  <p className="text-sm text-text-disabled">No bookmarked media files.</p>
                  <p className="text-xs text-text-disabled">
                    Click the bookmark icon on any media file to add it here.
                  </p>
                </>
              ) : (
                <>
                  <Image className="h-10 w-10 text-text-disabled" />
                  <p className="text-sm text-text-disabled">No media files found.</p>
                </>
              )}
            </div>
          )}

          {!isLoading && !isError && allItems.length > 0 && (
            <>
              <div className="grid grid-cols-3 gap-2 sm:grid-cols-4 lg:grid-cols-6 xl:grid-cols-8">
                {allItems.map((media) => (
                  <MediaCard
                    key={media.mediaFileId}
                    media={media}
                    isSelected={selectedMedia?.mediaFileId === media.mediaFileId}
                    isBookmarked={isBookmarked(media.mediaFileId)}
                    onSelect={() => setSelectedMedia(media)}
                    onDoubleClick={() => handleOpenLightbox(media)}
                    onToggleBookmark={() => toggleBookmark(media)}
                  />
                ))}
              </div>

              {/* Load More Trigger */}
              <div ref={loadMoreRef} className="flex justify-center py-8">
                {isBookmarkedTab ? (
                  <p className="text-xs text-text-disabled">
                    {allItems.length > 0
                      ? `Showing ${allItems.length} of ${bookmarkCount} bookmarked items`
                      : 'No bookmarked items'}
                  </p>
                ) : isFetchingNextPage ? (
                  <div className="flex items-center gap-2 text-sm text-text-secondary">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Loading more...
                  </div>
                ) : hasNextPage ? (
                  <button
                    onClick={() => fetchNextPage()}
                    className="rounded-md border border-border-subtle bg-surface-raised px-4 py-2 text-sm text-text-secondary hover:bg-surface-overlay"
                  >
                    Load More
                  </button>
                ) : allItems.length > 0 ? (
                  <p className="text-xs text-text-disabled">
                    All {totalCount.toLocaleString()} items loaded
                  </p>
                ) : null}
              </div>
            </>
          )}
        </div>

        {/* Detail Sidebar */}
        {selectedMedia && (
          <MediaDetailSidebar
            media={selectedMedia}
            isBookmarked={isBookmarked(selectedMedia.mediaFileId)}
            onClose={() => setSelectedMedia(null)}
            onToggleBookmark={() => toggleBookmark(selectedMedia)}
          />
        )}
      </div>

      {/* Image Lightbox */}
      {lightboxMedia && (
        <ImageLightbox
          media={lightboxMedia}
          onClose={() => setLightboxMedia(null)}
        />
      )}
    </div>
  );
}

function MediaCard({
  media,
  isSelected,
  isBookmarked,
  onSelect,
  onDoubleClick,
  onToggleBookmark,
}: {
  media: MediaFile;
  isSelected: boolean;
  isBookmarked: boolean;
  onSelect: () => void;
  onDoubleClick: () => void;
  onToggleBookmark: () => void;
}) {
  const Icon = getMediaIcon(media.mediaType);
  const [imgError, setImgError] = useState(false);

  const imageUrl = `/api/media/${media.mediaFileId}/file`;

  const handleBookmarkClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    onToggleBookmark();
  };

  return (
    <button
      type="button"
      onClick={onSelect}
      onDoubleClick={onDoubleClick}
      className={cn(
        'flex flex-col rounded-lg border text-left transition-colors relative group',
        isSelected
          ? 'border-accent-blue ring-2 ring-accent-blue/30'
          : 'border-border-subtle bg-surface-raised hover:border-border-default'
      )}
    >
      {/* Bookmark Button */}
      <div
        role="button"
        tabIndex={0}
        onClick={handleBookmarkClick}
        onKeyDown={(e) => e.key === 'Enter' && handleBookmarkClick(e as unknown as React.MouseEvent)}
        className={cn(
          'absolute top-1 right-1 z-10 flex h-6 w-6 items-center justify-center rounded-md transition-all',
          isBookmarked
            ? 'bg-accent-amber text-white'
            : 'bg-black/50 text-white opacity-0 group-hover:opacity-100 hover:bg-accent-amber'
        )}
      >
        <Bookmark className={cn('h-3.5 w-3.5', isBookmarked && 'fill-current')} />
      </div>

      {/* Thumbnail */}
      <div className="flex aspect-square items-center justify-center rounded-t-lg bg-surface-sunken overflow-hidden relative">
        {media.mediaType === 'image' && !imgError ? (
          <img
            src={imageUrl}
            alt={media.fileName}
            className="h-full w-full object-cover"
            onError={() => setImgError(true)}
            loading="lazy"
          />
        ) : media.mediaType === 'video' ? (
          <>
            <Film className="h-8 w-8 text-text-disabled" />
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="flex h-8 w-8 items-center justify-center rounded-full bg-accent-purple/80">
                <Video className="h-4 w-4 text-white" />
              </div>
            </div>
          </>
        ) : (
          <Icon className="h-8 w-8 text-text-disabled" />
        )}
      </div>

      {/* Compact Info */}
      <div className="p-1.5">
        <p className="text-[10px] font-medium text-text-primary truncate">
          {media.fileName}
        </p>
        <div className="flex items-center gap-1 mt-0.5">
          <span className="text-[9px] text-text-tertiary uppercase">
            {media.mediaType}
          </span>
          {media.fileSizeBytes !== undefined && (
            <span className="text-[9px] text-text-disabled">
              {formatFileSize(media.fileSizeBytes)}
            </span>
          )}
        </div>
      </div>
    </button>
  );
}

function MediaDetailSidebar({
  media,
  isBookmarked,
  onClose,
  onToggleBookmark,
}: {
  media: MediaFile;
  isBookmarked: boolean;
  onClose: () => void;
  onToggleBookmark: () => void;
}) {
  const Icon = getMediaIcon(media.mediaType);
  const [imgError, setImgError] = useState(false);

  const imageUrl = `/api/media/${media.mediaFileId}/file`;

  return (
    <div className="w-[35%] shrink-0 overflow-y-auto rounded-lg border border-border-subtle bg-surface-raised max-h-[calc(100vh-200px)] sticky top-4">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border-subtle p-4">
        <h3 className="text-sm font-semibold text-text-primary">Media Details</h3>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onToggleBookmark}
            className={cn(
              'flex items-center gap-1.5 rounded-md px-2 py-1 text-xs font-medium transition-colors',
              isBookmarked
                ? 'bg-accent-amber text-white'
                : 'bg-surface-overlay text-text-secondary hover:bg-accent-amber/20 hover:text-accent-amber'
            )}
          >
            <Bookmark className={cn('h-3.5 w-3.5', isBookmarked && 'fill-current')} />
            {isBookmarked ? 'Bookmarked' : 'Bookmark'}
          </button>
          <button
            type="button"
            onClick={onClose}
            className="text-text-tertiary hover:text-text-primary"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Preview */}
      <div className="flex aspect-video items-center justify-center bg-surface-sunken overflow-hidden">
        {media.mediaType === 'image' && !imgError ? (
          <img
            src={imageUrl}
            alt={media.fileName}
            className="h-full w-full object-contain"
            onError={() => setImgError(true)}
          />
        ) : media.mediaType === 'video' ? (
          <div className="flex flex-col items-center gap-2 w-full h-full">
            <video
              src={imageUrl}
              controls
              className="flex-1 w-full"
              preload="metadata"
            >
              Your browser does not support the video tag.
            </video>
            <a
              href={imageUrl}
              download={media.fileName}
              className="flex items-center gap-1.5 rounded-md bg-accent-purple px-3 py-1.5 text-xs font-medium text-white hover:bg-accent-purple/80 transition-colors"
            >
              <Film className="h-3.5 w-3.5" />
              Download Video
            </a>
          </div>
        ) : media.mediaType === 'audio' ? (
          <div className="flex flex-col items-center gap-4 p-4">
            <Icon className="h-16 w-16 text-text-disabled" />
            <audio src={imageUrl} controls className="w-full">
              Your browser does not support the audio tag.
            </audio>
          </div>
        ) : (
          <Icon className="h-16 w-16 text-text-disabled" />
        )}
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

function ImageLightbox({
  media,
  onClose,
}: {
  media: MediaFile;
  onClose: () => void;
}) {
  const [scale, setScale] = useState(1);
  const [rotation, setRotation] = useState(0);
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const containerRef = useRef<HTMLDivElement>(null);

  const imageUrl = `/api/media/${media.mediaFileId}/file`;

  const handleZoomIn = () => setScale((s) => Math.min(s * 1.5, 10));
  const handleZoomOut = () => setScale((s) => Math.max(s / 1.5, 0.1));
  const handleRotate = () => setRotation((r) => (r + 90) % 360);
  const handleReset = () => {
    setScale(1);
    setRotation(0);
    setPosition({ x: 0, y: 0 });
  };

  const handleWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault();
    const delta = e.deltaY > 0 ? 0.9 : 1.1;
    setScale((s) => Math.max(0.1, Math.min(10, s * delta)));
  }, []);

  const handleMouseDown = (e: React.MouseEvent) => {
    if (e.button !== 0) return;
    setIsDragging(true);
    setDragStart({ x: e.clientX - position.x, y: e.clientY - position.y });
  };

  const handleMouseMove = useCallback(
    (e: React.MouseEvent) => {
      if (!isDragging) return;
      setPosition({
        x: e.clientX - dragStart.x,
        y: e.clientY - dragStart.y,
      });
    },
    [isDragging, dragStart]
  );

  const handleMouseUp = () => setIsDragging(false);

  // Handle keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      switch (e.key) {
        case 'Escape':
          onClose();
          break;
        case '+':
        case '=':
          handleZoomIn();
          break;
        case '-':
          handleZoomOut();
          break;
        case 'r':
          handleRotate();
          break;
        case '0':
          handleReset();
          break;
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  // Prevent body scroll when lightbox is open
  useEffect(() => {
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = '';
    };
  }, []);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/90"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      {/* Toolbar */}
      <div className="absolute top-4 left-1/2 -translate-x-1/2 z-10 flex items-center gap-1 rounded-lg bg-surface-raised/90 backdrop-blur-sm border border-border-subtle p-1">
        <button
          type="button"
          onClick={handleZoomOut}
          className="flex h-8 w-8 items-center justify-center rounded-md text-text-secondary hover:bg-surface-overlay hover:text-text-primary transition-colors"
          title="Zoom Out (-)"
        >
          <ZoomOut className="h-4 w-4" />
        </button>
        <span className="px-2 text-xs text-text-secondary min-w-[4rem] text-center">
          {Math.round(scale * 100)}%
        </span>
        <button
          type="button"
          onClick={handleZoomIn}
          className="flex h-8 w-8 items-center justify-center rounded-md text-text-secondary hover:bg-surface-overlay hover:text-text-primary transition-colors"
          title="Zoom In (+)"
        >
          <ZoomIn className="h-4 w-4" />
        </button>
        <div className="w-px h-6 bg-border-subtle mx-1" />
        <button
          type="button"
          onClick={handleRotate}
          className="flex h-8 w-8 items-center justify-center rounded-md text-text-secondary hover:bg-surface-overlay hover:text-text-primary transition-colors"
          title="Rotate (R)"
        >
          <RotateCw className="h-4 w-4" />
        </button>
        <button
          type="button"
          onClick={handleReset}
          className="flex h-8 w-8 items-center justify-center rounded-md text-text-secondary hover:bg-surface-overlay hover:text-text-primary transition-colors"
          title="Reset View (0)"
        >
          <Maximize2 className="h-4 w-4" />
        </button>
        <div className="w-px h-6 bg-border-subtle mx-1" />
        <a
          href={imageUrl}
          download={media.fileName}
          className="flex h-8 w-8 items-center justify-center rounded-md text-text-secondary hover:bg-surface-overlay hover:text-text-primary transition-colors"
          title="Download"
        >
          <Download className="h-4 w-4" />
        </a>
      </div>

      {/* Close Button */}
      <button
        type="button"
        onClick={onClose}
        className="absolute top-4 right-4 z-10 flex h-10 w-10 items-center justify-center rounded-full bg-surface-raised/90 backdrop-blur-sm border border-border-subtle text-text-secondary hover:bg-surface-overlay hover:text-text-primary transition-colors"
        title="Close (Esc)"
      >
        <X className="h-5 w-5" />
      </button>

      {/* Image Container */}
      <div
        ref={containerRef}
        className="relative w-full h-full flex items-center justify-center overflow-hidden cursor-grab active:cursor-grabbing"
        onWheel={handleWheel}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
      >
        <img
          src={imageUrl}
          alt={media.fileName}
          className="max-w-none select-none"
          style={{
            transform: `translate(${position.x}px, ${position.y}px) scale(${scale}) rotate(${rotation}deg)`,
            transition: isDragging ? 'none' : 'transform 0.1s ease-out',
          }}
          draggable={false}
        />
      </div>

      {/* File Name */}
      <div className="absolute bottom-4 left-1/2 -translate-x-1/2 z-10 rounded-lg bg-surface-raised/90 backdrop-blur-sm border border-border-subtle px-4 py-2">
        <p className="text-sm text-text-primary font-medium">{media.fileName}</p>
        {media.widthPixels && media.heightPixels && (
          <p className="text-xs text-text-tertiary text-center">
            {media.widthPixels} x {media.heightPixels} px
          </p>
        )}
      </div>
    </div>
  );
}
