import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface FilterState {
  dateFrom?: string;
  dateTo?: string;
  personIds: number[];
  eventTypes: string[];
  confidenceLevels: string[];
  searchQuery: string;

  setDateRange: (from?: string, to?: string) => void;
  togglePersonId: (id: number) => void;
  setEventTypes: (types: string[]) => void;
  setConfidenceLevels: (levels: string[]) => void;
  setSearchQuery: (query: string) => void;
  clearFilters: () => void;
}

export const useFilterStore = create<FilterState>()(
  persist(
    (set) => ({
      personIds: [],
      eventTypes: [],
      confidenceLevels: [],
      searchQuery: '',

      setDateRange: (from, to) => set({ dateFrom: from, dateTo: to }),
      togglePersonId: (id) =>
        set((state) => ({
          personIds: state.personIds.includes(id)
            ? state.personIds.filter((p) => p !== id)
            : [...state.personIds, id],
        })),
      setEventTypes: (types) => set({ eventTypes: types }),
      setConfidenceLevels: (levels) => set({ confidenceLevels: levels }),
      setSearchQuery: (query) => set({ searchQuery: query }),
      clearFilters: () =>
        set({
          dateFrom: undefined,
          dateTo: undefined,
          personIds: [],
          eventTypes: [],
          confidenceLevels: [],
          searchQuery: '',
        }),
    }),
    { name: 'dashboard-filters' }
  )
);
