import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface BoardCard {
  id: string;
  entityId: number;
  entityType: string;
  label: string;
  x: number;
  y: number;
  notes?: string;
}

interface Board {
  id: string;
  name: string;
  cards: BoardCard[];
  createdAt: string;
}

interface BoardState {
  boards: Board[];
  activeBoardId: string | null;

  createBoard: (name: string) => void;
  deleteBoard: (id: string) => void;
  setActiveBoard: (id: string) => void;
  addCard: (boardId: string, card: Omit<BoardCard, 'id'>) => void;
  removeCard: (boardId: string, cardId: string) => void;
  updateCardPosition: (
    boardId: string,
    cardId: string,
    x: number,
    y: number
  ) => void;
  updateCardNotes: (
    boardId: string,
    cardId: string,
    notes: string
  ) => void;
}

export const useBoardStore = create<BoardState>()(
  persist(
    (set) => ({
      boards: [],
      activeBoardId: null,

      createBoard: (name) => {
        const id = crypto.randomUUID();
        set((state) => ({
          boards: [
            ...state.boards,
            { id, name, cards: [], createdAt: new Date().toISOString() },
          ],
          activeBoardId: id,
        }));
      },
      deleteBoard: (id) =>
        set((state) => ({
          boards: state.boards.filter((b) => b.id !== id),
          activeBoardId:
            state.activeBoardId === id ? null : state.activeBoardId,
        })),
      setActiveBoard: (id) => set({ activeBoardId: id }),
      addCard: (boardId, card) =>
        set((state) => ({
          boards: state.boards.map((b) =>
            b.id === boardId
              ? {
                  ...b,
                  cards: [
                    ...b.cards,
                    { ...card, id: crypto.randomUUID() },
                  ],
                }
              : b
          ),
        })),
      removeCard: (boardId, cardId) =>
        set((state) => ({
          boards: state.boards.map((b) =>
            b.id === boardId
              ? { ...b, cards: b.cards.filter((c) => c.id !== cardId) }
              : b
          ),
        })),
      updateCardPosition: (boardId, cardId, x, y) =>
        set((state) => ({
          boards: state.boards.map((b) =>
            b.id === boardId
              ? {
                  ...b,
                  cards: b.cards.map((c) =>
                    c.id === cardId ? { ...c, x, y } : c
                  ),
                }
              : b
          ),
        })),
      updateCardNotes: (boardId, cardId, notes) =>
        set((state) => ({
          boards: state.boards.map((b) =>
            b.id === boardId
              ? {
                  ...b,
                  cards: b.cards.map((c) =>
                    c.id === cardId ? { ...c, notes } : c
                  ),
                }
              : b
          ),
        })),
    }),
    { name: 'investigation-boards' }
  )
);
