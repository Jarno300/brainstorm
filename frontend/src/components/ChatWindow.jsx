import { useState, lazy, Suspense } from 'react';
import { Box, Tabs, Tab, Typography, Chip, alpha, CircularProgress, IconButton, TextField, Button, InputAdornment } from '@mui/material';
import { Hub as MapIcon, LibraryBooks as LibraryIcon, Share as ShareIcon, AutoAwesome as SparkleIcon, ArrowForward as ArrowIcon } from '@mui/icons-material';
import ErrorBoundary from './ErrorBoundary';
import ThemeSwitcher from './ThemeSwitcher';
import ModelSwitcher from './ModelSwitcher';
import AddModelModal from './AddModelModal';
import ShareDialog from './ShareDialog';
import LibraryTab from './LibraryTab';

const MapTab = lazy(() => import('./MapTab'));

function ChatWindow({ activeBrainstorm, mapData, libraryData, activeTab, onTabChange, onRefreshMap, onUpdateLibraryEntry, onSuggestionClick, themeId, onThemeChange, onModelChange, onStartNewBrainstorm }) {
    const [addModelOpen, setAddModelOpen] = useState(false);
    const [shareOpen, setShareOpen] = useState(false);
    const [refreshModels, setRefreshModels] = useState(null);
    const [topicInput, setTopicInput] = useState('');

    const handleAddModel = (refreshCallback) => {
        setRefreshModels(() => refreshCallback);
        setAddModelOpen(true);
    };

    const handleModelSaved = () => {
        if (refreshModels) refreshModels();
    };

    return (
        <Box sx={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
            {/* ── Header ──────────────────────────────────────────── */}
            <Box sx={(theme) => ({
                px: 3, py: 1.75,
                borderBottom: '1px solid', borderColor: alpha(theme.palette.divider, 0.5),
                bgcolor: alpha(theme.palette.background.default, 0.6),
                backdropFilter: 'blur(12px)',
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                position: 'relative',
                '&::after': {
                    content: '""', position: 'absolute', bottom: 0, left: '5%', right: '5%',
                    height: '1px',
                    background: `linear-gradient(90deg, transparent, ${alpha(theme.palette.primary.main, 0.12)}, transparent)`,
                },
            })}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, minWidth: 0 }}>
                    <Typography sx={{
                        fontWeight: 700, fontSize: '1rem', color: 'text.primary',
                        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                    }}>
                        {activeBrainstorm ? activeBrainstorm.title : 'Brainstorm'}
                    </Typography>
                    {activeBrainstorm && (
                        <Chip label={activeBrainstorm.model} size="small"
                            sx={(theme) => ({
                                height: 22, fontSize: '0.625rem', fontWeight: 700, borderRadius: '6px',
                                bgcolor: alpha(theme.palette.primary.main, 0.12),
                                color: theme.palette.primary.light,
                                border: '1px solid', borderColor: alpha(theme.palette.primary.main, 0.15),
                                '& .MuiChip-label': { px: 1 },
                            })} />
                    )}
                </Box>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                    {activeBrainstorm && (
                        <IconButton
                            size="small"
                            onClick={() => setShareOpen(true)}
                            sx={(t) => ({
                                width: 30, height: 30, borderRadius: 1,
                                border: '1px solid', borderColor: alpha(t.palette.divider, 0.6),
                                color: alpha(t.palette.text.secondary, 0.55),
                                transition: 'all 0.2s ease',
                                '&:hover': {
                                    bgcolor: alpha(t.palette.primary.main, 0.08),
                                    color: t.palette.primary.light,
                                    borderColor: alpha(t.palette.primary.main, 0.15),
                                },
                            })}
                        >
                            <ShareIcon sx={{ fontSize: 15 }} />
                        </IconButton>
                    )}
                    <ModelSwitcher
                        currentModel={activeBrainstorm?.model || ''}
                        onModelChange={onModelChange}
                        onAddModel={handleAddModel}
                    />
                    <ThemeSwitcher themeId={themeId} onThemeChange={onThemeChange} />
                </Box>
            </Box>

            {activeBrainstorm && (
                <>
                    {/* ── Tabs ────────────────────────────────────────────── */}
                    <Box sx={(theme) => ({
                        borderBottom: '1px solid', borderColor: alpha(theme.palette.divider, 0.5),
                        bgcolor: alpha(theme.palette.background.default, 0.3),
                    })}>
                        <Tabs value={activeTab} onChange={(e, v) => onTabChange(v)}
                            sx={(theme) => ({
                                minHeight: 40, px: 1,
                                '& .MuiTab-root': {
                                    minHeight: 40, py: 0.5, px: 2,
                                    fontSize: '0.8rem',
                                    color: alpha(theme.palette.text.secondary, 0.6),
                                    transition: 'all 0.2s ease',
                                },
                            })}>
                            <Tab icon={<MapIcon sx={{ fontSize: 15, mr: 0.5 }} />} iconPosition="start" label="Map" value="map" />
                            <Tab icon={<LibraryIcon sx={{ fontSize: 15, mr: 0.5 }} />} iconPosition="start" label="Library" value="library" />
                        </Tabs>
                    </Box>
                </>
            )}

            {/* ── Content ──────────────────────────────────────────── */}
            <Box sx={{ flex: 1, overflow: 'hidden', position: 'relative' }}>
                {!activeBrainstorm ? (
                    <Box sx={{
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        height: '100%', flexDirection: 'column', gap: 3, px: 4,
                    }}>
                        {/* ── Brand ────────────────────────────── */}
                        <Box sx={{ textAlign: 'center', mb: 1 }}>
                            <Box sx={(theme) => ({
                                display: 'inline-flex', alignItems: 'center', gap: 1,
                                px: 2.5, py: 1,
                                borderRadius: 2,
                                bgcolor: alpha(theme.palette.primary.main, 0.08),
                                border: '1px solid', borderColor: alpha(theme.palette.primary.main, 0.1),
                                mb: 2,
                            })}>
                                <SparkleIcon sx={(theme) => ({ fontSize: 18, color: theme.palette.primary.light })} />
                                <Typography sx={(theme) => ({
                                    fontWeight: 700, fontSize: '0.85rem',
                                    background: theme.palette.gradients.brand,
                                    WebkitBackgroundClip: 'text',
                                    WebkitTextFillColor: 'transparent',
                                })}>
                                    Brainstorm
                                </Typography>
                            </Box>
                            <Typography sx={(theme) => ({
                                fontWeight: 800, fontSize: { xs: '1.75rem', md: '2.25rem' },
                                color: theme.palette.text.primary,
                                letterSpacing: '-0.03em',
                                lineHeight: 1.2,
                                mb: 1,
                            })}>
                                What do you want to explore?
                            </Typography>
                            <Typography variant="body1" sx={(theme) => ({
                                color: alpha(theme.palette.text.secondary, 0.6),
                                fontSize: '0.95rem',
                                maxWidth: 420, mx: 'auto',
                                lineHeight: 1.6,
                            })}>
                                Enter a topic and instantly build a knowledge map and library.
                            </Typography>
                        </Box>

                        {/* ── Topic Input ──────────────────────── */}
                        <Box sx={{ width: '100%', maxWidth: 520, mx: 'auto' }}>
                            <TextField
                                fullWidth
                                size="medium"
                                placeholder="e.g. Quantum computing, Renaissance art, Dark matter..."
                                value={topicInput}
                                onChange={(e) => setTopicInput(e.target.value)}
                                onKeyDown={(e) => {
                                    if (e.key === 'Enter' && topicInput.trim()) {
                                        onStartNewBrainstorm?.(topicInput.trim());
                                        setTopicInput('');
                                    }
                                }}
                                variant="outlined"
                                slotProps={{
                                    input: {
                                        sx: (theme) => ({
                                            borderRadius: 2,
                                            fontSize: '1rem',
                                            bgcolor: alpha(theme.palette.background.paper, 0.5),
                                            border: '1.5px solid',
                                            borderColor: alpha(theme.palette.divider, 0.5),
                                            transition: 'all 0.2s ease',
                                            '&:hover': {
                                                borderColor: alpha(theme.palette.primary.main, 0.3),
                                            },
                                            '&.Mui-focused': {
                                                borderColor: theme.palette.primary.main,
                                                boxShadow: `0 0 0 3px ${alpha(theme.palette.primary.main, 0.12)}`,
                                            },
                                            '& fieldset': { border: 'none' },
                                            '& input': {
                                                padding: '14px 18px !important',
                                                '&::placeholder': {
                                                    color: alpha(theme.palette.text.secondary, 0.4),
                                                    opacity: 1,
                                                },
                                            },
                                        }),
                                        endAdornment: (
                                            <InputAdornment position="end" sx={{ mr: 0.5 }}>
                                                <Button
                                                    variant="contained"
                                                    disabled={!topicInput.trim()}
                                                    onClick={() => {
                                                        onStartNewBrainstorm?.(topicInput.trim());
                                                        setTopicInput('');
                                                    }}
                                                    endIcon={<ArrowIcon sx={{ fontSize: 16 }} />}
                                                    sx={(theme) => ({
                                                        borderRadius: 1.5,
                                                        textTransform: 'none',
                                                        fontWeight: 600,
                                                        fontSize: '0.85rem',
                                                        py: 0.75, px: 2,
                                                        background: theme.palette.gradients.primary,
                                                        boxShadow: `0 2px 8px ${alpha(theme.palette.primary.main, 0.28)}`,
                                                        '&:hover': {
                                                            background: theme.palette.gradients.primaryHover,
                                                            boxShadow: `0 4px 14px ${alpha(theme.palette.primary.main, 0.4)}`,
                                                        },
                                                        '&.Mui-disabled': {
                                                            background: alpha(theme.palette.action.disabled, 0.1),
                                                        },
                                                    })}
                                                >
                                                    Explore
                                                </Button>
                                            </InputAdornment>
                                        ),
                                    },
                                }}
                            />
                        </Box>

                        {/* ── Example Topics ─────────────────────── */}
                        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, justifyContent: 'center', maxWidth: 480 }}>
                            {['Renaissance art', 'Quantum computing', 'The Roman Empire', 'Climate change', 'Machine learning'].map((topic) => (
                                <Chip
                                    key={topic}
                                    label={topic}
                                    size="small"
                                    clickable
                                    onClick={() => {
                                        onStartNewBrainstorm?.(topic);
                                        setTopicInput('');
                                    }}
                                    sx={(theme) => ({
                                        borderRadius: 1.5,
                                        fontSize: '0.75rem',
                                        fontWeight: 500,
                                        bgcolor: alpha(theme.palette.action.hover, 0.4),
                                        color: alpha(theme.palette.text.secondary, 0.7),
                                        border: '1px solid',
                                        borderColor: alpha(theme.palette.divider, 0.4),
                                        transition: 'all 0.15s ease',
                                        '&:hover': {
                                            bgcolor: alpha(theme.palette.primary.main, 0.12),
                                            color: theme.palette.primary.light,
                                            borderColor: alpha(theme.palette.primary.main, 0.2),
                                        },
                                    })}
                                />
                            ))}
                        </Box>
                    </Box>
                ) : (
                    <>
                            {activeTab === 'map' && (
                            <ErrorBoundary fallbackTitle="Map unavailable" fallbackMessage="An error occurred loading the knowledge map. Try refreshing the map.">
                                <Suspense fallback={
                                    <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
                                        <CircularProgress size={32} sx={(t) => ({ color: t.palette.primary.light })} />
                                    </Box>
                                }>
                                    <MapTab mapData={mapData} onRefresh={onRefreshMap} onSuggestionClick={onSuggestionClick} brainstormTitle={activeBrainstorm?.title} />
                                </Suspense>
                            </ErrorBoundary>
                        )}
                        {activeTab === 'library' && (
                            <ErrorBoundary fallbackTitle="Library unavailable" fallbackMessage="An error occurred loading the library. Please try again.">
                                <LibraryTab libraryData={libraryData} onUpdateEntry={onUpdateLibraryEntry} brainstormId={activeBrainstorm?.id} />
                            </ErrorBoundary>
                        )}
                    </>
                )}
            </Box>

            {/* ── Add Model Modal ─────────────────────────────── */}
            <AddModelModal
                open={addModelOpen}
                onClose={() => setAddModelOpen(false)}
                onSaved={handleModelSaved}
            />

            {/* ── Share Dialog ───────────────────────────────── */}
            <ShareDialog
                open={shareOpen}
                onClose={() => setShareOpen(false)}
                brainstormId={activeBrainstorm?.id}
            />
        </Box>
    );
}

export default ChatWindow;
