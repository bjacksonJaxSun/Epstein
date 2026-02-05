import { useState, useCallback, useRef, useEffect } from 'react';
import {
  Layout,
  Plus,
  Trash2,
  MoreVertical,
  StickyNote,
  X,
  User,
  Building2,
  MapPin,
  Calendar,
  FileText,
} from 'lucide-react';
import { DndContext, useDraggable } from '@dnd-kit/core';
import type { DragEndEvent } from '@dnd-kit/core';
import { useBoardStore } from '@/stores/useBoardStore';
import { cn } from '@/lib/utils';

const entityIcons: Record<string, typeof User> = {
  person: User,
  organization: Building2,
  location: MapPin,
  event: Calendar,
  document: FileText,
};

const entityBandColors: Record<string, string> = {
  person: 'bg-entity-person',
  organization: 'bg-entity-organization',
  location: 'bg-entity-location',
  event: 'bg-entity-event',
  document: 'bg-entity-document',
};

interface BoardCardData {
  id: string;
  entityId: number;
  entityType: string;
  label: string;
  x: number;
  y: number;
  notes?: string;
}

function DraggableBoardCard({
  card,
  boardId,
  onEditNotes,
  onRemove,
}: {
  card: BoardCardData;
  boardId: string;
  onEditNotes: (cardId: string) => void;
  onRemove: (cardId: string) => void;
}) {
  const { attributes, listeners, setNodeRef, transform } = useDraggable({
    id: card.id,
  });
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  const style = {
    transform: transform
      ? `translate(${card.x + transform.x}px, ${card.y + transform.y}px)`
      : `translate(${card.x}px, ${card.y}px)`,
    position: 'absolute' as const,
  };

  const Icon = entityIcons[card.entityType] ?? FileText;
  const bandColor = entityBandColors[card.entityType] ?? entityBandColors.document;

  // Close menu on outside click
  useEffect(() => {
    if (!menuOpen) return;
    function handleClick(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [menuOpen]);

  // Suppress unused variable warning by referencing boardId in a no-op way
  void boardId;

  return (
    <div
      ref={setNodeRef}
      style={style}
      className="w-64 rounded-lg border border-border-subtle bg-surface-raised shadow-lg"
    >
      {/* Color band */}
      <div className={cn('h-1.5 rounded-t-lg', bandColor)} />

      {/* Header with drag handle */}
      <div
        {...listeners}
        {...attributes}
        className="flex cursor-grab items-center gap-2 border-b border-border-subtle px-3 py-2 active:cursor-grabbing"
      >
        <div
          className={cn(
            'flex h-6 w-6 shrink-0 items-center justify-center rounded',
            `text-entity-${card.entityType} bg-entity-${card.entityType}/15`
          )}
        >
          <Icon className="h-3.5 w-3.5" />
        </div>
        <span className="flex-1 truncate text-sm font-medium text-text-primary">
          {card.label}
        </span>
        <div className="relative" ref={menuRef}>
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              setMenuOpen(!menuOpen);
            }}
            onPointerDown={(e) => e.stopPropagation()}
            className="flex h-6 w-6 items-center justify-center rounded text-text-tertiary hover:bg-surface-overlay hover:text-text-primary"
            aria-label="Card menu"
          >
            <MoreVertical className="h-3.5 w-3.5" />
          </button>
          {menuOpen && (
            <div className="absolute right-0 top-full z-10 mt-1 w-40 rounded-md border border-border-subtle bg-surface-raised py-1 shadow-lg">
              <button
                type="button"
                onClick={() => {
                  setMenuOpen(false);
                  onEditNotes(card.id);
                }}
                className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-sm text-text-secondary hover:bg-surface-overlay hover:text-text-primary"
              >
                <StickyNote className="h-3.5 w-3.5" />
                Edit notes
              </button>
              <button
                type="button"
                onClick={() => {
                  setMenuOpen(false);
                  onRemove(card.id);
                }}
                className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-sm text-accent-red hover:bg-surface-overlay"
              >
                <Trash2 className="h-3.5 w-3.5" />
                Remove
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Card body */}
      <div className="px-3 py-2">
        <p className="text-xs text-text-tertiary">
          {card.entityType.charAt(0).toUpperCase() + card.entityType.slice(1)} #{card.entityId}
        </p>
        {card.notes && (
          <p className="mt-1 text-xs text-text-secondary line-clamp-3">
            {card.notes}
          </p>
        )}
      </div>
    </div>
  );
}

function NotesEditor({
  cardId,
  initialNotes,
  onSave,
  onClose,
}: {
  cardId: string;
  initialNotes: string;
  onSave: (cardId: string, notes: string) => void;
  onClose: () => void;
}) {
  const [notes, setNotes] = useState(initialNotes);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-full max-w-md rounded-lg border border-border-subtle bg-surface-raised p-4 shadow-xl">
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-text-primary">Edit Notes</h3>
          <button
            type="button"
            onClick={onClose}
            className="flex h-6 w-6 items-center justify-center rounded text-text-tertiary hover:text-text-primary"
            aria-label="Close"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          className="w-full rounded-md border border-border-subtle bg-surface-base px-3 py-2 text-sm text-text-primary placeholder:text-text-disabled focus:border-accent-blue focus:outline-none"
          rows={4}
          placeholder="Add notes about this entity..."
        />
        <div className="mt-3 flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded-md px-3 py-1.5 text-sm text-text-secondary hover:bg-surface-overlay"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={() => {
              onSave(cardId, notes);
              onClose();
            }}
            className="rounded-md bg-accent-blue px-3 py-1.5 text-sm font-medium text-white hover:bg-accent-blue/80"
          >
            Save
          </button>
        </div>
      </div>
    </div>
  );
}

export function BoardsPage() {
  const {
    boards,
    activeBoardId,
    createBoard,
    deleteBoard,
    setActiveBoard,
    removeCard,
    updateCardPosition,
    updateCardNotes,
  } = useBoardStore();

  const [newBoardName, setNewBoardName] = useState('');
  const [showNewBoard, setShowNewBoard] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);
  const [editingNotes, setEditingNotes] = useState<string | null>(null);

  const activeBoard = boards.find((b) => b.id === activeBoardId) ?? null;

  const handleCreateBoard = useCallback(() => {
    const name = newBoardName.trim();
    if (!name) return;
    createBoard(name);
    setNewBoardName('');
    setShowNewBoard(false);
  }, [newBoardName, createBoard]);

  const handleDeleteBoard = useCallback(
    (id: string) => {
      deleteBoard(id);
      setConfirmDelete(null);
    },
    [deleteBoard]
  );

  const handleDragEnd = useCallback(
    (event: DragEndEvent) => {
      const { active, delta } = event;
      if (!activeBoard) return;
      const card = activeBoard.cards.find((c) => c.id === active.id);
      if (card) {
        updateCardPosition(
          activeBoard.id,
          card.id,
          card.x + delta.x,
          card.y + delta.y
        );
      }
    },
    [activeBoard, updateCardPosition]
  );

  const handleRemoveCard = useCallback(
    (cardId: string) => {
      if (activeBoard) {
        removeCard(activeBoard.id, cardId);
      }
    },
    [activeBoard, removeCard]
  );

  const handleSaveNotes = useCallback(
    (cardId: string, notes: string) => {
      if (activeBoard) {
        updateCardNotes(activeBoard.id, cardId, notes);
      }
    },
    [activeBoard, updateCardNotes]
  );

  const editingCard = activeBoard?.cards.find((c) => c.id === editingNotes);

  return (
    <div className="flex h-full gap-0">
      {/* Board List Sidebar */}
      <aside className="flex w-[250px] shrink-0 flex-col border-r border-border-subtle bg-surface-raised">
        <div className="flex items-center justify-between border-b border-border-subtle px-4 py-3">
          <h2 className="text-sm font-semibold text-text-primary">Boards</h2>
          <button
            type="button"
            onClick={() => setShowNewBoard(true)}
            className="flex h-7 w-7 items-center justify-center rounded-md text-text-secondary transition-colors hover:bg-surface-overlay hover:text-text-primary"
            aria-label="New board"
          >
            <Plus className="h-4 w-4" />
          </button>
        </div>

        {/* New board input */}
        {showNewBoard && (
          <div className="border-b border-border-subtle p-3">
            <input
              type="text"
              value={newBoardName}
              onChange={(e) => setNewBoardName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleCreateBoard();
                if (e.key === 'Escape') setShowNewBoard(false);
              }}
              placeholder="Board name..."
              autoFocus
              className="w-full rounded-md border border-border-subtle bg-surface-base px-2.5 py-1.5 text-sm text-text-primary placeholder:text-text-disabled focus:border-accent-blue focus:outline-none"
            />
            <div className="mt-2 flex gap-2">
              <button
                type="button"
                onClick={handleCreateBoard}
                className="flex-1 rounded-md bg-accent-blue px-2 py-1 text-xs font-medium text-white hover:bg-accent-blue/80"
              >
                Create
              </button>
              <button
                type="button"
                onClick={() => {
                  setShowNewBoard(false);
                  setNewBoardName('');
                }}
                className="flex-1 rounded-md px-2 py-1 text-xs text-text-secondary hover:bg-surface-overlay"
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        {/* Board list */}
        <div className="flex-1 overflow-y-auto p-2">
          {boards.length === 0 && !showNewBoard && (
            <p className="px-2 py-4 text-center text-xs text-text-disabled">
              No boards yet
            </p>
          )}
          {boards.map((board) => (
            <div key={board.id} className="relative group">
              <button
                type="button"
                onClick={() => setActiveBoard(board.id)}
                className={cn(
                  'flex w-full flex-col rounded-md px-3 py-2 text-left transition-colors',
                  activeBoardId === board.id
                    ? 'bg-surface-overlay text-text-primary'
                    : 'text-text-secondary hover:bg-surface-overlay hover:text-text-primary'
                )}
              >
                <span className="text-sm font-medium truncate">
                  {board.name}
                </span>
                <span className="text-xs text-text-tertiary">
                  {board.cards.length} card{board.cards.length !== 1 ? 's' : ''} - {new Date(board.createdAt).toLocaleDateString()}
                </span>
              </button>
              {/* Delete button */}
              {confirmDelete === board.id ? (
                <div className="absolute right-1 top-1 flex gap-1">
                  <button
                    type="button"
                    onClick={() => handleDeleteBoard(board.id)}
                    className="rounded bg-accent-red px-1.5 py-0.5 text-[10px] font-medium text-white"
                  >
                    Delete
                  </button>
                  <button
                    type="button"
                    onClick={() => setConfirmDelete(null)}
                    className="rounded bg-surface-overlay px-1.5 py-0.5 text-[10px] font-medium text-text-secondary"
                  >
                    No
                  </button>
                </div>
              ) : (
                <button
                  type="button"
                  onClick={() => setConfirmDelete(board.id)}
                  className="absolute right-1 top-1 hidden h-6 w-6 items-center justify-center rounded text-text-disabled hover:text-accent-red group-hover:flex"
                  aria-label={`Delete ${board.name}`}
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              )}
            </div>
          ))}
        </div>
      </aside>

      {/* Board Canvas */}
      <div className="flex flex-1 flex-col">
        {!activeBoard && (
          <div className="flex flex-1 flex-col items-center justify-center gap-4">
            <Layout className="h-12 w-12 text-text-disabled" />
            <p className="text-sm text-text-disabled">
              {boards.length === 0
                ? 'Create your first investigation board to start organizing findings.'
                : 'Select a board from the sidebar to start.'}
            </p>
            {boards.length === 0 && (
              <button
                type="button"
                onClick={() => setShowNewBoard(true)}
                className="rounded-md bg-accent-blue px-4 py-2 text-sm font-medium text-white hover:bg-accent-blue/80"
              >
                Create Board
              </button>
            )}
          </div>
        )}

        {activeBoard && (
          <>
            {/* Board header */}
            <div className="flex items-center gap-3 border-b border-border-subtle bg-surface-raised px-4 py-2">
              <Layout className="h-4 w-4 text-text-tertiary" />
              <h3 className="text-sm font-semibold text-text-primary">
                {activeBoard.name}
              </h3>
              <span className="text-xs text-text-tertiary">
                {activeBoard.cards.length} card{activeBoard.cards.length !== 1 ? 's' : ''}
              </span>
            </div>

            {/* Canvas */}
            {activeBoard.cards.length === 0 ? (
              <div className="flex flex-1 flex-col items-center justify-center gap-4">
                <StickyNote className="h-10 w-10 text-text-disabled" />
                <p className="max-w-sm text-center text-sm text-text-disabled">
                  Pin entities from any page to add them to this board. Browse
                  People, Documents, or Events to get started.
                </p>
              </div>
            ) : (
              <div className="relative flex-1 overflow-auto bg-surface-base">
                {/* Grid pattern background */}
                <div
                  className="absolute inset-0"
                  style={{
                    backgroundImage:
                      'radial-gradient(circle, var(--color-border-subtle) 1px, transparent 1px)',
                    backgroundSize: '24px 24px',
                  }}
                />
                <DndContext onDragEnd={handleDragEnd}>
                  <div className="relative h-[2000px] w-[3000px]">
                    {activeBoard.cards.map((card) => (
                      <DraggableBoardCard
                        key={card.id}
                        card={card}
                        boardId={activeBoard.id}
                        onEditNotes={setEditingNotes}
                        onRemove={handleRemoveCard}
                      />
                    ))}
                  </div>
                </DndContext>
              </div>
            )}
          </>
        )}
      </div>

      {/* Notes Editor Modal */}
      {editingNotes && editingCard && (
        <NotesEditor
          cardId={editingCard.id}
          initialNotes={editingCard.notes ?? ''}
          onSave={handleSaveNotes}
          onClose={() => setEditingNotes(null)}
        />
      )}
    </div>
  );
}
