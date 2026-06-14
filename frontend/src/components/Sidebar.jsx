import { useState, useRef } from 'react';
import {
    Box,
    Typography,
    List,
    ListItemButton,
    ListItemText,
    ListItemIcon,
    IconButton,
    Divider,
    Button,
    alpha,
    Chip,
    TextField,
    Tooltip,
} from '@mui/material';
import {
    Add as AddIcon,
    Chat as ChatIcon,
    DarkMode as DarkModeIcon,
    LightMode as LightModeIcon,
    Psychology as BrainIcon,
    Delete as DeleteIcon,
    Edit as EditIcon,
    MenuOpen as CollapseIcon,
    ChevronRight as ExpandIcon,
    Search as SearchIcon,
} from '@mui/icons-material';
import { updateBrainstormTitle } from '../api';

function Sidebar({ brainstorms, activeBrainstorm, onNew, onSelect, onDelete, mode, onToggleTheme, collapsed, onToggleCollapse, onRenameComplete }) {
    const [editingId, setEditingId] = useState(null);
    const [editTitle, setEditTitle] = useState('');
    const [searchQuery, setSearchQuery] = useState('');
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
            await updateBrainstormTitle(editingId, editTitle.trim());
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
                    borderRight: '1px solid',
                    borderColor: alpha(theme.palette.divider, 0.6),
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
            </Box>
        );
    }

    return (
        <Box
            sx={(theme) => ({
                width: 280,
                minWidth: 280,
                height: '100vh',
                display: 'flex',
                flexDirection: 'column',
                bgcolor: theme.palette.mode === 'dark' ? alpha(theme.palette.background.paper, 0.75) : alpha(theme.palette.background.paper, 0.4),
                borderRight: '1px solid',
                borderColor: alpha(theme.palette.divider, 0.6),
                transition: 'all 0.2s ease',
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

            <Divider sx={{ borderColor: (theme) => alpha(theme.palette.divider, 0.6) }} />

            {/* ── New Brainstorm Button ───────────────────────── */}
            <Box sx={{ px: 2, py: 2 }}>
                <Button
                    variant="contained"
                    fullWidth
                    startIcon={<AddIcon />}
                    onClick={onNew}
                    sx={(theme) => ({
                        borderRadius: 1,
                        textTransform: 'none',
                        fontWeight: 600,
                        fontSize: '0.85rem',
                        py: 1.2,
                        background: theme.palette.gradients.primary,
                        boxShadow: `0 2px 8px ${alpha(theme.palette.primary.main, 0.28)}`,
                        '&:hover': {
                            background: theme.palette.gradients.primaryHover,
                            boxShadow: `0 4px 14px ${alpha(theme.palette.primary.main, 0.4)}`,
                            transform: 'translateY(-1px)',
                        },
                        '&:active': {
                            transform: 'translateY(0)',
                            boxShadow: `0 1px 4px ${alpha(theme.palette.primary.main, 0.22)}`,
                        },
                    })}
                >
                    New Brainstorm
                </Button>
            </Box>

            <Divider sx={{ borderColor: (theme) => alpha(theme.palette.divider, 0.6) }} />

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
                                border: '1px solid',
                                borderColor: alpha(theme.palette.divider, 0.5),
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

            {/* ── Brainstorm List ─────────────────────────────── */}
            <List sx={{ flex: 1, overflow: 'auto', px: 1.5, pb: 2, '& > :last-child': { mb: 0 } }}>
                {filteredBrainstorms.length === 0 ? (
                    <Box
                        sx={{
                            display: 'flex',
                            flexDirection: 'column',
                            alignItems: 'center',
                            justifyContent: 'center',
                            py: 6,
                            px: 2,
                            gap: 1.5,
                        }}
                    >
                        <BrainIcon
                            sx={(theme) => ({
                                fontSize: 36,
                                color: alpha(theme.palette.text.disabled, 0.4),
                                opacity: 0.5,
                            })}
                            className="empty-state-icon"
                        />
                        <Typography
                            variant="body2"
                            sx={(theme) => ({ color: alpha(theme.palette.text.secondary, 0.6), textAlign: 'center', lineHeight: 1.5 })}
                        >
                            {searchQuery ? 'No matching sessions.' : 'No brainstorms yet.\nEnter a topic above and explore.'}
                        </Typography>
                    </Box>
                ) : (
                    filteredBrainstorms.map((b) => (
                        <ListItemWrapper
                            key={b.id}
                            brainstorm={b}
                            isActive={activeBrainstorm?.id === b.id}
                            editingId={editingId}
                            editTitle={editTitle}
                            editingRef={editingRef}
                            onSelect={() => onSelect(b)}
                            onStartEdit={(e) => handleStartRename(e, b)}
                            onEditTitleChange={(e) => setEditTitle(e.target.value)}
                            onEditKeyDown={handleRenameKeyDown}
                            onSaveEdit={handleSaveRename}
                            onDelete={(e) => {
                                e.stopPropagation();
                                onDelete(b);
                            }}
                        />
                    ))
                )}
            </List>
        </Box>
    );
}

function ListItemWrapper({ brainstorm: b, isActive, onSelect, onStartEdit, onDelete, editingId, editTitle, editingRef, onEditTitleChange, onEditKeyDown, onSaveEdit }) {
    const isEditing = editingId === b.id;

    return (
        <Box
            sx={{
                position: 'relative',
                mb: 0.5,
                borderRadius: 2,
                '&:hover .brainstorm-actions': { opacity: 1 },
            }}
        >
            <ListItemButton
                selected={isActive}
                onClick={isEditing ? undefined : onSelect}
                sx={(theme) => ({
                    borderRadius: 2,
                    py: 1.2,
                    px: 1.5,
                    pr: 5.5,
                    position: 'relative',
                    overflow: 'hidden',
                    '&::before': isActive ? {
                        content: '""',
                        position: 'absolute',
                        left: 0,
                        top: 0,
                        bottom: 0,
                        width: 3,
                        borderRadius: '0 2px 2px 0',
                        bgcolor: 'primary.main',
                        boxShadow: (theme) => `0 0 10px ${alpha(theme.palette.primary.main, 0.4)}`,
                    } : {},
                    '&.Mui-selected': {
                        bgcolor: (theme) => alpha(theme.palette.primary.main, 0.12),
                        border: '1px solid',
                        borderColor: (theme) => alpha(theme.palette.primary.main, 0.18),
                        '&:hover': { bgcolor: (theme) => alpha(theme.palette.primary.main, 0.12) },
                    },
                    '&:hover': {
                        bgcolor: (theme) => alpha(theme.palette.action.hover, 0.3),
                    },
                })}
            >
                <ListItemIcon sx={{ minWidth: 34 }}>
                    <ChatIcon
                        sx={(theme) => ({
                            fontSize: 17,
                            color: isActive ? theme.palette.primary.light : alpha(theme.palette.text.secondary, 0.5),
                            transition: 'color 0.2s ease',
                        })}
                    />
                </ListItemIcon>
                {isEditing ? (
                    <TextField
                        inputRef={editingRef}
                        fullWidth
                        size="small"
                        value={editTitle}
                        onChange={onEditTitleChange}
                        onKeyDown={onEditKeyDown}
                        onBlur={onSaveEdit}
                        onClick={(e) => e.stopPropagation()}
                        variant="outlined"
                        slotProps={{
                            input: {
                                sx: (theme) => ({
                                    borderRadius: 1.5,
                                    fontSize: '0.825rem',
                                    fontWeight: 600,
                                    color: theme.palette.text.primary,
                                    bgcolor: alpha(theme.palette.primary.main, 0.08),
                                    border: '1px solid',
                                    borderColor: theme.palette.primary.main,
                                    '& fieldset': { border: 'none' },
                                    '& input': {
                                        padding: '2px 8px !important',
                                    },
                                }),
                            },
                        }}
                    />
                ) : (
                    <ListItemText
                        primary={b.title}
                        secondary={`${b.message_count} message${b.message_count !== 1 ? 's' : ''}`}
                        slotProps={{
                            primary: {
                                variant: 'body2',
                                fontWeight: isActive ? 600 : 500,
                                noWrap: true,
                                sx: {
                                    color: isActive ? 'text.primary' : 'text.secondary',
                                    fontSize: '0.825rem',
                                    lineHeight: 1.4,
                                },
                            },
                            secondary: {
                                variant: 'caption',
                                sx: (theme) => ({
                                    color: alpha(theme.palette.text.secondary, 0.55),
                                    fontSize: '0.7rem',
                                    lineHeight: 1.3,
                                    mt: 0.25,
                                }),
                            },
                        }}
                    />
                )}
            </ListItemButton>
            {/* ── Action Buttons ──────────────────────────────── */}
            <Box
                className="brainstorm-actions"
                sx={{
                    position: 'absolute',
                    right: 8,
                    top: '50%',
                    transform: 'translateY(-50%)',
                    display: 'flex',
                    gap: 0.25,
                    opacity: 0,
                    transition: 'opacity 0.15s ease',
                }}
            >
                {!isEditing && (
                    <>
                        <Tooltip title="Rename" arrow>
                            <IconButton
                                size="small"
                                onClick={onStartEdit}
                                sx={(theme) => ({
                                    width: 24,
                                    height: 24,
                                    borderRadius: 1,
                                    color: alpha(theme.palette.text.secondary, 0.4),
                                    '&:hover': {
                                        color: theme.palette.primary.light,
                                        bgcolor: alpha(theme.palette.primary.main, 0.15),
                                    },
                                })}
                                aria-label={`Rename ${b.title}`}
                            >
                                <EditIcon sx={{ fontSize: 12 }} />
                            </IconButton>
                        </Tooltip>
                        <Tooltip title="Delete" arrow>
                            <IconButton
                                size="small"
                                onClick={onDelete}
                                sx={(theme) => ({
                                    width: 24,
                                    height: 24,
                                    borderRadius: 1,
                                    color: alpha(theme.palette.text.secondary, 0.4),
                                    '&:hover': {
                                        color: theme.palette.error.main,
                                        bgcolor: alpha(theme.palette.error.main, 0.15),
                                    },
                                })}
                                aria-label={`Delete ${b.title}`}
                            >
                                <DeleteIcon sx={{ fontSize: 12 }} />
                            </IconButton>
                        </Tooltip>
                    </>
                )}
            </Box>
        </Box>
    );
}

export default Sidebar;