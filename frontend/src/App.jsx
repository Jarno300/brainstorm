import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
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
  IconButton,
  Tooltip,
  CircularProgress,
} from '@mui/material';
import { DarkMode, LightMode } from '@mui/icons-material';
import { createAppTheme } from './theme';
import { useAuth } from './auth/AuthContext';
import LoginDialog from './auth/LoginDialog';
import RegisterDialog from './auth/RegisterDialog';
import Sidebar from './components/Sidebar';
import ChatWindow from './components/ChatWindow';
import TopicDetailPanel from './components/TopicDetailPanel';
import {
  listBrainstorms,
  createBrainstorm,
  getBrainstorm,
  deleteBrainstorm,
  getMessages,
  streamMessage,
  updateTopic,
  deleteTopic,
  createTopic,
  exploreTopic,
  getMap,
  refreshMap,
  getLibrary,
  updateLibraryEntry,
  deleteLibraryEntry,
  updateBrainstormModel,
  buildBrainstormWebSocketUrl,
} from './api';

// ─── Theme — delegated to theme system ─────────────────
// See src/theme/createAppTheme.js

function AppContent() {
  const prefersDark = useMediaQuery('(prefers-color-scheme: dark)');
  const [mode, setMode] = useState('light');
  const [themeId, setThemeId] = useState(() => {
    return localStorage.getItem('brainstorm-theme-id') || 'auburn';
  });
  const handleThemeChange = useCallback((newThemeId) => {
    setThemeId(newThemeId);
    localStorage.setItem('brainstorm-theme-id', newThemeId);
  }, []);

  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => {
    return localStorage.getItem('brainstorm-sidebar-collapsed') === 'true';
  });
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    const stored = localStorage.getItem('brainstorm-theme');
    if (stored) setMode(stored);
    else if (prefersDark) setMode('dark');
  }, [prefersDark]);

  const theme = useMemo(() => createAppTheme(mode, themeId), [mode, themeId]);

  const toggleTheme = useCallback(() => {
    setMode(prev => {
      const next = prev === 'dark' ? 'light' : 'dark';
      localStorage.setItem('brainstorm-theme', next);
      return next;
    });
  }, []);

  const toggleSidebar = useCallback(() => {
    setSidebarCollapsed(prev => {
      const next = !prev;
      localStorage.setItem('brainstorm-sidebar-collapsed', next);
      return next;
    });
  }, []);

  const [brainstorms, setBrainstorms] = useState([]);
  const [activeBrainstorm, setActiveBrainstorm] = useState(null);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [messages, setMessages] = useState([]);
  const [mapData, setMapData] = useState({ topics: [], edges: [], suggestions: [] });
  const [libraryData, setLibraryData] = useState([]);
  const [activeTab, setActiveTab] = useState('map');
  const [sending, setSending] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [chatError, setChatError] = useState('');
  const [exploringTopic, setExploringTopic] = useState(null);
  const [hasClassified, setHasClassified] = useState(false);
  const [selectedTopic, setSelectedTopic] = useState(null);
  const wsRef = useRef(null);
  const streamAbortRef = useRef(null);
  const sendingRef = useRef(false);
  const activeBrainstormRef = useRef(null);

  // Keep ref in sync with state
  useEffect(() => {
    activeBrainstormRef.current = activeBrainstorm;
  }, [activeBrainstorm]);

  const loadBrainstorms = useCallback(async () => {
    try { const res = await listBrainstorms(); setBrainstorms(res.data); return res.data; }
    catch (err) { console.error('Failed to load brainstorms:', err); return []; }
  }, [reloadKey]);

  const loadBrainstormDetails = useCallback(async (id) => {
    try { const res = await getBrainstorm(id); return res.data; }
    catch (err) { console.error('Failed to load brainstorm:', err); return null; }
  }, []);

  const loadMap = useCallback(async (id) => {
    try { const res = await getMap(id); console.log('[DEBUG] loadMap returned:', JSON.stringify(res.data).slice(0, 300)); setMapData(res.data); }
    catch (err) { console.error('[DEBUG] Failed to load map:', err); }
  }, []);

  const loadLibrary = useCallback(async (id) => {
    try { const res = await getLibrary(id); console.log('[DEBUG] loadLibrary returned:', JSON.stringify(res.data).slice(0, 200)); setLibraryData(res.data); }
    catch (err) { console.error('[DEBUG] Failed to load library:', err); }
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => { try { if (!cancelled) { const res = await listBrainstorms(); setBrainstorms(res.data); } } catch (err) { console.error(err); } })();
    return () => { cancelled = true; };
  }, [reloadKey]);

  // ─── Load brainstorm data on selection ────────────────────────
  useEffect(() => {
    if (activeBrainstorm) {
      let cancelled = false;
      (async () => {
        try {
          const [messagesRes, mapRes, libraryRes] = await Promise.all([
            getMessages(activeBrainstorm.id), getMap(activeBrainstorm.id), getLibrary(activeBrainstorm.id),
          ]);
          if (cancelled) return;
          console.log('[DEBUG] Loaded brainstorm data — map topics:', mapRes.data?.topics?.length, 'library folders:', libraryRes.data?.length);
          setMessages(messagesRes.data); setMapData(mapRes.data); setLibraryData(libraryRes.data);
        } catch (err) { console.error('[DEBUG] Load brainstorm data error:', err); }
      })();
      return () => { cancelled = true; };
    }
  }, [activeBrainstorm]);

  // ─── WebSocket: live updates after async classification ───────
  useEffect(() => {
    const ws = wsRef.current;
    if (!activeBrainstorm) {
      if (ws) { ws.close(); wsRef.current = null; }
      return;
    }
    // Close any previous connection before opening a new one
    if (ws) ws.close();

    const socket = new WebSocket(buildBrainstormWebSocketUrl(activeBrainstorm.id));
    wsRef.current = socket;

    socket.onmessage = (event) => {
      console.log('[DEBUG] WebSocket message received:', event.data.slice(0, 500));
      try {
        const msg = JSON.parse(event.data);
        if (msg.event === 'classification_complete' || msg.event === 'classification_error') {
          console.log('[DEBUG] Classification event:', msg.event, '- reloading map + library');
          if (msg.event === 'classification_error') {
            console.error('[DEBUG] Classification error data:', msg.data);
          }
          // Reload map + library after Celery finishes
          loadMap(activeBrainstorm.id);
          loadLibrary(activeBrainstorm.id);
          loadBrainstorms();
          // Clear the exploring indicator now that classification completed (or errored)
          setExploringTopic(null);
          setHasClassified(true);

        }
      } catch (err) {
        console.log('[DEBUG] WebSocket message parse error:', err.message);
      }
    };

    socket.onclose = (e) => {
      console.log('[DEBUG] WebSocket closed. code:', e.code, 'reason:', e.reason);
      if (wsRef.current === socket) wsRef.current = null;
    };

    socket.onerror = (err) => {
      console.log('[DEBUG] WebSocket error:', err);
    };

    socket.onopen = () => {
      console.log('[DEBUG] WebSocket connected for brainstorm:', activeBrainstorm.id);
    };

    return () => {
      socket.close();
      if (wsRef.current === socket) wsRef.current = null;
    };
  }, [activeBrainstorm, loadMap, loadLibrary, loadBrainstorms]);

  const handleNewBrainstorm = useCallback(() => {
    if (streamAbortRef.current) {
      streamAbortRef.current.abort();
      streamAbortRef.current = null;
    }
    setSending(false);
    setSelectedTopic(null);
    setActiveBrainstorm(null);
    setMessages([]);
    setMapData({ topics: [], edges: [], suggestions: [] });
    setLibraryData([]);
    setChatError('');
    setExploringTopic(null);
    setHasClassified(false);
    setActiveTab('map');
  }, []);

  const handleSelectBrainstorm = useCallback(async (brainstorm) => {
    // Abort any in-flight stream before switching
    if (streamAbortRef.current) {
      streamAbortRef.current.abort();
      streamAbortRef.current = null;
    }
    setSending(false);
    const full = await loadBrainstormDetails(brainstorm.id);
    if (!full) return;
    setActiveBrainstorm(full); setActiveTab('map');
    setMessages([]); setMapData({ topics: [], edges: [], suggestions: [] }); setLibraryData([]); setChatError('');
  }, [loadBrainstormDetails]);

  const clearBrainstormState = useCallback(() => {
    setActiveBrainstorm(null);
    setMessages([]);
    setMapData({ topics: [], edges: [], suggestions: [] });
    setLibraryData([]);
    setChatError('');
    setActiveTab('map');
  }, []);

  const handleRequestDelete = (b) => setDeleteTarget(b);
  const handleCancelDelete = () => { if (!deleting) setDeleteTarget(null); };

  const handleConfirmDelete = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      const id = deleteTarget.id; await deleteBrainstorm(id);
      const next = await loadBrainstorms(); const wasActive = activeBrainstorm?.id === id;
      setDeleteTarget(null);
      if (wasActive) {
        if (next.length > 0) await handleSelectBrainstorm(next[0]);
        else clearBrainstormState();
      }
    } catch (err) {
      if (err?.response?.status === 404) {
        const next = await loadBrainstorms();
        const wasActive = activeBrainstorm?.id === deleteTarget.id;
        setDeleteTarget(null);
        if (wasActive) {
          if (next.length > 0) await handleSelectBrainstorm(next[0]);
          else clearBrainstormState();
        }
      } else {
        console.error(err);
      }
    }
    finally { setDeleting(false); }
  };

  const submitBrainstormMessage = useCallback(async (content) => {
    const brainstorm = activeBrainstormRef.current;
    console.log('[DEBUG] submitBrainstormMessage called, content:', content.slice(0, 60), 'brainstorm:', !!brainstorm, 'sending:', sendingRef.current);
    if (!brainstorm || sendingRef.current) return;
    sendingRef.current = true;
    setSending(true);
    setChatError('');

    const userMsgId = Date.now().toString();
    const thinkingMessageId = `thinking-${userMsgId}`;
    const userMsg = { id: userMsgId, brainstorm_id: brainstorm.id, role: 'user', content, created_at: new Date().toISOString() };

    // Show user message + thinking placeholder immediately
    setMessages(p => [...p, userMsg]);
    setMessages(p => [...p, { id: thinkingMessageId, brainstorm_id: brainstorm.id, role: 'assistant', content: '', isThinking: true, isStreaming: true, created_at: new Date().toISOString() }]);

    let streamedContent = '';
    let firstToken = true;

    const controller = streamMessage(
      { brainstorm_id: brainstorm.id, message: content },
      {
        onToken: (token) => {
          streamedContent += token;
          setMessages(p => p.map(msg => {
            if (msg.id === thinkingMessageId) {
              return { ...msg, content: streamedContent, isThinking: firstToken };
            }
            return msg;
          }));
          firstToken = false;
        },
        onDone: () => {
          setMessages(p => p.map(msg => {
            if (msg.id === thinkingMessageId) {
              return { ...msg, isThinking: false, isStreaming: false };
            }
            return msg;
          }));
          setSending(false);
          sendingRef.current = false;
          streamAbortRef.current = null;
          loadBrainstorms();
        },
        onError: (error) => {
          setMessages(p => p.filter(msg => msg.id !== thinkingMessageId));
          setChatError(error);
          setSending(false);
          sendingRef.current = false;
          streamAbortRef.current = null;
        },
      }
    );

    streamAbortRef.current = controller;
  }, [loadBrainstorms]);

  const handleSendMessage = useCallback((content) => {
    void submitBrainstormMessage(content);
  }, [submitBrainstormMessage]);

  const handleSuggestionClick = useCallback((topicName) => {
    console.log('[DEBUG] handleSuggestionClick called with:', topicName);
    // Show immediate feedback on the map that we're exploring this topic
    setExploringTopic(topicName);
    // Phrase it like a prompt so the backend promotes the existing proposition
    // instead of creating a brand-new topic from a generic classification pass.
    void submitBrainstormMessage(`Tell me about ${topicName}`);
  }, [submitBrainstormMessage]);

  // Abort any in-flight stream on unmount
  useEffect(() => {
    return () => {
      if (streamAbortRef.current) {
        streamAbortRef.current.abort();
        streamAbortRef.current = null;
      }
    };
  }, []);

  const handleModelChange = useCallback(async (model) => {
    if (!activeBrainstorm) return;
    try {
      await updateBrainstormModel(activeBrainstorm.id, model);
      // Reload brainstorm to update the model chip
      const updated = await loadBrainstormDetails(activeBrainstorm.id);
      if (updated) setActiveBrainstorm(updated);
    } catch (err) {
      console.error('Failed to update model:', err);
    }
  }, [activeBrainstorm, loadBrainstormDetails]);

  const handleRefreshMap = async () => {
    if (!activeBrainstorm) return;
    try { const res = await refreshMap(activeBrainstorm.id); setMapData(res.data); }
    catch (err) { console.error(err); }
  };

  const handleTopicClick = useCallback((topic) => {
    setSelectedTopic(topic);
  }, []);

  const handleCloseTopicPanel = useCallback(() => {
    setSelectedTopic(null);
  }, []);

  const handleUpdateTopic = useCallback(async (topicId, data) => {
    if (!activeBrainstorm) return;
    await updateTopic(activeBrainstorm.id, topicId, data);
    const mapRes = await getMap(activeBrainstorm.id);
    setMapData(mapRes.data);
    const fresh = mapRes.data?.topics?.find(t => t.id === topicId);
    if (fresh) setSelectedTopic(fresh);
  }, [activeBrainstorm]);

  const handleDeleteTopic = useCallback(async (topicId) => {
    if (!activeBrainstorm) return;
    await deleteTopic(activeBrainstorm.id, topicId);
    setSelectedTopic(null);
    await loadMap(activeBrainstorm.id);
    await loadLibrary(activeBrainstorm.id);
  }, [activeBrainstorm, loadMap, loadLibrary]);

  const handleExploreTopic = useCallback(async (topicId) => {
    if (!activeBrainstorm) return;
    const res = await exploreTopic(activeBrainstorm.id, topicId);
    setMapData(res.data);
    await loadLibrary(activeBrainstorm.id);
  }, [activeBrainstorm, loadLibrary]);

  const handleSwitchToLibrary = useCallback(() => {
    setActiveTab('library');
  }, []);

  const handleStartNewBrainstorm = useCallback(async (topic) => {
    console.log('[DEBUG] handleStartNewBrainstorm called with topic:', topic);
    try {
      const res = await createBrainstorm({ title: topic });
      console.log('[DEBUG] createBrainstorm response:', JSON.stringify(res.data));
      setActiveBrainstorm(res.data);
      setMessages([]);
      setMapData({ topics: [], edges: [], suggestions: [] });
      setLibraryData([]);
      setChatError('');
      setActiveTab('map');
      await loadBrainstorms();
      // Use streaming — the topic message gets the same real-time treatment
      submitBrainstormMessage(topic);
    } catch (err) {
      console.error('Failed to start brainstorm:', err);
    }
  }, [loadBrainstorms, submitBrainstormMessage]);

  const handleUpdateLibraryEntry = async (entryId, content) => {
    try { await updateLibraryEntry(entryId, content); await loadLibrary(activeBrainstorm.id); }
    catch (err) { console.error(err); }
  };

  const handleDeleteLibraryEntry = async (entryId) => {
    try { await deleteLibraryEntry(entryId); await loadLibrary(activeBrainstorm.id); }
    catch (err) { console.error(err); }
  };

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
          onDelete={handleRequestDelete}
          mode={mode}
          onToggleTheme={toggleTheme}
          collapsed={sidebarCollapsed}
          onToggleCollapse={toggleSidebar}
          onRenameComplete={() => setReloadKey(k => k + 1)}
        />
        <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0, position: 'relative', zIndex: 1 }}>
          <Box sx={{ display: 'flex', flex: 1, minHeight: 0 }}>
            <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
              <ChatWindow
                activeBrainstorm={activeBrainstorm}
                mapData={mapData} libraryData={libraryData}
                activeTab={activeTab} onTabChange={setActiveTab}
                onRefreshMap={handleRefreshMap}
                onUpdateLibraryEntry={handleUpdateLibraryEntry}
                onDeleteLibraryEntry={handleDeleteLibraryEntry}
                onStartNewBrainstorm={handleStartNewBrainstorm}
                onSuggestionClick={handleSuggestionClick}
                onTopicClick={handleTopicClick}
                selectedTopic={selectedTopic}
                exploringTopic={exploringTopic}
                hasClassified={hasClassified}
                themeId={themeId} onThemeChange={handleThemeChange}
                onModelChange={handleModelChange}
              />
            </Box>
            {selectedTopic && (
              <TopicDetailPanel
                topic={selectedTopic}
                mapData={mapData}
                libraryData={libraryData}
                onClose={handleCloseTopicPanel}
                onUpdate={handleUpdateTopic}
                onDelete={handleDeleteTopic}
                onExplore={handleExploreTopic}
                onSwitchToLibrary={handleSwitchToLibrary}
              />
            )}
          </Box>
        </Box>
      </Box>

      {/* ── Delete Dialog ────────────────────────────────── */}
      <Dialog open={Boolean(deleteTarget)} onClose={handleCancelDelete} maxWidth="xs">
        <DialogTitle sx={{ fontWeight: 700, fontSize: '1.1rem', pb: 0.5 }}>Delete brainstorm?</DialogTitle>
        <DialogContent sx={{ pb: 1 }}>
          <DialogContentText sx={(theme) => ({ color: alpha(theme.palette.text.primary, 0.6), fontSize: '0.875rem', lineHeight: 1.6 })}>
            {deleteTarget
              ? `This will permanently delete "${deleteTarget.title}", including its messages, knowledge map, and library entries.`
              : 'This will permanently delete the selected brainstorm.'}
          </DialogContentText>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2.5, gap: 1 }}>
          <Button onClick={handleCancelDelete} disabled={deleting}
            sx={(theme) => ({ color: alpha(theme.palette.text.primary, 0.6), textTransform: 'none', fontWeight: 600, borderRadius: 2, px: 2.5, py: 1, fontSize: '0.85rem', '&:hover': { bgcolor: alpha(theme.palette.action.hover, 0.5), color: theme.palette.text.primary } })}>
            Cancel
          </Button>
          <Button onClick={handleConfirmDelete} disabled={deleting} variant="contained" color="error"
            sx={{ borderRadius: 1, textTransform: 'none', fontWeight: 700, px: 2.5, py: 1, fontSize: '0.85rem', boxShadow: (theme) => `0 4px 16px ${alpha(theme.palette.error.main, 0.35)}`, '&:hover': { boxShadow: (theme) => `0 6px 24px ${alpha(theme.palette.error.main, 0.5)}` } }}>
            {deleting ? 'Deleting...' : 'Delete'}
          </Button>
        </DialogActions>
      </Dialog>

    </ThemeProvider>
  );
}

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
