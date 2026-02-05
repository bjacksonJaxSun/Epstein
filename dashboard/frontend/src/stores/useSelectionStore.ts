import { create } from 'zustand';

interface SelectionState {
  selectedEntityId: string | null;
  selectedEntityType: string | null;
  contextPanelOpen: boolean;

  selectEntity: (id: string, type: string) => void;
  clearSelection: () => void;
  toggleContextPanel: () => void;
}

export const useSelectionStore = create<SelectionState>()((set) => ({
  selectedEntityId: null,
  selectedEntityType: null,
  contextPanelOpen: false,

  selectEntity: (id, type) =>
    set({
      selectedEntityId: id,
      selectedEntityType: type,
      contextPanelOpen: true,
    }),
  clearSelection: () =>
    set({
      selectedEntityId: null,
      selectedEntityType: null,
      contextPanelOpen: false,
    }),
  toggleContextPanel: () =>
    set((state) => ({ contextPanelOpen: !state.contextPanelOpen })),
}));
