import { useState, lazy, Suspense } from 'react';
import { Box, Tabs, Tab, Typography, Chip, alpha, CircularProgress, TextField, Button, InputAdornment } from '@mui/material';
import { Map as MapIcon, LibraryBooks as LibraryIcon, AutoAwesome as SparkleIcon, ArrowForward as ArrowIcon, School as SchoolIcon } from '@mui/icons-material';
import ErrorBoundary from './ErrorBoundary';

const CanvasTab = lazy(() => import('../features/canvas/CanvasTab'));
const LibraryTab = lazy(() => import('../features/library/LibraryTab'));
const FlashcardTab = lazy(() => import('../features/flashcards/FlashcardTab'));

function ChatWindow({ activeBrainstorm, activeTab, onTabChange, onStartNewBrainstorm }) {
    const [topicInput, setTopicInput] = useState('');

    return (
        <Box sx={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
            {activeBrainstorm && (
                <Box sx={(theme) => ({
                    bgcolor: alpha(theme.palette.background.default, 0.3),
                    borderBottom: '1px solid',
                    borderColor: alpha(theme.palette.divider, 0.08),
                })}>
                    <Tabs value={activeTab} onChange={(e, v) => onTabChange(v)}
                        sx={(theme) => ({
                            minHeight: 40, px: 1,
                            '& .MuiTab-root': { minHeight: 40, py: 0.5, px: 2, fontSize: '0.8rem', color: alpha(theme.palette.text.secondary, 0.6), transition: 'all 0.2s ease' },
                        })}>
                        <Tab icon={<MapIcon sx={{ fontSize: 15, mr: 0.5 }} />} iconPosition="start" label="Map" value="map" />
                        <Tab icon={<LibraryIcon sx={{ fontSize: 15, mr: 0.5 }} />} iconPosition="start" label="Library" value="library" />
                        <Tab icon={<SchoolIcon sx={{ fontSize: 15, mr: 0.5 }} />} iconPosition="start" label="Flashcards" value="flashcards" />
                    </Tabs>
                </Box>
            )}

            <Box sx={{ flex: 1, overflow: 'hidden', position: 'relative' }}>
                {!activeBrainstorm ? (
                    <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', flexDirection: 'column', gap: 3, px: 4 }}>
                        <Box sx={{ textAlign: 'center', mb: 1 }}>
                            <Box sx={(theme) => ({ display: 'inline-flex', alignItems: 'center', gap: 1.5, px: 3, py: 1.25, borderRadius: 3, bgcolor: alpha(theme.palette.primary.main, 0.1), border: '1px solid', borderColor: alpha(theme.palette.primary.main, 0.15), mb: 3, '@keyframes badgeShimmer': { '0%, 100%': { boxShadow: `0 0 0 0 ${alpha(theme.palette.primary.main, 0)}` }, '50%': { boxShadow: `0 0 24px 2px ${alpha(theme.palette.primary.main, 0.08)}` } }, animation: 'badgeShimmer 4s ease-in-out infinite' })}>
                                <SparkleIcon sx={(theme) => ({ fontSize: 22, color: theme.palette.primary.light })} />
                                <Typography sx={(theme) => ({ fontWeight: 800, fontSize: '1rem', background: theme.palette.gradients.brand, WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', letterSpacing: '-0.02em' })}>Brainstorm</Typography>
                            </Box>
                            <Typography sx={(theme) => ({ fontWeight: 800, fontSize: { xs: '1.75rem', md: '2.5rem' }, color: theme.palette.text.primary, letterSpacing: '-0.04em', lineHeight: 1.1, mb: 1.5, textShadow: theme.palette.mode === 'dark' ? `0 0 80px ${alpha(theme.palette.primary.main, 0.2)}` : 'none' })}>What do you want to explore?</Typography>
                            <Typography variant="body1" sx={(theme) => ({ color: alpha(theme.palette.text.secondary, 0.6), fontSize: '0.95rem', maxWidth: 420, mx: 'auto', lineHeight: 1.6 })}>Enter a topic and instantly build a knowledge map and library.</Typography>
                        </Box>
                        <Box sx={{ width: '100%', maxWidth: 520, mx: 'auto' }}>
                            <TextField fullWidth size="medium" placeholder="e.g. Quantum computing, Renaissance art, Dark matter..."
                                value={topicInput} onChange={(e) => setTopicInput(e.target.value)}
                                onKeyDown={(e) => { if (e.key === 'Enter' && topicInput.trim()) { onStartNewBrainstorm?.(topicInput.trim()); setTopicInput(''); } }}
                                variant="outlined"
                                slotProps={{ input: { sx: (theme) => ({ borderRadius: 2, fontSize: '1rem', bgcolor: alpha(theme.palette.background.paper, 0.5), transition: 'all 0.2s ease', '&:hover': { borderColor: alpha(theme.palette.primary.main, 0.3) }, '&.Mui-focused': { borderColor: theme.palette.primary.main, boxShadow: `0 0 0 3px ${alpha(theme.palette.primary.main, 0.12)}` }, '& fieldset': { border: 'none' }, '& input': { padding: '14px 18px !important', '&::placeholder': { color: alpha(theme.palette.text.secondary, 0.4), opacity: 1 } } }), endAdornment: (
                                    <InputAdornment position="end" sx={{ mr: 0.5 }}>
                                        <Button variant="contained" disabled={!topicInput.trim()} onClick={() => { onStartNewBrainstorm?.(topicInput.trim()); setTopicInput(''); }} endIcon={<ArrowIcon sx={{ fontSize: 16 }} />}
                                            sx={(theme) => ({ borderRadius: 1.5, textTransform: 'none', fontWeight: 600, fontSize: '0.85rem', py: 0.75, px: 2, background: theme.palette.gradients.primary, boxShadow: `0 2px 8px ${alpha(theme.palette.primary.main, 0.28)}`, '&:hover': { background: theme.palette.gradients.primaryHover, boxShadow: `0 4px 14px ${alpha(theme.palette.primary.main, 0.4)}` }, '&.Mui-disabled': { background: alpha(theme.palette.action.disabled, 0.1) } })}>Explore</Button>
                                    </InputAdornment>
                                ) } }}
                            />
                        </Box>
                        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, justifyContent: 'center', maxWidth: 480 }}>
                            {['Renaissance art', 'Quantum computing', 'The Roman Empire', 'Climate change', 'Machine learning'].map((topic) => (
                                <Chip key={topic} label={topic} size="small" clickable onClick={() => { onStartNewBrainstorm?.(topic); setTopicInput(''); }}
                                    sx={(theme) => ({ borderRadius: 1.5, fontSize: '0.75rem', fontWeight: 500, bgcolor: alpha(theme.palette.action.hover, 0.4), color: alpha(theme.palette.text.secondary, 0.7), transition: 'all 0.15s ease', '&:hover': { bgcolor: alpha(theme.palette.primary.main, 0.12), color: theme.palette.primary.light, borderColor: alpha(theme.palette.primary.main, 0.2) } })}
                                />
                            ))}
                        </Box>
                    </Box>
                ) : (
                    <>
                        {activeTab === 'map' && (
                            <ErrorBoundary fallbackTitle="Map unavailable" fallbackMessage="An error occurred loading the knowledge map. Try refreshing the map.">
                                <Suspense fallback={<Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}><CircularProgress size={32} sx={(t) => ({ color: t.palette.primary.light })} /></Box>}>
                                    <CanvasTab brainstormingId={activeBrainstorm?.id} />
                                </Suspense>
                            </ErrorBoundary>
                        )}
                        {activeTab === 'library' && (
                            <ErrorBoundary fallbackTitle="Library unavailable" fallbackMessage="An error occurred loading the library. Please try again.">
                                <Suspense fallback={<Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}><CircularProgress size={32} sx={(t) => ({ color: t.palette.primary.light })} /></Box>}>
                                    <LibraryTab brainstormId={activeBrainstorm?.id} />
                                </Suspense>
                            </ErrorBoundary>
                        )}
                        {activeTab === 'flashcards' && (
                            <ErrorBoundary fallbackTitle="Flashcards unavailable" fallbackMessage="An error occurred loading flashcards. Please try again.">
                                <Suspense fallback={<Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}><CircularProgress size={32} sx={(t) => ({ color: t.palette.primary.light })} /></Box>}>
                                    <FlashcardTab brainstormId={activeBrainstorm?.id} />
                                </Suspense>
                            </ErrorBoundary>
                        )}
                    </>
                )}
            </Box>
        </Box>
    );
}

export default ChatWindow;
