import { useState, lazy, Suspense } from 'react';
import {
  ThemeProvider, CssBaseline, Box,
  Dialog, DialogActions, DialogContent, DialogContentText, DialogTitle,
  Button, alpha, CircularProgress,
} from '@mui/material';
import { createAppTheme } from './theme';
import { useAuth } from './auth/AuthContext';
import LoginDialog from './auth/LoginDialog';
import RegisterDialog from './auth/RegisterDialog';
import Sidebar from './components/Sidebar';
import ChatWindow from './components/ChatWindow';
import useMapStore from './stores/mapStore';
import { useAppOrchestrator } from './hooks/useAppOrchestrator';

const SharedView = lazy(() => import('./features/share/SharedView'));
const LandingPage = lazy(() => import('./features/landing'));

const TopicDetailPanel = lazy(() => import('./features/canvas/TopicDetailPanel'));
const SearchDialog = lazy(() => import('./features/search/SearchDialog'));

// ─── AppContent — main application shell ─────────────────

function AppContent() {
  const {
    searchOpen, setSearchOpen,
    theme,
    mode, themeId, sidebarCollapsed, activeTab,
    brainstorms, activeBrainstorm,
    deleteTarget, deleting,
    handleNewBrainstorm, handleSelectBrainstorm,
    toggleTheme, handleThemeChange,
    handleStartNewBrainstorm, handleModelChange,
    requestDelete, cancelDelete, confirmDelete,
    toggleSidebar, setActiveTab, reloadList,
  } = useAppOrchestrator();

  const selectedTopic = useMapStore(s => s.selectedTopic);

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Box sx={{ display: 'flex', height: '100vh', overflow: 'hidden', bgcolor: 'background.default', position: 'relative' }}>
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
          onRenameComplete={reloadList}
          themeId={themeId}
          onThemeChange={handleThemeChange}
          onModelChange={handleModelChange}
        />
        <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0, position: 'relative', zIndex: 1 }}>
          <Box sx={{ display: 'flex', flex: 1, minHeight: 0 }}>
            <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
              <ChatWindow
                activeBrainstorm={activeBrainstorm}
                activeTab={activeTab}
                onTabChange={setActiveTab}
                onStartNewBrainstorm={handleStartNewBrainstorm}
              />
            </Box>
            {selectedTopic && (
              <Suspense fallback={null}>
                <TopicDetailPanel />
              </Suspense>
            )}
          </Box>
        </Box>
      </Box>

      {searchOpen && (
        <Suspense fallback={null}>
          <SearchDialog open={searchOpen} onClose={() => setSearchOpen(false)} />
        </Suspense>
      )}

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

// ─── AuthGate — landing page for unauthenticated, app for authenticated ──

function AuthGate() {
  const { token, loading } = useAuth();
  const [authView, setAuthView] = useState(null);

  if (loading) {
    return (
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', bgcolor: 'background.default' }}>
        <CircularProgress size={32} />
      </Box>
    );
  }

  if (token) return <AppContent />;

  return (
    <>
      <Suspense fallback={
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', bgcolor: '#1A1512' }}>
          <CircularProgress size={32} sx={{ color: '#CA6F4E' }} />
        </Box>
      }>
        <LandingPage
          onGetStarted={() => setAuthView('register')}
          onSignIn={() => setAuthView('login')}
        />
      </Suspense>
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
    </>
  );
}

function App() {
  // ── Shared view route — public, no auth required ──────
  if (window.location.pathname.startsWith('/shared/')) {
    return (
      <Suspense fallback={
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', bgcolor: 'background.default' }}>
          <CircularProgress size={32} />
        </Box>
      }>
        <SharedView />
      </Suspense>
    );
  }
  return <AuthGate />;
}

export default App;
