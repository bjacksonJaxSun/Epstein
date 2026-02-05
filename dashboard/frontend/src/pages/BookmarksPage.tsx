import { useState, useMemo, useCallback } from 'react';
import { useNavigate } from 'react-router';
import {
  Bookmark,
  Search,
  User,
  Building2,
  MapPin,
  Calendar,
  FileText,
  X,
  Plus,
  Tag,
  Trash2,
  SortAsc,
  SortDesc,
} from 'lucide-react';
import { useBookmarkStore } from '@/stores/useBookmarkStore';
import type { Bookmark as BookmarkType } from '@/stores/useBookmarkStore';
import { cn } from '@/lib/utils';

const entityIcons: Record<string, typeof User> = {
  person: User,
  organization: Building2,
  location: MapPin,
  event: Calendar,
  document: FileText,
};

const entityColors: Record<string, string> = {
  person: 'text-entity-person bg-entity-person/15',
  organization: 'text-entity-organization bg-entity-organization/15',
  location: 'text-entity-location bg-entity-location/15',
  event: 'text-entity-event bg-entity-event/15',
  document: 'text-entity-document bg-entity-document/15',
};

const entityBandColors: Record<string, string> = {
  person: 'bg-entity-person',
  organization: 'bg-entity-organization',
  location: 'bg-entity-location',
  event: 'bg-entity-event',
  document: 'bg-entity-document',
};

type SortMode = 'date-desc' | 'date-asc' | 'name-asc' | 'name-desc';
type EntityTypeFilter = 'all' | 'person' | 'organization' | 'document' | 'event' | 'location';

const typeFilters: { key: EntityTypeFilter; label: string }[] = [
  { key: 'all', label: 'All' },
  { key: 'person', label: 'People' },
  { key: 'organization', label: 'Orgs' },
  { key: 'document', label: 'Docs' },
  { key: 'event', label: 'Events' },
  { key: 'location', label: 'Locations' },
];

function BookmarkCard({
  bookmark,
  onNavigate,
  onUpdateNotes,
  onRemove,
  onAddTag,
  onRemoveTag,
}: {
  bookmark: BookmarkType;
  onNavigate: (bookmark: BookmarkType) => void;
  onUpdateNotes: (id: string, notes: string) => void;
  onRemove: (id: string) => void;
  onAddTag: (id: string, tag: string) => void;
  onRemoveTag: (id: string, tag: string) => void;
}) {
  const [editingNotes, setEditingNotes] = useState(false);
  const [notesValue, setNotesValue] = useState(bookmark.notes ?? '');
  const [tagInput, setTagInput] = useState('');
  const [showTagInput, setShowTagInput] = useState(false);

  const Icon = entityIcons[bookmark.entityType] ?? FileText;
  const bandColor = entityBandColors[bookmark.entityType] ?? entityBandColors.document;

  return (
    <div className="rounded-lg border border-border-subtle bg-surface-raised transition-colors hover:border-border-default">
      {/* Color band */}
      <div className={cn('h-1 rounded-t-lg', bandColor)} />

      <div className="p-3">
        {/* Header */}
        <div className="mb-2 flex items-start justify-between">
          <button
            type="button"
            onClick={() => onNavigate(bookmark)}
            className="flex items-center gap-2 text-left"
          >
            <div
              className={cn(
                'flex h-7 w-7 shrink-0 items-center justify-center rounded',
                entityColors[bookmark.entityType] ?? entityColors.document
              )}
            >
              <Icon className="h-3.5 w-3.5" />
            </div>
            <div className="min-w-0">
              <p className="truncate text-sm font-medium text-text-primary hover:text-accent-blue">
                {bookmark.label}
              </p>
              <p className="text-xs text-text-tertiary">
                {bookmark.entityType.charAt(0).toUpperCase() + bookmark.entityType.slice(1)} #{bookmark.entityId}
              </p>
            </div>
          </button>
          <button
            type="button"
            onClick={() => onRemove(bookmark.id)}
            className="flex h-6 w-6 shrink-0 items-center justify-center rounded text-text-disabled hover:text-accent-red"
            aria-label="Remove bookmark"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </button>
        </div>

        {/* Notes */}
        <div className="mb-2">
          {editingNotes ? (
            <div className="flex flex-col gap-1">
              <textarea
                value={notesValue}
                onChange={(e) => setNotesValue(e.target.value)}
                className="w-full rounded border border-border-subtle bg-surface-base px-2 py-1.5 text-xs text-text-primary placeholder:text-text-disabled focus:border-accent-blue focus:outline-none"
                rows={2}
                placeholder="Add notes..."
                autoFocus
              />
              <div className="flex gap-1 justify-end">
                <button
                  type="button"
                  onClick={() => {
                    setEditingNotes(false);
                    setNotesValue(bookmark.notes ?? '');
                  }}
                  className="rounded px-2 py-0.5 text-[11px] text-text-tertiary hover:text-text-primary"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={() => {
                    onUpdateNotes(bookmark.id, notesValue);
                    setEditingNotes(false);
                  }}
                  className="rounded bg-accent-blue px-2 py-0.5 text-[11px] font-medium text-white"
                >
                  Save
                </button>
              </div>
            </div>
          ) : (
            <button
              type="button"
              onClick={() => setEditingNotes(true)}
              className="w-full text-left"
            >
              {bookmark.notes ? (
                <p className="text-xs text-text-secondary line-clamp-2">
                  {bookmark.notes}
                </p>
              ) : (
                <p className="text-xs text-text-disabled italic">
                  Click to add notes...
                </p>
              )}
            </button>
          )}
        </div>

        {/* Tags */}
        <div className="flex flex-wrap items-center gap-1">
          {bookmark.tags.map((tag) => (
            <span
              key={tag}
              className="inline-flex items-center gap-0.5 rounded-sm bg-surface-overlay px-1.5 py-0.5 text-[11px] text-text-secondary"
            >
              {tag}
              <button
                type="button"
                onClick={() => onRemoveTag(bookmark.id, tag)}
                className="ml-0.5 text-text-disabled hover:text-text-primary"
                aria-label={`Remove tag ${tag}`}
              >
                <X className="h-2.5 w-2.5" />
              </button>
            </span>
          ))}
          {showTagInput ? (
            <input
              type="text"
              value={tagInput}
              onChange={(e) => setTagInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && tagInput.trim()) {
                  onAddTag(bookmark.id, tagInput.trim());
                  setTagInput('');
                  setShowTagInput(false);
                }
                if (e.key === 'Escape') {
                  setTagInput('');
                  setShowTagInput(false);
                }
              }}
              onBlur={() => {
                if (tagInput.trim()) {
                  onAddTag(bookmark.id, tagInput.trim());
                }
                setTagInput('');
                setShowTagInput(false);
              }}
              placeholder="tag..."
              autoFocus
              className="w-16 rounded-sm border border-border-subtle bg-surface-base px-1 py-0.5 text-[11px] text-text-primary placeholder:text-text-disabled focus:border-accent-blue focus:outline-none"
            />
          ) : (
            <button
              type="button"
              onClick={() => setShowTagInput(true)}
              className="inline-flex items-center gap-0.5 rounded-sm px-1 py-0.5 text-[11px] text-text-disabled hover:text-text-secondary"
              aria-label="Add tag"
            >
              <Plus className="h-2.5 w-2.5" />
              <Tag className="h-2.5 w-2.5" />
            </button>
          )}
        </div>

        {/* Date */}
        <p className="mt-2 text-[11px] text-text-disabled">
          Added {new Date(bookmark.createdAt).toLocaleDateString()}
        </p>
      </div>
    </div>
  );
}

export function BookmarksPage() {
  const navigate = useNavigate();
  const {
    bookmarks,
    removeBookmark,
    updateBookmarkNotes,
    addTag,
    removeTag,
  } = useBookmarkStore();

  const [typeFilter, setTypeFilter] = useState<EntityTypeFilter>('all');
  const [sortMode, setSortMode] = useState<SortMode>('date-desc');
  const [searchText, setSearchText] = useState('');

  const filtered = useMemo(() => {
    let result = [...bookmarks];

    // Type filter
    if (typeFilter !== 'all') {
      result = result.filter((b) => b.entityType === typeFilter);
    }

    // Search filter
    if (searchText.trim()) {
      const q = searchText.toLowerCase();
      result = result.filter(
        (b) =>
          b.label.toLowerCase().includes(q) ||
          (b.notes && b.notes.toLowerCase().includes(q)) ||
          b.tags.some((t) => t.toLowerCase().includes(q))
      );
    }

    // Sort
    result.sort((a, b) => {
      switch (sortMode) {
        case 'date-desc':
          return new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime();
        case 'date-asc':
          return new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime();
        case 'name-asc':
          return a.label.localeCompare(b.label);
        case 'name-desc':
          return b.label.localeCompare(a.label);
        default:
          return 0;
      }
    });

    return result;
  }, [bookmarks, typeFilter, sortMode, searchText]);

  const handleNavigate = useCallback(
    (bookmark: BookmarkType) => {
      if (bookmark.entityType === 'person') {
        navigate(`/people/${bookmark.entityId}`);
      } else if (bookmark.entityType === 'document') {
        navigate('/documents');
      } else if (bookmark.entityType === 'organization') {
        navigate('/organizations');
      } else if (bookmark.entityType === 'event') {
        navigate('/timeline');
      } else if (bookmark.entityType === 'location') {
        navigate('/locations');
      }
    },
    [navigate]
  );

  const toggleSort = useCallback(() => {
    setSortMode((prev) => {
      switch (prev) {
        case 'date-desc':
          return 'date-asc';
        case 'date-asc':
          return 'name-asc';
        case 'name-asc':
          return 'name-desc';
        case 'name-desc':
          return 'date-desc';
        default:
          return 'date-desc';
      }
    });
  }, []);

  const sortLabel = useMemo(() => {
    switch (sortMode) {
      case 'date-desc':
        return 'Newest first';
      case 'date-asc':
        return 'Oldest first';
      case 'name-asc':
        return 'Name A-Z';
      case 'name-desc':
        return 'Name Z-A';
      default:
        return 'Sort';
    }
  }, [sortMode]);

  return (
    <div className="flex flex-col gap-6">
      {/* Page Header */}
      <div>
        <h2 className="text-xl font-semibold text-text-primary">Bookmarks</h2>
        <p className="mt-1 text-sm text-text-secondary">
          Saved entities, documents, and search queries for quick access.
        </p>
      </div>

      {/* Empty state */}
      {bookmarks.length === 0 && (
        <div className="flex flex-col items-center justify-center gap-4 rounded-lg border border-border-subtle bg-surface-raised py-24">
          <Bookmark className="h-12 w-12 text-text-disabled" />
          <p className="text-sm text-text-disabled">
            No bookmarks yet. Pin items from any page using the bookmark icon.
          </p>
        </div>
      )}

      {bookmarks.length > 0 && (
        <>
          {/* Filter/Sort Bar */}
          <div className="flex flex-wrap items-center gap-3">
            {/* Type Filter Tabs */}
            <div className="flex items-center gap-1 rounded-md border border-border-subtle bg-surface-raised p-0.5">
              {typeFilters.map((tf) => (
                <button
                  key={tf.key}
                  type="button"
                  onClick={() => setTypeFilter(tf.key)}
                  className={cn(
                    'rounded-md px-2.5 py-1 text-xs font-medium transition-colors',
                    typeFilter === tf.key
                      ? 'bg-surface-overlay text-text-primary'
                      : 'text-text-tertiary hover:text-text-secondary'
                  )}
                >
                  {tf.label}
                </button>
              ))}
            </div>

            {/* Search */}
            <div className="flex items-center gap-2 rounded-md border border-border-subtle bg-surface-base px-2.5 py-1">
              <Search className="h-3.5 w-3.5 text-text-tertiary" />
              <input
                type="text"
                value={searchText}
                onChange={(e) => setSearchText(e.target.value)}
                placeholder="Search bookmarks..."
                className="w-40 bg-transparent text-xs text-text-primary placeholder:text-text-disabled focus:outline-none"
              />
              {searchText && (
                <button
                  type="button"
                  onClick={() => setSearchText('')}
                  className="text-text-disabled hover:text-text-primary"
                  aria-label="Clear search"
                >
                  <X className="h-3 w-3" />
                </button>
              )}
            </div>

            {/* Sort */}
            <button
              type="button"
              onClick={toggleSort}
              className="flex items-center gap-1.5 rounded-md border border-border-subtle bg-surface-raised px-2.5 py-1 text-xs text-text-secondary hover:text-text-primary"
            >
              {sortMode.includes('desc') ? (
                <SortDesc className="h-3.5 w-3.5" />
              ) : (
                <SortAsc className="h-3.5 w-3.5" />
              )}
              {sortLabel}
            </button>

            {/* Count */}
            <span className="ml-auto text-xs text-text-tertiary">
              {filtered.length} bookmark{filtered.length !== 1 ? 's' : ''}
            </span>
          </div>

          {/* Bookmark Grid */}
          {filtered.length === 0 ? (
            <div className="flex flex-col items-center justify-center gap-3 rounded-lg border border-border-subtle bg-surface-raised py-16">
              <Search className="h-8 w-8 text-text-disabled" />
              <p className="text-sm text-text-disabled">
                No bookmarks match your filters.
              </p>
            </div>
          ) : (
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              {filtered.map((bookmark) => (
                <BookmarkCard
                  key={bookmark.id}
                  bookmark={bookmark}
                  onNavigate={handleNavigate}
                  onUpdateNotes={updateBookmarkNotes}
                  onRemove={removeBookmark}
                  onAddTag={addTag}
                  onRemoveTag={removeTag}
                />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
