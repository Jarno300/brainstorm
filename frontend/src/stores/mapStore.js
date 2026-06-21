import { create } from 'zustand';
import {
  getMap,
  refreshMap,
  updateTopic,
  deleteTopic,
  exploreTopic,
  createEdge,
  deleteEdge,
  createTopic,
  generateTopicContent,
  exploreConnection,
  getGaps,
} from '../api';
import logger from '../utils/logger';

const useMapStore = create((set, get) => ({
  // State
  mapData: { topics: [], edges: [], suggestions: [] },
  selectedTopic: null,
  exploringTopic: null,         // { name, sourceTopicId }
  exploringEdge: null,           // { sourceId, targetId, x, y, sourceName, targetName }
  hasClassified: false,
  gaps: [],
  moveTimers: {},

  // Actions

  loadMap: async (brainstormId) => {
    try {
      const res = await getMap(brainstormId);
      if (res.data) set({ mapData: res.data });
      return res.data;
    } catch (err) {
      logger.error('Failed to load map:', err);
    }
  },

  refreshMap: async (brainstormId) => {
    try {
      const res = await refreshMap(brainstormId);
      if (res.data) set({ mapData: res.data });
      return res.data;
    } catch (err) {
      logger.error('Failed to refresh map:', err);
    }
  },

  selectTopic: (topic) => set({ selectedTopic: topic }),
  closeTopicPanel: () => set({ selectedTopic: null }),

  updateTopic: async (brainstormId, topicId, data) => {
    try {
      await updateTopic(brainstormId, topicId, data);
      const res = await getMap(brainstormId);
      if (res.data) set({ mapData: res.data });
      const fresh = res.data?.topics?.find((t) => t.id === topicId);
      if (fresh) set({ selectedTopic: fresh });
    } catch (err) {
      logger.error('Failed to update topic:', err);
    }
  },

  deleteTopic: async (brainstormId, topicId) => {
    try {
      await deleteTopic(brainstormId, topicId);
      set({ selectedTopic: null });
      await get().loadMap(brainstormId);
    } catch (err) {
      logger.error('Failed to delete topic:', err);
    }
  },

  exploreTopic: async (brainstormId, topicId) => {
    try {
      const res = await exploreTopic(brainstormId, topicId);
      if (res.data) set({ mapData: res.data });
    } catch (err) {
      logger.error('Failed to explore topic:', err);
    }
  },

  createEdge: async (brainstormId, sourceId, targetId) => {
    try {
      await createEdge(brainstormId, {
        source_topic_id: sourceId,
        target_topic_id: targetId,
        relationship: 'related',
        weight: 0.5,
      });
      await get().loadMap(brainstormId);
    } catch (err) {
      if (err?.response?.status !== 409) {
        logger.error('Failed to create edge:', err);
      }
    }
  },

  deleteEdge: async (brainstormId, edge) => {
    try {
      await deleteEdge(brainstormId, edge.id);
      await get().loadMap(brainstormId);
    } catch (err) {
      logger.error('Failed to delete edge:', err);
    }
  },

  // Debounced topic position save
  handleTopicMove: (brainstormId, topicId, x, y) => {
    // Update local state immediately for smooth dragging
    set((s) => ({
      mapData: {
        ...s.mapData,
        topics: s.mapData.topics?.map((t) =>
          t.id === topicId ? { ...t, position_x: x, position_y: y } : t
        ),
      },
    }));

    // Debounce the API call
    const timers = get().moveTimers;
    if (timers[topicId]) clearTimeout(timers[topicId]);
    timers[topicId] = setTimeout(() => {
      updateTopic(brainstormId, topicId, { position_x: x, position_y: y }).catch(
        (err) => logger.error('Failed to save topic position:', err)
      );
    }, 500);
  },

  // Create a blank topic card (no AI generation)
  addBlankTopic: async (brainstormId, name) => {
    try {
      const res = await createTopic(brainstormId, {
        name,
        auto_generate: false,
      });
      await get().loadMap(brainstormId);
      return res.data;
    } catch (err) {
      logger.error('Failed to add blank topic:', err);
      throw err;
    }
  },

  // Update outline locally (optimistic) and save via API
  updateOutline: async (brainstormId, topicId, outline) => {
    // Update local state immediately
    set((s) => ({
      mapData: {
        ...s.mapData,
        topics: s.mapData.topics?.map((t) =>
          t.id === topicId ? { ...t, outline } : t
        ),
      },
    }));
    // Persist to backend (debounced per topic)
    const timers = get().moveTimers;
    const outlineKey = `outline_${topicId}`;
    if (timers[outlineKey]) clearTimeout(timers[outlineKey]);
    timers[outlineKey] = setTimeout(() => {
      patchTopic(brainstormId, topicId, { outline }).catch(
        (err) => logger.error('Failed to save outline:', err)
      );
    }, 600);
  },

  // Generate content for a topic (flushes pending outline save first)
  generateContent: async (brainstormId, topicId, callbacks) => {
    // Flush any pending outline save before generating
    const timers = get().moveTimers;
    const outlineKey = `outline_${topicId}`;
    if (timers[outlineKey]) {
      clearTimeout(timers[outlineKey]);
      delete timers[outlineKey];
      // Sync the latest outline to the backend immediately
      const topic = get().mapData?.topics?.find(t => t.id === topicId);
      if (topic?.outline) {
        await updateTopic(brainstormId, topicId, { outline: topic.outline });
      }
    }
    return generateTopicContent(brainstormId, topicId, {
      ...callbacks,
      onDone: async (event) => {
        await get().loadMap(brainstormId);
        callbacks.onDone?.(event);
      },
    });
  },

  setExploringTopic: (topic) => set({ exploringTopic: topic }),
  setExploringEdge: (edge) => set({ exploringEdge: edge }),
  setHasClassified: (v) => set({ hasClassified: v }),

  // Gap detection
  detectGaps: async (brainstormId) => {
    try {
      const res = await getGaps(brainstormId);
      if (res.data) set({ gaps: res.data.gaps || [] });
      return res.data;
    } catch (err) {
      logger.error('Failed to detect gaps:', err);
    }
  },

  // Explore connection between two topics (dispatches to backend, result via WebSocket)
  exploreConnection: async (brainstormId, sourceId, targetId, x, y) => {
    try {
      await exploreConnection(brainstormId, {
        source_topic_id: sourceId,
        target_topic_id: targetId,
        position_x: x,
        position_y: y,
      });
      // Don't loadMap here — the WebSocket topic_generated event will trigger it
      // once the Celery task completes and the connection card is created.
    } catch (err) {
      logger.error('Failed to explore connection:', err);
      throw err;
    }
  },

  clear: () =>
    set({
      mapData: { topics: [], edges: [], suggestions: [] },
      selectedTopic: null,
      exploringTopic: null,
      exploringEdge: null,
      hasClassified: false,
      gaps: [],
      moveTimers: {},
    }),
}));

export default useMapStore;
