import { create } from 'zustand';

/**
 * Undo/redo store for canvas operations.
 *
 * Tracks commands with execute/undo functions. Max history depth
 * prevents memory leaks on long sessions.
 */

const MAX_HISTORY = 50;

const useUndoStore = create((set, get) => ({
  // Stack of undo entries: [{ undo, redo, label }]
  undoStack: [],
  redoStack: [],

  /**
   * Execute an action and push its inverse onto the undo stack.
   *
   * @param {string} label - Human-readable label (e.g., "Move topic")
   * @param {Function} execute - The forward action
   * @param {Function} undo - The inverse action
   */
  execute: (label, execute, undo) => {
    // Execute the forward action immediately
    execute();

    // Push onto undo stack
    set((s) => {
      const stack = [...s.undoStack, { undo, redo: execute, label }];
      // Enforce max history
      if (stack.length > MAX_HISTORY) {
        stack.shift();
      }
      return { undoStack: stack, redoStack: [] }; // Clear redo on new action
    });
  },

  undo: () => {
    const { undoStack, redoStack } = get();
    if (undoStack.length === 0) return;

    const command = undoStack[undoStack.length - 1];
    command.undo();

    set({
      undoStack: undoStack.slice(0, -1),
      redoStack: [...redoStack, command],
    });
  },

  redo: () => {
    const { undoStack, redoStack } = get();
    if (redoStack.length === 0) return;

    const command = redoStack[redoStack.length - 1];
    command.redo();

    set({
      undoStack: [...undoStack, command],
      redoStack: redoStack.slice(0, -1),
    });
  },

  clear: () => set({ undoStack: [], redoStack: [] }),

  canUndo: () => get().undoStack.length > 0,
  canRedo: () => get().redoStack.length > 0,
}));

export default useUndoStore;
