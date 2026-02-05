import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export interface Bookmark {
  id: string;
  entityId: number;
  entityType: string;
  label: string;
  notes?: string;
  tags: string[];
  createdAt: string;
}

interface BookmarkState {
  bookmarks: Bookmark[];
  addBookmark: (bookmark: Omit<Bookmark, 'id' | 'createdAt'>) => void;
  removeBookmark: (id: string) => void;
  updateBookmarkNotes: (id: string, notes: string) => void;
  addTag: (id: string, tag: string) => void;
  removeTag: (id: string, tag: string) => void;
  isBookmarked: (entityId: number, entityType: string) => boolean;
  getBookmark: (entityId: number, entityType: string) => Bookmark | undefined;
}

export const useBookmarkStore = create<BookmarkState>()(
  persist(
    (set, get) => ({
      bookmarks: [],

      addBookmark: (bookmark) => {
        const id = crypto.randomUUID();
        set((state) => ({
          bookmarks: [
            ...state.bookmarks,
            { ...bookmark, id, createdAt: new Date().toISOString() },
          ],
        }));
      },

      removeBookmark: (id) =>
        set((state) => ({
          bookmarks: state.bookmarks.filter((b) => b.id !== id),
        })),

      updateBookmarkNotes: (id, notes) =>
        set((state) => ({
          bookmarks: state.bookmarks.map((b) =>
            b.id === id ? { ...b, notes } : b
          ),
        })),

      addTag: (id, tag) =>
        set((state) => ({
          bookmarks: state.bookmarks.map((b) =>
            b.id === id && !b.tags.includes(tag)
              ? { ...b, tags: [...b.tags, tag] }
              : b
          ),
        })),

      removeTag: (id, tag) =>
        set((state) => ({
          bookmarks: state.bookmarks.map((b) =>
            b.id === id ? { ...b, tags: b.tags.filter((t) => t !== tag) } : b
          ),
        })),

      isBookmarked: (entityId, entityType) =>
        get().bookmarks.some(
          (b) => b.entityId === entityId && b.entityType === entityType
        ),

      getBookmark: (entityId, entityType) =>
        get().bookmarks.find(
          (b) => b.entityId === entityId && b.entityType === entityType
        ),
    }),
    { name: 'investigation-bookmarks' }
  )
);
