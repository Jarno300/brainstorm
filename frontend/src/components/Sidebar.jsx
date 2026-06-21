import { useState, useRef, lazy, Suspense } from 'react';
import {
    Box,
    Typography,
    IconButton,
    Button,
    alpha,
    Chip,
    TextField,
    Tooltip,
} from '@mui/material';
import {
    Add as AddIcon,
    DarkMode as DarkModeIcon,
    LightMode as LightModeIcon,
    Psychology as BrainIcon,
    MenuOpen as CollapseIcon,
    ChevronRight as ExpandIcon,
    Search as SearchIcon,
    Share as ShareIcon,
} from '@mui/icons-material';
import ThemeSwitcher from '../features/settings/ThemeSwitcher';
import ModelSwitcher from '../features/settings/ModelSwitcher';
import BrainstormList from '../features/brainstorm/BrainstormList';
import useBrainstormStore from '../stores/brainstormStore';

const AddModelModal = lazy(() => import('../features/settings/AddModelModal'));
const ShareDialog = lazy(() => import('../features/share/ShareDialog'));

function Sidebar({ brainstorms, activeBrainstorm, onNew, onSelect, onDelete, mode, onToggleTheme, collapsed, onToggleCollapse, onRenameComplete, themeId, onThemeChange, onModelChange }) {
    const [editingId, setEditingId] = useState(null);
    const [editTitle, setEditTitle] = useState('');
    const [searchQuery, setSearchQuery] = useState('');
    const [addModelOpen, setAddModelOpen] = useState(false);
    const [shareOpen, setShareOpen] = useState(false);
    const [refreshModels, setRefreshModels] = useState(null);
    const editingRef = useRef(null);

    const filteredBrainstorms = brainstorms.filter((b) =>
        b.title.toLowerCase().includes(searchQuery.toLowerCase())
    );

    const handleStartRename = (e, brainstorm) => {
        e.stopPropagation();
        setEditingId(brainstorm.id);
        setEditTitle(brainstorm.title);
        setTimeout(() => editingRef.current?.focus(), 50);
    };

    const handleSaveRename = async () => {
        if (!editingId || !editTitle.trim()) {
            setEditingId(null);
            return;
        }
        try {
            await useBrainstormStore.getState().updateTitle(editingId, editTitle.trim());
            setEditingId(null);
            onRenameComplete?.();
        } catch (err) {
            console.error('Failed to rename:', err);
        }
        setEditingId(null);
    };

    const handleRenameKeyDown = (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            handleSaveRename();
        } else if (e.key === 'Escape') {
            setEditingId(null);
        }
    };

    if (collapsed) {
        return (
            <Box
                sx={(theme) => ({
                    width: 60,
                    minWidth: 60,
                    height: '100vh',
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    bgcolor: theme.palette.mode === 'dark' ? alpha(theme.palette.background.paper, 0.75) : alpha(theme.palette.background.paper, 0.4),
                    transition: 'all 0.2s ease',
                    position: 'relative',
                    zIndex: 10,
                    py: 2,
                    gap: 2,
                })}
            >
                <Box
                    sx={(theme) => ({
                        width: 34,
                        height: 34,
                        borderRadius: 2,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        background: theme.palette.gradients.primary,
                        boxShadow: `0 2px 8px ${alpha(theme.palette.primary.main, 0.35)}`,
                        flexShrink: 0,
                    })}
                >
                    <BrainIcon sx={{ color: '#fff', fontSize: 18 }} />
                </Box>
                <Tooltip title="New Brainstorm" arrow placement="right">
                    <IconButton
                        onClick={onNew}
                        size="small"
                        sx={(theme) => ({
                            width: 36,
                            height: 36,
                            borderRadius: 1.5,
                            bgcolor: alpha(theme.palette.primary.main, 0.15),
                            color: theme.palette.primary.light,
                            '&:hover': {
                                bgcolor: alpha(theme.palette.primary.main, 0.25),
                            },
                        })}
                    >
                        <AddIcon sx={{ fontSize: 18 }} />
                    </IconButton>
                </Tooltip>
                {/* ── Model chip (compact) ────────────────── */}
                {activeBrainstorm && (
                    <Chip
                        label={activeBrainstorm.model}
                        size="small"
                        sx={(theme) => ({
                            height: 20, fontSize: '0.55rem', fontWeight: 700, borderRadius: '6px',
                            bgcolor: alpha(theme.palette.primary.main, 0.12),
                            color: theme.palette.primary.light,
                            border: '1px solid', borderColor: alpha(theme.palette.primary.main, 0.15),
                            '& .MuiChip-label': { px: 0.75 },
                        })}
                    />
                )}
                <Tooltip title="Expand sidebar" arrow placement="right">
                    <IconButton
                        onClick={onToggleCollapse}
                        size="small"
                        sx={(theme) => ({
                            width: 28,
                            height: 28,
                            borderRadius: 1,
                            color: alpha(theme.palette.text.secondary, 0.55),
                            mt: 'auto',
                            '&:hover': {
                                color: theme.palette.text.primary,
                                bgcolor: alpha(theme.palette.action.hover, 0.4),
                            },
                        })}
                    >
                        <ExpandIcon sx={{ fontSize: 16 }} />
                    </IconButton>
                </Tooltip>
                <ThemeSwitcher themeId={themeId} onThemeChange={onThemeChange} />
                {activeBrainstorm && (
                    <ModelSwitcher
                        currentModel={activeBrainstorm.model || ''}
                        onModelChange={onModelChange}
                        onAddModel={() => setAddModelOpen(true)}
                    />
                )}
                <Tooltip title={mode === 'dark' ? 'Light mode' : 'Dark mode'} arrow placement="right">
                    <IconButton
                        onClick={onToggleTheme}
                        size="small"
                        sx={(theme) => ({
                            width: 28,
                            height: 28,
                            borderRadius: 1,
                            color: alpha(theme.palette.text.secondary, 0.55),
                            '&:hover': {
                                color: theme.palette.text.primary,
                                bgcolor: alpha(theme.palette.action.hover, 0.4),
                            },
                        })}
                    >
                        {mode === 'dark' ? <LightModeIcon sx={{ fontSize: 16 }} /> : <DarkModeIcon sx={{ fontSize: 16 }} />}
                    </IconButton>
                </Tooltip>

                <Suspense fallback={null}>
                    {addModelOpen && <AddModelModal open={addModelOpen} onClose={() => setAddModelOpen(false)} />}
                </Suspense>
                <Suspense fallback={null}>
                    {shareOpen && <ShareDialog open={shareOpen} onClose={() => setShareOpen(false)} brainstormId={activeBrainstorm?.id} />}
                </Suspense>
            </Box>
        );
    }

    return (
        <Box
            sx={(theme) => ({
                width: { xs: '100vw', md: 280 },
                minWidth: { xs: '100vw', md: 280 },
                maxWidth: { xs: '100vw', md: 280 },
                height: '100vh',
                display: 'flex',
                flexDirection: 'column',
                bgcolor: theme.palette.mode === 'dark' ? alpha(theme.palette.background.paper, 0.75) : alpha(theme.palette.background.paper, 0.4),
                transition: 'all 0.2s ease',
                position: { xs: 'fixed', md: 'relative' },
                zIndex: { xs: 20, md: 1 },
                left: 0,
                top: 0,
                position: 'relative',
                zIndex: 10,
            })}
        >
            {/* ── Header ─────────────────────────────────────── */}
            <Box
                sx={{
                    px: 2.5,
                    py: 2,
                    display: 'flex',
                    alignItems: 'center',
                    gap: 1.5,
                }}
            >
                <Box
                    sx={(theme) => ({
                        width: 36,
                        height: 36,
                        borderRadius: 2,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        background: theme.palette.gradients.primary,
                        boxShadow: `0 2px 8px ${alpha(theme.palette.primary.main, 0.35)}`,
                        flexShrink: 0,
                    })}
                >
                    <BrainIcon sx={{ color: '#fff', fontSize: 20 }} />
                </Box>
                <Typography
                    variant="h6"
                    sx={{
                        flex: 1,
                        fontWeight: 800,
                        fontSize: '1.15rem',
                        letterSpacing: '-0.03em',
                        background: (theme) => theme.palette.gradients.brand,
                        WebkitBackgroundClip: 'text',
                        WebkitTextFillColor: 'transparent',
                    }}
                >
                    Brainstorm
                </Typography>
                <Tooltip title="Collapse sidebar" arrow>
                    <IconButton
                        size="small"
                        onClick={onToggleCollapse}
                        sx={(theme) => ({
                            color: alpha(theme.palette.text.secondary, 0.55),
                            borderRadius: 1.5,
                            width: 28,
                            height: 28,
                            '&:hover': {
                                bgcolor: alpha(theme.palette.action.hover, 0.4),
                                color: theme.palette.text.primary,
                            },
                        })}
                    >
                        <CollapseIcon sx={{ fontSize: 16 }} />
                    </IconButton>
                </Tooltip>
                <Tooltip title={mode === 'dark' ? 'Light mode' : 'Dark mode'} arrow>
                    <IconButton
                        size="small"
                        onClick={onToggleTheme}
                        sx={(theme) => ({
                            color: alpha(theme.palette.text.secondary, 0.55),
                            borderRadius: 1.5,
                            width: 28,
                            height: 28,
                            '&:hover': {
                                bgcolor: alpha(theme.palette.action.hover, 0.4),
                                color: theme.palette.text.primary,
                            },
                        })}
                    >
                        {mode === 'dark' ? <LightModeIcon sx={{ fontSize: 16 }} /> : <DarkModeIcon sx={{ fontSize: 16 }} />}
                    </IconButton>
                </Tooltip>
            </Box>

            {/* ── Search Input ──────────────────────────────── */}
            <Box sx={{ px: 2, pt: 1.5, pb: 0.5 }}>
                <TextField
                    fullWidth
                    size="small"
                    placeholder="Search..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    variant="outlined"
                    slotProps={{
                        input: {
                            startAdornment: (
                                <SearchIcon sx={(theme) => ({
                                    fontSize: 14,
                                    color: alpha(theme.palette.text.secondary, 0.5),
                                    mr: 0.75,
                                })} />
                            ),
                            sx: (theme) => ({
                                borderRadius: 1,
                                fontSize: '0.78rem',
                                bgcolor: alpha(theme.palette.background.paper, theme.palette.mode === 'dark' ? 0.6 : 0.5),
                                '& fieldset': { border: 'none' },
                                '&:hover': {
                                    borderColor: alpha(theme.palette.primary.main, 0.2),
                                },
                                '&.Mui-focused': {
                                    borderColor: theme.palette.primary.main,
                                    boxShadow: `0 0 0 2px ${alpha(theme.palette.primary.main, 0.1)}`,
                                },
                                '& input': {
                                    padding: '6px 8px !important',
                                    '&::placeholder': {
                                        color: alpha(theme.palette.text.secondary, 0.4),
                                        opacity: 1,
                                    },
                                },
                            }),
                        },
                    }}
                />
            </Box>

            {/* ── History Header ──────────────────────────────── */}
            <Box
                sx={{
                    px: 2.5,
                    pt: 1.5,
                    pb: 1,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                }}
            >
                <Typography
                    variant="overline"
                    sx={(theme) => ({
                        color: alpha(theme.palette.text.secondary, 0.7),
                        fontWeight: 700,
                        fontSize: '0.6rem',
                        letterSpacing: '0.1em',
                    })}
                >
                    History
                </Typography>
                {filteredBrainstorms.length > 0 && (
                    <Chip
                        label={filteredBrainstorms.length}
                        size="small"
                        sx={(theme) => ({
                            height: 20,
                            minWidth: 20,
                            fontSize: '0.65rem',
                            fontWeight: 700,
                            borderRadius: '10px',
                            bgcolor: alpha(theme.palette.primary.main, 0.15),
                            color: theme.palette.primary.light,
                            '& .MuiChip-label': { px: 0.6 },
                        })}
                    />
                )}
            </Box>

            <Tooltip title="New Brainstorm" arrow placement="right">
                <Box
                    role="button"
                    tabIndex={0}
                    onClick={onNew}
                    onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                            e.preventDefault();
                            onNew();
                        }
                    }}
                    sx={(theme) => ({
                        mx: 2,
                        mb: 1.25,
                        height: 56,
                        borderRadius: 2,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        cursor: 'pointer',
                        border: '1px dashed',
                        borderColor: alpha(theme.palette.primary.main, 0.28),
                        bgcolor: alpha(theme.palette.primary.main, 0.08),
                        color: theme.palette.primary.light,
                        transition: 'all 0.18s ease',
                        boxShadow: `inset 0 0 0 1px ${alpha(theme.palette.background.paper, 0.35)}`,
                        '&:hover': {
                            bgcolor: alpha(theme.palette.primary.main, 0.14),
                            borderColor: alpha(theme.palette.primary.main, 0.45),
                            transform: 'translateY(-1px)',
                        },
                        '&:focus-visible': {
                            outline: 'none',
                            boxShadow: `0 0 0 2px ${alpha(theme.palette.primary.main, 0.25)}`,
                        },
                    })}
                >
                    <AddIcon sx={{ fontSize: 28 }} />
                </Box>
            </Tooltip>

            {/* ── Brainstorm List ─────────────────────────────── */}
            <BrainstormList
                brainstorms={filteredBrainstorms}
                activeBrainstorm={activeBrainstorm}
                onSelect={onSelect}
                onDelete={onDelete}
                editingId={editingId}
                editTitle={editTitle}
                editingRef={editingRef}
                onStartEdit={handleStartRename}
                onEditTitleChange={(e) => setEditTitle(e.target.value)}
                onEditKeyDown={handleRenameKeyDown}
                onSaveEdit={handleSaveRename}
                searchQuery={searchQuery}
            />

            {/* ── Bottom toolbar ─────────────────────────── */}
            {activeBrainstorm && (
                <Box sx={(theme) => ({
                    px: 2, py: 1.5,
                    borderTop: '1px solid',
                    borderColor: alpha(theme.palette.divider, 0.1),
                    display: 'flex', flexDirection: 'column', gap: 1,
                    bgcolor: alpha(theme.palette.background.paper, 0.3),
                })}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <Chip
                            label={activeBrainstorm.model}
                            size="small"
                            sx={(theme) => ({
                                height: 24, fontSize: '0.7rem', fontWeight: 700, borderRadius: '6px',
                                bgcolor: alpha(theme.palette.primary.main, 0.12),
                                color: theme.palette.primary.light,
                                border: '1px solid', borderColor: alpha(theme.palette.primary.main, 0.15),
                                '& .MuiChip-label': { px: 1 },
                            })}
                        />
                        <IconButton
                            size="small"
                            onClick={() => setShareOpen(true)}
                            sx={(t) => ({
                                width: 28, height: 28, borderRadius: 1,
                                color: alpha(t.palette.text.secondary, 0.5),
                                ml: 'auto',
                                '&:hover': {
                                    bgcolor: alpha(t.palette.primary.main, 0.08),
                                    color: t.palette.primary.light,
                                },
                            })}
                        >
                            <ShareIcon sx={{ fontSize: 15 }} />
                        </IconButton>
                    </Box>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                        <ModelSwitcher
                            currentModel={activeBrainstorm?.model || ''}
                            onModelChange={onModelChange}
                            onAddModel={() => setAddModelOpen(true)}
                        />
                        <ThemeSwitcher themeId={themeId} onThemeChange={onThemeChange} />
                    </Box>
                </Box>
            )}

            <Suspense fallback={null}>
                {addModelOpen && <AddModelModal open={addModelOpen} onClose={() => setAddModelOpen(false)} />}
            </Suspense>
            <Suspense fallback={null}>
                {shareOpen && <ShareDialog open={shareOpen} onClose={() => setShareOpen(false)} brainstormId={activeBrainstorm?.id} />}
            </Suspense>
        </Box>
    );
}

export default Sidebar;