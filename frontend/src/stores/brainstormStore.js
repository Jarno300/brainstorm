import { create } from 'zustand';
import {
  listBrainstorms,
  createBrainstorm,
  getBrainstorm,
  deleteBrainstorm,
  updateBrainstormTitle,
  updateBrainstormModel,
} from '../api';
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
    try {
      const res = await listBrainstorms();
      set({ brainstorms: res.data });
      return res.data;
    } catch (err) {
      logger.error('Failed to load brainstorms:', err);
      set({ brainstorms: [] });
      return [];
    }
  },

  loadDetail: async (id) => {
    try {
      const res = await getBrainstorm(id);
      return res.data;
    } catch (err) {
      logger.error('Failed to load brainstorm:', err);
      return null;
    }
  },

  selectBrainstorm: async (brainstorm) => {
    const full = await get().loadDetail(brainstorm.id);
    if (!full) return;
    set({ activeBrainstorm: full });
  },

  create: async (title) => {
    try {
      const res = await createBrainstorm({ title });
      set({ activeBrainstorm: res.data });
      await get().loadList();
      return res.data;
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
      await deleteBrainstorm(target.id);
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
    try {
      const res = await updateBrainstormTitle(id, title);
      set({ reloadKey: get().reloadKey + 1 });
      return res.data;
    } catch (err) {
      logger.error('Failed to rename brainstorm:', err);
    }
  },

  updateModel: async (id, model) => {
    try {
      await updateBrainstormModel(id, model);
      const res = await getBrainstorm(id);
      if (res.data) set({ activeBrainstorm: res.data });
    } catch (err) {
      logger.error('Failed to update model:', err);
    }
  },

  clear: () => set({
    activeBrainstorm: null,
    deleteTarget: null,
    deleting: false,
  }),
}));

export default useBrainstormStore;
