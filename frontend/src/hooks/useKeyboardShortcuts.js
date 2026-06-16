import { useEffect } from 'react';
import useUndoStore from '../stores/undoStore';

export function useKeyboardShortcuts(setSearchOpen) {
  useEffect(() => {
    const handler = (e) => {
      const mod = e.metaKey || e.ctrlKey;
      if (mod && e.key === 'k') {
        e.preventDefault();
        setSearchOpen(true);
        return;
      }
      if (mod && e.key === 'z' && !e.shiftKey) {
        e.preventDefault();
        useUndoStore.getState().undo();
        return;
      }
      if (mod && (e.key === 'y' || (e.key === 'z' && e.shiftKey))) {
        e.preventDefault();
        useUndoStore.getState().redo();
        return;
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [setSearchOpen]);
}
