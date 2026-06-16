import { create } from 'zustand';
import {
  fetchBrainstorms,
  fetchBrainstorm,
  createNewBrainstorm,
  removeBrainstorm,
  renameBrainstorm,
  changeBrainstormModel,
} from '../services/brainstormService';
import logger from '../utils/logger';

const useBrainstormStore = create((set, get) => ({
  // State
  brainstorms: [],
  activeBrainstorm: null,
  deleting: false,
  deleteTarget: null,
  reloadKey: 0,

  // Actions

  loadList: async () => {
    const data = await fetchBrainstorms();
    set({ brainstorms: data });
    return data;
  },

  loadDetail: async (id) => {
    return fetchBrainstorm(id);
  },

  selectBrainstorm: async (brainstorm) => {
    const full = await get().loadDetail(brainstorm.id);
    if (!full) return;
    set({ activeBrainstorm: full });
  },

  create: async (title) => {
    try {
      const data = await createNewBrainstorm(title);
      set({ activeBrainstorm: data });
      await get().loadList();
      return data;
    } catch (err) {
      logger.error('Failed to create brainstorm:', err);
      throw err;
    }
  },

  requestDelete: (brainstorm) => set({ deleteTarget: brainstorm }),
  cancelDelete: () => {
    if (!get().deleting) set({ deleteTarget: null });
  },

  confirmDelete: async () => {
    const target = get().deleteTarget;
    if (!target) return;
    set({ deleting: true });
    try {
      await removeBrainstorm(target.id);
      const next = await get().loadList();
      const wasActive = get().activeBrainstorm?.id === target.id;
      set({ deleteTarget: null, deleting: false });
      if (wasActive) {
        if (next.length > 0) await get().selectBrainstorm(next[0]);
        else set({ activeBrainstorm: null });
      }
    } catch (err) {
      if (err?.response?.status === 404) {
        const next = await get().loadList();
        const wasActive = get().activeBrainstorm?.id === target.id;
        set({ deleteTarget: null, deleting: false });
        if (wasActive) {
          if (next.length > 0) await get().selectBrainstorm(next[0]);
          else set({ activeBrainstorm: null });
        }
      } else {
        logger.error(err);
        set({ deleting: false });
      }
    }
  },

  updateTitle: async (id, title) => {
    const data = await renameBrainstorm(id, title);
    set({ reloadKey: get().reloadKey + 1 });
    return data;
  },

  updateModel: async (id, model) => {
    const updated = await changeBrainstormModel(id, model);
    if (updated) set({ activeBrainstorm: updated });
  },

  clear: () => set({
    activeBrainstorm: null,
    deleteTarget: null,
    deleting: false,
  }),
}));

export default useBrainstormStore;
