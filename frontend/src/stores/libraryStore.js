import { create } from 'zustand';
import {
  fetchLibrary,
  patchLibraryEntry,
  removeLibraryEntry,
} from '../services/libraryService';
import logger from '../utils/logger';

const useLibraryStore = create((set) => ({
  // State
  libraryData: [],

  // Actions

  loadLibrary: async (brainstormId) => {
    const data = await fetchLibrary(brainstormId);
    if (data) set({ libraryData: data });
    return data;
  },

  updateEntry: async (entryId, content) => {
    try {
      await patchLibraryEntry(entryId, content);
    } catch (err) {
      logger.error('Failed to update library entry:', err);
    }
  },

  deleteEntry: async (entryId) => {
    try {
      await removeLibraryEntry(entryId);
    } catch (err) {
      logger.error('Failed to delete library entry:', err);
    }
  },

  clear: () => set({ libraryData: [] }),
}));

export default useLibraryStore;
