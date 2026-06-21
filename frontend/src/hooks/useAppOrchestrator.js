import { useState, useEffect, useMemo, useCallback } from 'react';
import { useMediaQuery } from '@mui/material';
import { createAppTheme } from '../theme';
import { researchTopic } from '../api';
import { useKeyboardShortcuts } from './useKeyboardShortcuts';
import { useBrainstormWebSocket } from './useBrainstormWebSocket';
import useUIStore from '../stores/uiStore';
import useBrainstormStore from '../stores/brainstormStore';
import useChatStore from '../stores/chatStore';
import useMapStore from '../stores/mapStore';
import useLibraryStore from '../stores/libraryStore';
import logger from '../utils/logger';

/**
 * Central orchestrator hook for the Brainstorm app.
 *
 * Manages all cross-cutting concerns — theme, brainstorm lifecycle,
 * WebSocket, keyboard shortcuts, parallax, and handler callbacks.
 * Feature components read their own stores; this hook only handles
 * concerns that span multiple features.
 */
export function useAppOrchestrator() {
  const prefersDark = useMediaQuery('(prefers-color-scheme: dark)');
  const [searchOpen, setSearchOpen] = useState(false);

  // ── UI store ────────────────────────────────────────────
  const mode = useUIStore((s) => s.mode);
  const themeId = useUIStore((s) => s.themeId);
  const sidebarCollapsed = useUIStore((s) => s.sidebarCollapsed);
  const activeTab = useUIStore((s) => s.activeTab);
  const setMode = useUIStore((s) => s.setMode);
  const setThemeId = useUIStore((s) => s.setThemeId);
  const toggleSidebar = useUIStore((s) => s.toggleSidebar);

  // ── Brainstorm store ─────────────────────────────────────
  const brainstorms = useBrainstormStore((s) => s.brainstorms);
  const activeBrainstorm = useBrainstormStore((s) => s.activeBrainstorm);
  const deleteTarget = useBrainstormStore((s) => s.deleteTarget);
  const deleting = useBrainstormStore((s) => s.deleting);
  const reloadKey = useBrainstormStore((s) => s.reloadKey);
  const loadList = useBrainstormStore((s) => s.loadList);
  const selectBrainstorm = useBrainstormStore((s) => s.selectBrainstorm);
  const createBrainstorm = useBrainstormStore((s) => s.create);
  const requestDelete = useBrainstormStore((s) => s.requestDelete);
  const cancelDelete = useBrainstormStore((s) => s.cancelDelete);
  const confirmDelete = useBrainstormStore((s) => s.confirmDelete);
  const updateModel = useBrainstormStore((s) => s.updateModel);

  // ── Chat store ───────────────────────────────────────────
  const loadMessages = useChatStore((s) => s.loadMessages);
  const abortStream = useChatStore((s) => s.abortStream);

  // ── Map store (only what's needed for orchestration) ─────
  const loadMap = useMapStore((s) => s.loadMap);
  const setExploringTopic = useMapStore((s) => s.setExploringTopic);
  const setExploringEdge = useMapStore((s) => s.setExploringEdge);
  const setHasClassified = useMapStore((s) => s.setHasClassified);

  // ── Library store (only what's needed for WebSocket) ─────
  const loadLibrary = useLibraryStore((s) => s.loadLibrary);

  // ── Theme ────────────────────────────────────────────────
  useEffect(() => {
    const stored = localStorage.getItem('brainstorm-theme');
    if (stored) setMode(stored);
    else if (prefersDark) setMode('dark');
  }, [prefersDark, setMode]);

  const theme = useMemo(() => createAppTheme(mode, themeId), [mode, themeId]);

  // ── Initial brainstorm list load ─────────────────────────
  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (!cancelled) await loadList();
    })();
    return () => { cancelled = true; };
  }, [reloadKey, loadList]);

  // ── Load brainstorm data on selection ────────────────────
  useEffect(() => {
    if (!activeBrainstorm) return;
    let cancelled = false;
    (async () => {
      try {
        await loadMessages(activeBrainstorm.id);
      } catch (err) {
        logger.error('Load messages error:', err);
      }
      if (cancelled) return;
      loadMap(activeBrainstorm.id).catch(err => logger.debug('Map load deferred:', err?.message));
      loadLibrary(activeBrainstorm.id).catch(err => logger.debug('Library load deferred:', err?.message));
    })();
    return () => { cancelled = true; };
  }, [activeBrainstorm, loadMessages, loadMap, loadLibrary]);

  // ── WebSocket: live updates after async classification ───
  useBrainstormWebSocket(activeBrainstorm, {
    loadMap, loadLibrary, loadList,
    setExploringTopic, setExploringEdge, setHasClassified,
  });

  // ⌘K / Ctrl+K for search, Ctrl+Z / Ctrl+Shift+Z for undo/redo
  useKeyboardShortcuts(setSearchOpen);

  // Abort any in-flight stream on unmount
  useEffect(() => {
    return () => abortStream();
  }, [abortStream]);

  // ── Handlers ─────────────────────────────────────────────

  const handleNewBrainstorm = useCallback(() => {
    abortStream();
    useBrainstormStore.getState().clear();
    useChatStore.getState().clear();
    useMapStore.getState().clear();
    useLibraryStore.getState().clear();
    useUIStore.getState().setActiveTab('map');
  }, [abortStream]);

  const handleSelectBrainstorm = useCallback(async (brainstorm) => {
    abortStream();
    await selectBrainstorm(brainstorm);
    useUIStore.getState().setActiveTab('map');
    useChatStore.getState().clear();
    useMapStore.getState().clear();
    useLibraryStore.getState().clear();
  }, [abortStream, selectBrainstorm]);

  const toggleTheme = useCallback(() => {
    setMode(mode === 'dark' ? 'light' : 'dark');
  }, [mode, setMode]);

  const handleThemeChange = useCallback((newThemeId) => {
    setThemeId(newThemeId);
  }, [setThemeId]);

  const handleStartNewBrainstorm = useCallback(async (topic) => {
    try {
      const b = await createBrainstorm(topic);
      if (b) {
        useChatStore.getState().clear();
        useMapStore.getState().clear();
        useLibraryStore.getState().clear();
        useUIStore.getState().setActiveTab('map');
        setHasClassified(false);
        researchTopic(b.id, topic).catch(err => logger.error('Research failed:', err));
      }
    } catch (err) {
      logger.error('Failed to start brainstorm:', err);
    }
  }, [createBrainstorm, setHasClassified]);

  const handleModelChange = useCallback(async (model) => {
    if (!activeBrainstorm) return;
    await updateModel(activeBrainstorm.id, model);
  }, [activeBrainstorm, updateModel]);

  return {
    // State
    searchOpen, setSearchOpen,
    theme,
    mode, themeId, sidebarCollapsed, activeTab,
    brainstorms, activeBrainstorm,
    deleteTarget, deleting,
    // Handlers
    handleNewBrainstorm,
    handleSelectBrainstorm,
    toggleTheme,
    handleThemeChange,
    handleStartNewBrainstorm,
    handleModelChange,
    requestDelete, cancelDelete, confirmDelete,
    toggleSidebar,
    setActiveTab: useUIStore.getState().setActiveTab,
    reloadList: () => useBrainstormStore.getState().loadList(),
  };
}
