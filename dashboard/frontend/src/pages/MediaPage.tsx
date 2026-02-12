import { useState, useRef, useCallback, useEffect, useMemo } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
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
  Search,
  ArrowRight,
  ChevronLeft,
  ChevronRight,
  ChevronUp,
  ChevronDown,
} from 'lucide-react';
import { format } from 'date-fns';
import { mediaApi } from '@/api/endpoints/media';
import { LoadingSpinner } from '@/components/shared';
import { cn } from '@/lib/utils';
import { useBookmarkStore } from '@/stores/useBookmarkStore';
import type { MediaFile, PaginatedResponse } from '@/types';

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
  const [goToIdInput, setGoToIdInput] = useState('');
  const [goToIdError, setGoToIdError] = useState<string | null>(null);
  const [isJumping, setIsJumping] = useState(false);
  const [excludeDocumentScans, setExcludeDocumentScans] = useState(true); // Hide document scans by default

  // Bi-directional pagination state
  const [loadedPages, setLoadedPages] = useState<Map<number, PaginatedResponse<MediaFile>>>(new Map());
  const [currentStartPage, setCurrentStartPage] = useState(0);
  const [totalInfo, setTotalInfo] = useState({ totalCount: 0, totalPages: 0 });
  const [isLoadingPage, setIsLoadingPage] = useState(false);
  const isLoadingRef = useRef(false); // Ref to track loading state across renders

  const loadMoreTopRef = useRef<HTMLDivElement>(null);
  const loadMoreBottomRef = useRef<HTMLDivElement>(null);
  const topTriggerReady = useRef(true); // Prevents re-triggering until user scrolls away
  const queryClient = useQueryClient();

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
    window.open(`/api/documents/${documentId}/file`, '_blank');
  };

  const isBookmarkedTab = activeTab === 'bookmarked';
  const queryMediaType = isBookmarkedTab ? undefined : (activeTab !== 'all' ? activeTab : undefined);

  // Load a specific page
  const loadPage = useCallback(async (pageNum: number) => {
    // Use ref for immediate check to prevent race conditions
    if (loadedPages.has(pageNum) || isLoadingRef.current) return;

    isLoadingRef.current = true;
    setIsLoadingPage(true);
    try {
      const result = await mediaApi.list({
        page: pageNum + 1, // API uses 1-based for our call, converts to 0-based
        pageSize: PAGE_SIZE,
        mediaType: queryMediaType,
        excludeDocumentScans,
      });
      setLoadedPages(prev => new Map(prev).set(pageNum, result));
      setTotalInfo({ totalCount: result.totalCount, totalPages: result.totalPages });
    } finally {
      isLoadingRef.current = false;
      setIsLoadingPage(false);
    }
  }, [loadedPages, queryMediaType, excludeDocumentScans]);

  // Initial load - page 0
  const { isLoading, isError } = useQuery({
    queryKey: ['media-initial', isBookmarkedTab ? 'all' : activeTab, excludeDocumentScans],
    queryFn: async () => {
      const result = await mediaApi.list({
        page: 1,
        pageSize: PAGE_SIZE,
        mediaType: queryMediaType,
        excludeDocumentScans,
      });
      setLoadedPages(new Map([[0, result]]));
      setCurrentStartPage(0);
      setTotalInfo({ totalCount: result.totalCount, totalPages: result.totalPages });
      return result;
    },
  });

  // Handle "Go to ID" - jump directly to the page containing that ID
  const handleGoToId = async () => {
    const id = parseInt(goToIdInput.trim(), 10);
    if (isNaN(id) || id <= 0) {
      setGoToIdError('Please enter a valid media ID');
      return;
    }

    setGoToIdError(null);
    setIsJumping(true);

    try {
      // Get the position of this media ID from the backend
      const position = await mediaApi.getPosition(id, PAGE_SIZE, queryMediaType, excludeDocumentScans);

      // Load that specific page - clear existing pages first to avoid gaps
      const pageNum = position.page;
      const result = await mediaApi.list({
        page: pageNum + 1,
        pageSize: PAGE_SIZE,
        mediaType: queryMediaType,
        excludeDocumentScans,
      });

      // Replace all loaded pages with just this one page
      setLoadedPages(new Map([[pageNum, result]]));
      setTotalInfo({ totalCount: result.totalCount, totalPages: result.totalPages });
      setCurrentStartPage(pageNum);
      setGoToIdInput('');

      // Get the media for the sidebar
      const media = await mediaApi.getById(id);
      setSelectedMedia(media);

      // Wait for render then scroll to the element
      setTimeout(() => {
        const element = document.getElementById(`media-card-${id}`);
        if (element) {
          element.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
      }, 100);

    } catch {
      setGoToIdError(`Media ID ${id} not found`);
    } finally {
      setIsJumping(false);
    }
  };

  const handleOpenLightbox = (media: MediaFile) => {
    if (media.mediaType === 'image') {
      setLightboxMedia(media);
    } else if (media.sourceDocumentId) {
      handleOpenDocument(media.sourceDocumentId);
    }
  };

  // Get sorted page numbers and items
  const sortedPageNumbers = useMemo(() =>
    Array.from(loadedPages.keys()).sort((a, b) => a - b),
    [loadedPages]
  );

  const minLoadedPage = sortedPageNumbers.length > 0 ? sortedPageNumbers[0] : 0;
  const maxLoadedPage = sortedPageNumbers.length > 0 ? sortedPageNumbers[sortedPageNumbers.length - 1] : 0;
  const hasPreviousPage = minLoadedPage > 0;
  const hasNextPage = maxLoadedPage < totalInfo.totalPages - 1;

  // Load previous page (above current content)
  const loadPreviousPage = useCallback(async () => {
    if (minLoadedPage <= 0 || isLoadingRef.current) return;
    await loadPage(minLoadedPage - 1);
  }, [minLoadedPage, loadPage]);

  // Load next page (below current content)
  const loadNextPage = useCallback(async () => {
    if (maxLoadedPage >= totalInfo.totalPages - 1 || isLoadingRef.current) return;
    await loadPage(maxLoadedPage + 1);
  }, [maxLoadedPage, totalInfo.totalPages, loadPage]);

  // Intersection observers for bi-directional scroll
  useEffect(() => {
    const topElement = loadMoreTopRef.current;
    const bottomElement = loadMoreBottomRef.current;
    if (!bottomElement) return;

    // Top observer: only triggers once per scroll-to-top action
    let topObserver: IntersectionObserver | null = null;
    if (topElement && minLoadedPage > 0) {
      topObserver = new IntersectionObserver(
        (entries) => {
          const isIntersecting = entries[0].isIntersecting;

          if (isIntersecting && topTriggerReady.current && !isLoadingRef.current) {
            // Trigger load and mark as not ready until user scrolls away
            topTriggerReady.current = false;
            loadPreviousPage();
          } else if (!isIntersecting) {
            // User scrolled away, re-arm the trigger
            topTriggerReady.current = true;
          }
        },
        { root: null, rootMargin: '50px', threshold: 0 }
      );
      topObserver.observe(topElement);
    }

    // Bottom observer: standard infinite scroll
    const bottomObserver = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && !isLoadingRef.current && maxLoadedPage < totalInfo.totalPages - 1) {
          loadNextPage();
        }
      },
      { root: null, rootMargin: '200px', threshold: 0 }
    );
    bottomObserver.observe(bottomElement);

    return () => {
      topObserver?.disconnect();
      bottomObserver.disconnect();
    };
  }, [minLoadedPage, maxLoadedPage, totalInfo.totalPages, loadPreviousPage, loadNextPage]);

  // Combine all loaded pages' items in order
  const allApiItems = useMemo(() => {
    const items: Array<{ media: MediaFile; globalIndex: number }> = [];
    for (const pageNum of sortedPageNumbers) {
      const page = loadedPages.get(pageNum);
      if (page) {
        page.items.forEach((item, idx) => {
          items.push({
            media: item,
            globalIndex: pageNum * PAGE_SIZE + idx + 1,
          });
        });
      }
    }
    return items;
  }, [loadedPages, sortedPageNumbers]);

  const totalCount = totalInfo.totalCount;

  const allItems = useMemo(() => {
    if (isBookmarkedTab) {
      return allApiItems.filter((item) => checkIsBookmarked(item.media.mediaFileId, 'media'));
    }
    return allApiItems;
  }, [isBookmarkedTab, allApiItems, checkIsBookmarked]);

  // Build flat list of image items for lightbox navigation
  const imageItems = useMemo(
    () => allItems.filter((item) => item.media.mediaType === 'image'),
    [allItems]
  );

  const lightboxIndex = useMemo(() => {
    if (!lightboxMedia) return -1;
    return imageItems.findIndex((item) => item.media.mediaFileId === lightboxMedia.mediaFileId);
  }, [lightboxMedia, imageItems]);

  const handleLightboxPrevious = useCallback(() => {
    if (lightboxIndex > 0) {
      setLightboxMedia(imageItems[lightboxIndex - 1].media);
    }
  }, [lightboxIndex, imageItems]);

  const handleLightboxNext = useCallback(() => {
    if (lightboxIndex < imageItems.length - 1) {
      setLightboxMedia(imageItems[lightboxIndex + 1].media);
    }
  }, [lightboxIndex, imageItems]);

  // Reset when tab or filter changes
  useEffect(() => {
    setLoadedPages(new Map());
    setCurrentStartPage(0);
    setSelectedMedia(null);
    queryClient.invalidateQueries({ queryKey: ['media-initial'] });
  }, [activeTab, excludeDocumentScans, queryClient]);

  function handleTabChange(tab: MediaTab) {
    setActiveTab(tab);
  }

  return (
    <div className="flex flex-col">
      {/* Sticky Header and Filter Bar */}
      <div className="sticky top-[-1rem] z-20 bg-[#12121A] pb-4 pt-6 -mx-4 -mt-4 px-4 border-b border-border-subtle shadow-lg">
        {/* Header with Total Count */}
        <div className="flex items-center justify-between mb-4">
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

        {/* Document Scans Toggle */}
        <button
          type="button"
          onClick={() => setExcludeDocumentScans(!excludeDocumentScans)}
          className={cn(
            'flex items-center gap-2 rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors',
            excludeDocumentScans
              ? 'border-accent-amber/30 bg-accent-amber/10 text-accent-amber'
              : 'border-border-subtle bg-surface-raised text-text-secondary hover:bg-surface-overlay'
          )}
        >
          <FileText className="h-3.5 w-3.5" />
          {excludeDocumentScans ? 'Photos Only' : 'All Images'}
        </button>

        {/* Go to ID */}
        <div className="flex items-center gap-2">
          <div className="flex items-center rounded-lg border border-border-subtle bg-surface-raised">
            <div className="flex items-center gap-1.5 px-2 text-text-tertiary">
              <Search className="h-3.5 w-3.5" />
              <span className="text-xs">ID:</span>
            </div>
            <input
              type="text"
              value={goToIdInput}
              onChange={(e) => {
                setGoToIdInput(e.target.value);
                setGoToIdError(null);
              }}
              onKeyDown={(e) => e.key === 'Enter' && handleGoToId()}
              placeholder="Enter media ID"
              className="w-28 bg-transparent px-2 py-1.5 text-xs text-text-primary placeholder:text-text-disabled focus:outline-none"
            />
            <button
              type="button"
              onClick={handleGoToId}
              className="flex items-center justify-center h-full px-2 text-text-tertiary hover:text-accent-blue transition-colors border-l border-border-subtle"
              title="Go to media ID"
            >
              <ArrowRight className="h-3.5 w-3.5" />
            </button>
          </div>
          {goToIdError && (
            <span className="text-xs text-accent-red">{goToIdError}</span>
          )}
          {isJumping && (
            <div className="flex items-center gap-2 rounded-lg border border-accent-blue/30 bg-accent-blue/10 px-3 py-1.5">
              <Loader2 className="h-4 w-4 animate-spin text-accent-blue" />
              <span className="text-xs text-accent-blue font-medium">
                Jumping to ID...
              </span>
            </div>
          )}
          {/* Page range indicator */}
          {sortedPageNumbers.length > 0 && (
            <div className="flex items-center gap-1.5 text-xs text-text-tertiary">
              <span>Pages {minLoadedPage + 1}-{maxLoadedPage + 1} of {totalInfo.totalPages}</span>
            </div>
          )}
        </div>
      </div>
      </div>

      {/* Content Area */}
      <div className="flex gap-4 mt-4">
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
              {/* Load Previous Trigger (Top) */}
              <div ref={loadMoreTopRef} className="flex justify-center py-4">
                {hasPreviousPage && (
                  <button
                    onClick={loadPreviousPage}
                    disabled={isLoadingPage}
                    className="flex items-center gap-2 rounded-md border border-border-subtle bg-surface-raised px-4 py-2 text-sm text-text-secondary hover:bg-surface-overlay disabled:opacity-50"
                  >
                    {isLoadingPage ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <ChevronUp className="h-4 w-4" />
                    )}
                    Load Previous (Page {minLoadedPage})
                  </button>
                )}
              </div>

              <div className="grid grid-cols-3 gap-2 sm:grid-cols-4 lg:grid-cols-6 xl:grid-cols-8">
                {allItems.map((item) => (
                  <MediaCard
                    key={item.media.mediaFileId}
                    media={item.media}
                    index={item.globalIndex}
                    isSelected={selectedMedia?.mediaFileId === item.media.mediaFileId}
                    isBookmarked={isBookmarked(item.media.mediaFileId)}
                    onSelect={() => setSelectedMedia(item.media)}
                    onDoubleClick={() => handleOpenLightbox(item.media)}
                    onToggleBookmark={() => toggleBookmark(item.media)}
                  />
                ))}
              </div>

              {/* Load Next Trigger (Bottom) */}
              <div ref={loadMoreBottomRef} className="flex justify-center py-8">
                {isBookmarkedTab ? (
                  <p className="text-xs text-text-disabled">
                    {allItems.length > 0
                      ? `Showing ${allItems.length} of ${bookmarkCount} bookmarked items`
                      : 'No bookmarked items'}
                  </p>
                ) : isLoadingPage ? (
                  <div className="flex items-center gap-2 text-sm text-text-secondary">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Loading more...
                  </div>
                ) : hasNextPage ? (
                  <button
                    onClick={loadNextPage}
                    className="flex items-center gap-2 rounded-md border border-border-subtle bg-surface-raised px-4 py-2 text-sm text-text-secondary hover:bg-surface-overlay"
                  >
                    <ChevronDown className="h-4 w-4" />
                    Load More (Page {maxLoadedPage + 2})
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
            onOpenFullscreen={() => handleOpenLightbox(selectedMedia)}
          />
        )}
      </div>

      {/* Image Lightbox */}
      {lightboxMedia && (
        <ImageLightbox
          media={lightboxMedia}
          onClose={() => setLightboxMedia(null)}
          onPrevious={lightboxIndex > 0 ? handleLightboxPrevious : undefined}
          onNext={lightboxIndex < imageItems.length - 1 ? handleLightboxNext : undefined}
        />
      )}
    </div>
  );
}

function MediaCard({
  media,
  index,
  isSelected,
  isBookmarked,
  onSelect,
  onDoubleClick,
  onToggleBookmark,
}: {
  media: MediaFile;
  index: number;
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
      id={`media-card-${media.mediaFileId}`}
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
      {/* Index Badge */}
      <div className="absolute top-1 left-1 z-10 flex items-center gap-1 rounded-md bg-black/60 px-1.5 py-0.5 text-[10px] font-medium text-white">
        <span className="text-text-disabled">#{index}</span>
        <span className="text-accent-blue">ID:{media.mediaFileId}</span>
      </div>

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
  onOpenFullscreen,
}: {
  media: MediaFile;
  isBookmarked: boolean;
  onClose: () => void;
  onToggleBookmark: () => void;
  onOpenFullscreen: () => void;
}) {
  const Icon = getMediaIcon(media.mediaType);
  const [imgError, setImgError] = useState(false);

  const imageUrl = `/api/media/${media.mediaFileId}/file`;

  return (
    <div className="w-[35%] shrink-0 overflow-y-auto rounded-lg border border-border-subtle bg-surface-raised max-h-[calc(100vh-220px)] sticky top-32">
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
      <div className="flex aspect-video items-center justify-center bg-surface-sunken overflow-hidden relative group/preview">
        {media.mediaType === 'image' && !imgError ? (
          <>
            <img
              src={imageUrl}
              alt={media.fileName}
              className="h-full w-full object-contain cursor-pointer"
              onError={() => setImgError(true)}
              onClick={onOpenFullscreen}
            />
            <button
              type="button"
              onClick={onOpenFullscreen}
              className="absolute bottom-2 right-2 flex items-center gap-1.5 rounded-md bg-black/60 backdrop-blur-sm px-2.5 py-1.5 text-xs font-medium text-white opacity-0 group-hover/preview:opacity-100 transition-opacity hover:bg-black/80"
              title="View fullscreen"
            >
              <Maximize2 className="h-3.5 w-3.5" />
              Fullscreen
            </button>
          </>
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
        <div className="flex items-center justify-between mb-1">
          <span className="text-xs font-mono text-accent-blue">ID: {media.mediaFileId}</span>
        </div>
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
  onPrevious,
  onNext,
}: {
  media: MediaFile;
  onClose: () => void;
  onPrevious?: () => void;
  onNext?: () => void;
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
  const handleReset = useCallback(() => {
    setScale(1);
    setRotation(0);
    setPosition({ x: 0, y: 0 });
  }, []);

  // Reset view when media changes
  useEffect(() => {
    handleReset();
  }, [media.mediaFileId, handleReset]);

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
        case 'ArrowLeft':
          e.preventDefault();
          onPrevious?.();
          break;
        case 'ArrowRight':
          e.preventDefault();
          onNext?.();
          break;
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose, onPrevious, onNext, handleReset]);

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

      {/* Previous Button */}
      {onPrevious && (
        <button
          type="button"
          onClick={(e) => { e.stopPropagation(); onPrevious(); }}
          className="absolute left-4 top-1/2 -translate-y-1/2 z-10 flex h-12 w-12 items-center justify-center rounded-full bg-surface-raised/80 backdrop-blur-sm border border-border-subtle text-text-secondary hover:bg-surface-overlay hover:text-text-primary transition-colors"
          title="Previous image (Left arrow)"
        >
          <ChevronLeft className="h-6 w-6" />
        </button>
      )}

      {/* Next Button */}
      {onNext && (
        <button
          type="button"
          onClick={(e) => { e.stopPropagation(); onNext(); }}
          className="absolute right-4 top-1/2 -translate-y-1/2 z-10 flex h-12 w-12 items-center justify-center rounded-full bg-surface-raised/80 backdrop-blur-sm border border-border-subtle text-text-secondary hover:bg-surface-overlay hover:text-text-primary transition-colors"
          title="Next image (Right arrow)"
        >
          <ChevronRight className="h-6 w-6" />
        </button>
      )}

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
        <div className="flex items-center justify-center gap-3 mt-1">
          <span className="text-xs font-mono text-accent-blue">ID: {media.mediaFileId}</span>
          {media.widthPixels && media.heightPixels && (
            <span className="text-xs text-text-tertiary">
              {media.widthPixels} x {media.heightPixels} px
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
