import { create } from 'zustand';
import {
  fetchMap,
  triggerMapRefresh,
  patchTopic,
  removeTopic,
  deepenTopic,
  addEdge,
  removeEdge,
  createBlankTopic,
  streamTopicContent,
  createConnectionTopic,
} from '../services/mapService';
import logger from '../utils/logger';

const useMapStore = create((set, get) => ({
  // State
  mapData: { topics: [], edges: [], suggestions: [] },
  selectedTopic: null,
  exploringTopic: null,         // { name, sourceTopicId }
  hasClassified: false,
  moveTimers: {},

  // Actions

  loadMap: async (brainstormId) => {
    const data = await fetchMap(brainstormId);
    if (data) set({ mapData: data });
    return data;
  },

  refreshMap: async (brainstormId) => {
    const data = await triggerMapRefresh(brainstormId);
    if (data) set({ mapData: data });
    return data;
  },

  selectTopic: (topic) => set({ selectedTopic: topic }),
  closeTopicPanel: () => set({ selectedTopic: null }),

  updateTopic: async (brainstormId, topicId, data) => {
    try {
      await patchTopic(brainstormId, topicId, data);
      const mapRes = await fetchMap(brainstormId);
      if (mapRes) set({ mapData: mapRes });
      const fresh = mapRes?.topics?.find((t) => t.id === topicId);
      if (fresh) set({ selectedTopic: fresh });
    } catch (err) {
      logger.error('Failed to update topic:', err);
    }
  },

  deleteTopic: async (brainstormId, topicId) => {
    try {
      await removeTopic(brainstormId, topicId);
      set({ selectedTopic: null });
      await get().loadMap(brainstormId);
    } catch (err) {
      logger.error('Failed to delete topic:', err);
    }
  },

  exploreTopic: async (brainstormId, topicId) => {
    try {
      const data = await deepenTopic(brainstormId, topicId);
      if (data) set({ mapData: data });
    } catch (err) {
      logger.error('Failed to explore topic:', err);
    }
  },

  createEdge: async (brainstormId, sourceId, targetId) => {
    try {
      await addEdge(brainstormId, sourceId, targetId);
      await get().loadMap(brainstormId);
    } catch (err) {
      logger.error('Failed to create edge:', err);
    }
  },

  deleteEdge: async (brainstormId, edge) => {
    try {
      await removeEdge(brainstormId, edge.id);
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
      patchTopic(brainstormId, topicId, { position_x: x, position_y: y }).catch(
        (err) => logger.error('Failed to save topic position:', err)
      );
    }, 500);
  },

  // Create a blank topic card (no AI generation)
  addBlankTopic: async (brainstormId, name) => {
    try {
      const topic = await createBlankTopic(brainstormId, name);
      // Reload the full map to get the topic with server-assigned fields
      await get().loadMap(brainstormId);
      return topic;
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
        await patchTopic(brainstormId, topicId, { outline: topic.outline });
      }
    }
    return streamTopicContent(brainstormId, topicId, {
      ...callbacks,
      onDone: async (event) => {
        await get().loadMap(brainstormId);
        callbacks.onDone?.(event);
      },
    });
  },

  setExploringTopic: (topic) => set({ exploringTopic: topic }),
  setHasClassified: (v) => set({ hasClassified: v }),

  // Explore connection between two topics
  exploreConnection: async (brainstormId, sourceId, targetId, x, y) => {
    try {
      const topic = await createConnectionTopic(brainstormId, sourceId, targetId, x, y);
      await get().loadMap(brainstormId);
      return topic;
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
      hasClassified: false,
      moveTimers: {},
    }),
}));

export default useMapStore;
