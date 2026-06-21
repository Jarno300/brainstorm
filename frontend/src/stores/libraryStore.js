import { create } from 'zustand';
import {
  getLibrary,
  updateLibraryEntry,
  deleteLibraryEntry,
} from '../api';
import logger from '../utils/logger';

const useLibraryStore = create((set) => ({
  // State
  libraryData: [],

  // Actions

  loadLibrary: async (brainstormId) => {
    try {
      const res = await getLibrary(brainstormId);
      if (res.data) set({ libraryData: res.data });
      return res.data;
    } catch (err) {
      logger.error('Failed to load library:', err);
    }
  },

  updateEntry: async (entryId, content) => {
    try {
      await updateLibraryEntry(entryId, content);
    } catch (err) {
      logger.error('Failed to update library entry:', err);
    }
  },

  deleteEntry: async (entryId) => {
    try {
      await deleteLibraryEntry(entryId);
    } catch (err) {
      logger.error('Failed to delete library entry:', err);
    }
  },

  clear: () => set({ libraryData: [] }),
}));

export default useLibraryStore;
