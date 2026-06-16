import { useState, useEffect, useMemo, useCallback } from 'react';
import {
  ThemeProvider,
  CssBaseline,
  Box,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  Button,
  alpha,
  useMediaQuery,
  CircularProgress,
} from '@mui/material';
import { createAppTheme } from './theme';
import { useAuth } from './auth/AuthContext';
import LoginDialog from './auth/LoginDialog';
import RegisterDialog from './auth/RegisterDialog';
import Sidebar from './components/Sidebar';
import ChatWindow from './components/ChatWindow';
import TopicDetailPanel from './components/TopicDetailPanel';
import SearchDialog from './components/SearchDialog';
import logger from './utils/logger';
import { researchTopic } from './api';
import { useKeyboardShortcuts } from './hooks/useKeyboardShortcuts';
import { useBrainstormWebSocket } from './hooks/useBrainstormWebSocket';

// ─── Zustand stores ──────────────────────────────────────
import useUIStore from './stores/uiStore';
import useBrainstormStore from './stores/brainstormStore';
import useChatStore from './stores/chatStore';
import useMapStore from './stores/mapStore';
import useLibraryStore from './stores/libraryStore';

// ─── AppContent — main application shell ─────────────────

function AppContent() {
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

  // ── Map store ────────────────────────────────────────────
  const mapData = useMapStore((s) => s.mapData);
  const selectedTopic = useMapStore((s) => s.selectedTopic);
  const exploringTopic = useMapStore((s) => s.exploringTopic);
  const hasClassified = useMapStore((s) => s.hasClassified);
  const loadMap = useMapStore((s) => s.loadMap);
  const selectTopic = useMapStore((s) => s.selectTopic);
  const closeTopicPanel = useMapStore((s) => s.closeTopicPanel);
  const updateTopic = useMapStore((s) => s.updateTopic);
  const deleteTopic = useMapStore((s) => s.deleteTopic);
  const exploreTopic = useMapStore((s) => s.exploreTopic);
  const createEdge = useMapStore((s) => s.createEdge);
  const deleteEdge = useMapStore((s) => s.deleteEdge);
  const handleTopicMove = useMapStore((s) => s.handleTopicMove);
  const setExploringTopic = useMapStore((s) => s.setExploringTopic);
  const setHasClassified = useMapStore((s) => s.setHasClassified);
  const refreshMapData = useMapStore((s) => s.refreshMap);

  // ── Library store ────────────────────────────────────────
  const libraryData = useLibraryStore((s) => s.libraryData);
  const loadLibrary = useLibraryStore((s) => s.loadLibrary);
  const updateLibraryEntry = useLibraryStore((s) => s.updateEntry);
  const deleteLibraryEntry = useLibraryStore((s) => s.deleteEntry);

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
      // Load messages first (always available). Map and library may still
      // be generating — they'll arrive via WebSocket when classification completes.
      try {
        await loadMessages(activeBrainstorm.id);
      } catch (err) {
        logger.error('Load messages error:', err);
      }
      if (cancelled) return;
      // Fire map/library loads independently — don't block on them
      loadMap(activeBrainstorm.id).catch(err => logger.debug('Map load deferred:', err?.message));
      loadLibrary(activeBrainstorm.id).catch(err => logger.debug('Library load deferred:', err?.message));
    })();
    return () => { cancelled = true; };
  }, [activeBrainstorm, loadMessages, loadMap, loadLibrary]);

  // ── WebSocket: live updates after async classification ───
  useBrainstormWebSocket(activeBrainstorm, {
    loadMap,
    loadLibrary,
    loadList,
    setExploringTopic,
    setHasClassified,
  });

  // ⌘K / Ctrl+K for search, Ctrl+Z / Ctrl+Shift+Z for undo/redo
  useKeyboardShortcuts(setSearchOpen);

  // Abort any in-flight stream on unmount
  useEffect(() => {
    return () => abortStream();
  }, [abortStream]);

  // ── Handlers (thin wrappers around store actions) ────────
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

  const handleSuggestionClick = useCallback((topicName, sourceTopicId) => {
    if (!activeBrainstorm) return;
    setExploringTopic({ name: topicName, sourceTopicId });
    setHasClassified(false);
    researchTopic(activeBrainstorm.id, topicName).catch(err =>
      logger.error('Research failed:', err)
    );
  }, [activeBrainstorm, setExploringTopic, setHasClassified]);

  const handleSwitchToLibrary = useCallback(() => {
    useUIStore.getState().setActiveTab('library');
  }, []);

  const handleStartNewBrainstorm = useCallback(async (topic) => {
    try {
      const b = await createBrainstorm(topic);
      if (b) {
        useChatStore.getState().clear();
        useMapStore.getState().clear();
        useLibraryStore.getState().clear();
        useUIStore.getState().setActiveTab('map');
        // Research the topic — builds the knowledge map in one LLM call
        setHasClassified(false);
        researchTopic(b.id, topic).catch(err =>
          logger.error('Research failed:', err)
        );
      }
    } catch (err) {
      logger.error('Failed to start brainstorm:', err);
    }
  }, [createBrainstorm, setHasClassified]);

  const handleModelChange = useCallback(async (model) => {
    if (!activeBrainstorm) return;
    await updateModel(activeBrainstorm.id, model);
  }, [activeBrainstorm, updateModel]);

  const handleRefreshMap = useCallback(async () => {
    if (!activeBrainstorm) return;
    await refreshMapData(activeBrainstorm.id);
  }, [activeBrainstorm, refreshMapData]);

  const handleUpdateLibraryEntryWrap = useCallback(async (entryId, content) => {
    await updateLibraryEntry(entryId, content);
    if (activeBrainstorm) await loadLibrary(activeBrainstorm.id);
  }, [activeBrainstorm, updateLibraryEntry, loadLibrary]);

  const handleDeleteLibraryEntryWrap = useCallback(async (entryId) => {
    await deleteLibraryEntry(entryId);
    if (activeBrainstorm) await loadLibrary(activeBrainstorm.id);
  }, [activeBrainstorm, deleteLibraryEntry, loadLibrary]);

  const handleDeleteTopicWrap = useCallback(async (topicId) => {
    if (!activeBrainstorm) return;
    await deleteTopic(activeBrainstorm.id, topicId);
    if (activeBrainstorm) await loadLibrary(activeBrainstorm.id);
  }, [activeBrainstorm, deleteTopic, loadLibrary]);

  const handleUpdateTopicWrap = useCallback(async (topicId, data) => {
    if (!activeBrainstorm) return;
    await updateTopic(activeBrainstorm.id, topicId, data);
  }, [activeBrainstorm, updateTopic]);

  const handleExploreTopicWrap = useCallback(async (topicId) => {
    if (!activeBrainstorm) return;
    await exploreTopic(activeBrainstorm.id, topicId);
    if (activeBrainstorm) await loadLibrary(activeBrainstorm.id);
  }, [activeBrainstorm, exploreTopic, loadLibrary]);

  const handleTopicMoveWrap = useCallback((topicId, x, y) => {
    if (!activeBrainstorm) return;
    handleTopicMove(activeBrainstorm.id, topicId, x, y);
  }, [activeBrainstorm, handleTopicMove]);

  const handleEdgeCreate = useCallback(async (sourceId, targetId) => {
    if (!activeBrainstorm) return;
    await createEdge(activeBrainstorm.id, sourceId, targetId);
  }, [activeBrainstorm, createEdge]);

  const handleEdgeDelete = useCallback(async (edge) => {
    if (!activeBrainstorm) return;
    await deleteEdge(activeBrainstorm.id, edge);
  }, [activeBrainstorm, deleteEdge]);

  const handleAddBlankTopic = useCallback(async (brainstormId, name) => {
    await useMapStore.getState().addBlankTopic(brainstormId, name);
  }, []);

  const handleGenerateContent = useCallback(async (brainstormId, topicId, callbacks) => {
    return await useMapStore.getState().generateContent(brainstormId, topicId, callbacks);
  }, []);

  const handleUpdateOutline = useCallback((brainstormId, topicId, outline) => {
    useMapStore.getState().updateOutline(brainstormId, topicId, outline);
  }, []);

  const handleExploreConnection = useCallback(async (brainstormId, sourceId, targetId, x, y) => {
    try {
      await useMapStore.getState().exploreConnection(brainstormId, sourceId, targetId, x, y);
    } catch (err) {
      // 409: connection already exists — silently ignore
      if (err?.response?.status !== 409) {
        logger.error('Failed to explore connection:', err);
      }
    }
  }, []);

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Box sx={{ display: 'flex', height: '100vh', overflow: 'hidden', bgcolor: 'background.default', position: 'relative' }}>
        {/* ── Ambient Glow ──────────────────────────────── */}
        <Box sx={(theme) => ({
          position: 'fixed', inset: 0, overflow: 'hidden', pointerEvents: 'none', zIndex: 0,
          opacity: theme.palette.mode === 'dark' ? 0.8 : 0.25,
          transition: 'opacity 0.5s ease',
          '& > div': {
            position: 'absolute', borderRadius: '50%',
            opacity: theme.palette.mode === 'dark' ? 0.1 : 0.06,
          },
        })}>
          <Box sx={{ width: '40%', height: '40%', bgcolor: 'primary.main', top: '-12%', left: '-8%', filter: 'blur(160px)' }} />
          <Box sx={{ width: '30%', height: '30%', bgcolor: 'secondary.main', bottom: '-8%', right: '-4%', filter: 'blur(140px)' }} />
          <Box sx={{ width: '20%', height: '20%', bgcolor: 'primary.light', top: '45%', right: '25%', filter: 'blur(120px)', opacity: 0.5 }} />
        </Box>

        <Sidebar
          brainstorms={brainstorms}
          activeBrainstorm={activeBrainstorm}
          onNew={handleNewBrainstorm}
          onSelect={handleSelectBrainstorm}
          onDelete={requestDelete}
          mode={mode}
          onToggleTheme={toggleTheme}
          collapsed={sidebarCollapsed}
          onToggleCollapse={toggleSidebar}
          onRenameComplete={() => useBrainstormStore.getState().loadList()}
        />
        <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0, position: 'relative', zIndex: 1 }}>
          <Box sx={{ display: 'flex', flex: 1, minHeight: 0 }}>
            <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
              <ChatWindow
                activeBrainstorm={activeBrainstorm}
                mapData={mapData}
                libraryData={libraryData}
                activeTab={activeTab}
                onTabChange={useUIStore.getState().setActiveTab}
                onRefreshMap={handleRefreshMap}
                onUpdateLibraryEntry={handleUpdateLibraryEntryWrap}
                onDeleteLibraryEntry={handleDeleteLibraryEntryWrap}
                onDeleteTopic={handleDeleteTopicWrap}
                onUpdateTopic={handleUpdateTopicWrap}
                onStartNewBrainstorm={handleStartNewBrainstorm}
                onSuggestionClick={handleSuggestionClick}
                onTopicClick={selectTopic}
                onTopicMove={handleTopicMoveWrap}
                onEdgeCreate={handleEdgeCreate}
                onEdgeDelete={handleEdgeDelete}
                selectedTopic={selectedTopic}
                exploringSuggestion={exploringTopic}
                hasClassified={hasClassified}
                themeId={themeId}
                onThemeChange={handleThemeChange}
                onModelChange={handleModelChange}
                onAddBlankTopic={handleAddBlankTopic}
                onGenerateContent={handleGenerateContent}
                onUpdateOutline={handleUpdateOutline}
                onExploreConnection={handleExploreConnection}
              />
            </Box>
            {selectedTopic && (
              <TopicDetailPanel
                topic={selectedTopic}
                mapData={mapData}
                libraryData={libraryData}
                onClose={closeTopicPanel}
                onUpdate={handleUpdateTopicWrap}
                onDelete={handleDeleteTopicWrap}
                onExplore={handleExploreTopicWrap}
                onSwitchToLibrary={handleSwitchToLibrary}
              />
            )}
          </Box>
        </Box>
      </Box>

      {/* ── Search Dialog ────────────────────────────────── */}
      <SearchDialog open={searchOpen} onClose={() => setSearchOpen(false)} />

      {/* ── Delete Dialog ────────────────────────────────── */}
      <Dialog open={Boolean(deleteTarget)} onClose={cancelDelete} maxWidth="xs">
        <DialogTitle sx={{ fontWeight: 700, fontSize: '1.1rem', pb: 0.5 }}>Delete brainstorm?</DialogTitle>
        <DialogContent sx={{ pb: 1 }}>
          <DialogContentText sx={(theme) => ({ color: alpha(theme.palette.text.primary, 0.6), fontSize: '0.875rem', lineHeight: 1.6 })}>
            {deleteTarget
              ? `This will permanently delete "${deleteTarget.title}", including its messages, knowledge map, and library entries.`
              : 'This will permanently delete the selected brainstorm.'}
          </DialogContentText>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2.5, gap: 1 }}>
          <Button onClick={cancelDelete} disabled={deleting}
            sx={(theme) => ({ color: alpha(theme.palette.text.primary, 0.6), textTransform: 'none', fontWeight: 600, borderRadius: 2, px: 2.5, py: 1, fontSize: '0.85rem', '&:hover': { bgcolor: alpha(theme.palette.action.hover, 0.5), color: theme.palette.text.primary } })}>
            Cancel
          </Button>
          <Button onClick={confirmDelete} disabled={deleting} variant="contained" color="error"
            sx={{ borderRadius: 1, textTransform: 'none', fontWeight: 700, px: 2.5, py: 1, fontSize: '0.85rem', boxShadow: (theme) => `0 4px 16px ${alpha(theme.palette.error.main, 0.35)}`, '&:hover': { boxShadow: (theme) => `0 6px 24px ${alpha(theme.palette.error.main, 0.5)}` } }}>
            {deleting ? 'Deleting...' : 'Delete'}
          </Button>
        </DialogActions>
      </Dialog>
    </ThemeProvider>
  );
}

// ─── AuthGate — routes unauthenticated users to login/register ──

function AuthGate() {
  const { token, loading } = useAuth();
  const [authView, setAuthView] = useState('login');

  if (loading) {
    return (
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', bgcolor: 'background.default' }}>
        <CircularProgress size={32} />
      </Box>
    );
  }

  if (token) {
    return <AppContent />;
  }

  return (
    <ThemeProvider theme={createAppTheme('light', 'auburn')}>
      <CssBaseline />
      <Box sx={{ height: '100vh', bgcolor: 'background.default' }} />
      <LoginDialog
        open={authView === 'login'}
        onSwitchToRegister={() => setAuthView('register')}
      />
      <RegisterDialog
        open={authView === 'register'}
        onSwitchToLogin={() => setAuthView('login')}
      />
    </ThemeProvider>
  );
}

function App() {
  return <AuthGate />;
}

export default App;
