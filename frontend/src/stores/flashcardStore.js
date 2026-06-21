import { create } from 'zustand';
import {
  getFlashcards,
  getDueFlashcards,
  reviewFlashcard,
  generateFlashcards,
} from '../api';
import logger from '../utils/logger';

const useFlashcardStore = create((set, get) => ({
  // State
  flashcards: [],
  dueFlashcards: [],
  total: 0,
  dueCount: 0,
  isGenerating: false,
  generationStream: null,
  generationText: '',
  generationError: null,

  // Actions

  loadFlashcards: async (brainstormId) => {
    try {
      const res = await getFlashcards(brainstormId);
      if (res.data) {
        set({
          flashcards: res.data.flashcards || [],
          total: res.data.total || 0,
          dueCount: res.data.due_count || 0,
        });
      }
    } catch (err) {
      logger.error('Failed to load flashcards:', err);
    }
  },

  loadDueFlashcards: async (brainstormId) => {
    try {
      const res = await getDueFlashcards(brainstormId);
      if (res.data) {
        set({
          dueFlashcards: res.data.flashcards || [],
          dueCount: res.data.due_count || 0,
        });
      }
    } catch (err) {
      logger.error('Failed to load due flashcards:', err);
    }
  },

  reviewCard: async (brainstormId, flashcardId, quality) => {
    try {
      const res = await reviewFlashcard(brainstormId, flashcardId, quality);
      if (res.data) {
        // Update the card in both lists
        set((state) => ({
          flashcards: state.flashcards.map((c) =>
            c.id === flashcardId ? res.data : c
          ),
          dueFlashcards: state.dueFlashcards.map((c) =>
            c.id === flashcardId ? res.data : c
          ),
        }));
      }
      return res.data;
    } catch (err) {
      logger.error('Failed to review flashcard:', err);
      throw err;
    }
  },

  generateCards: async (brainstormId, callbacks = {}) => {
    const { onToken, onDone, onError } = callbacks;

    set({ isGenerating: true, generationText: '', generationError: null });

    const controller = generateFlashcards(brainstormId, {
      onToken: (token) => {
        set((s) => ({ generationText: s.generationText + token }));
        onToken?.(token);
      },
      onDone: async (event) => {
        set({ isGenerating: false, generationStream: null });
        // Reload flashcards after generation
        await get().loadFlashcards(brainstormId);
        onDone?.(event);
      },
      onError: (error) => {
        set({ isGenerating: false, generationStream: null, generationError: error });
        onError?.(error);
      },
    });

    set({ generationStream: controller });
    return controller;
  },

  abortGeneration: () => {
    const { generationStream } = get();
    if (generationStream) {
      generationStream.abort();
      set({ isGenerating: false, generationStream: null });
    }
  },

  clear: () =>
    set({
      flashcards: [],
      dueFlashcards: [],
      total: 0,
      dueCount: 0,
      isGenerating: false,
      generationStream: null,
      generationText: '',
      generationError: null,
    }),
}));

export default useFlashcardStore;
