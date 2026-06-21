import { useState, useMemo, useEffect } from 'react';
import {
    Box, Typography, Accordion, AccordionSummary, AccordionDetails,
    TextField, IconButton, Tooltip, Chip, alpha, Button,
    Dialog, DialogTitle, DialogContent, DialogContentText, DialogActions,
} from '@mui/material';
import {
    Folder as FolderIcon, ExpandMore as ExpandIcon,
    Edit as EditIcon, Save as SaveIcon, Cancel as CancelIcon,
    Description as FileIcon, LibraryBooks as LibraryIcon,
    Download as DownloadIcon, Delete as DeleteIcon,
    Search as SearchIcon, Close as CloseIcon,
    UnfoldMore as ExpandAllIcon, UnfoldLess as CollapseAllIcon,
} from '@mui/icons-material';
import ReactMarkdown from 'react-markdown';
import { exportMarkdown, exportOPML, importUrl } from '../../api';
import useLibraryStore from '../../stores/libraryStore';
import { OpenInNew as ImportIcon } from '@mui/icons-material';

function LibraryTab({ brainstormId }) {
    const libraryData = useLibraryStore(s => s.libraryData);
    const updateEntry = useLibraryStore(s => s.updateEntry);
    const deleteEntry = useLibraryStore(s => s.deleteEntry);
    const loadLibrary = useLibraryStore(s => s.loadLibrary);
    const [editingEntry, setEditingEntry] = useState(null);
    const [editContent, setEditContent] = useState('');
    const [deleteTarget, setDeleteTarget] = useState(null);
    const [searchQuery, setSearchQuery] = useState('');
    const [expandedFolders, setExpandedFolders] = useState(() => new Set());
    const [allExpanded, setAllExpanded] = useState(true);
    const [importingUrl, setImportingUrl] = useState(false);
    const [urlInput, setUrlInput] = useState('');
    const [showUrlInput, setShowUrlInput] = useState(false);

    // Filter by search query
    const filteredData = useMemo(() => {
        if (!searchQuery.trim()) return libraryData;
        const q = searchQuery.toLowerCase();
        return libraryData
            .map(folder => ({
                ...folder,
                entries: folder.entries.filter(e =>
                    e.file_name.toLowerCase().includes(q) ||
                    (e.content || '').toLowerCase().includes(q)
                ),
            }))
            .filter(folder => folder.entries.length > 0);
    }, [libraryData, searchQuery]);

    const totalEntries = libraryData.reduce((sum, folder) => sum + folder.entries.length, 0);
    const visibleEntries = filteredData.reduce((sum, folder) => sum + folder.entries.length, 0);

    const handleStartEdit = (entry) => {
        setEditingEntry(entry.id);
        setEditContent(entry.content);
    };

    const handleSave = async () => {
        if (editingEntry) {
            await updateEntry(editingEntry, editContent);
            await loadLibrary(brainstormId);
            setEditingEntry(null);
            setEditContent('');
        }
    };

    const handleCancel = () => {
        setEditingEntry(null);
        setEditContent('');
    };

    const handleDelete = async () => {
        if (deleteTarget) {
            await deleteEntry(deleteTarget);
            await loadLibrary(brainstormId);
            setDeleteTarget(null);
        }
    };

    const handleImportUrl = async () => {
        if (!urlInput.trim() || !brainstormId) return;
        setImportingUrl(true);
        try {
            await importUrl(brainstormId, urlInput.trim());
            await loadLibrary(brainstormId);
            setUrlInput('');
            setShowUrlInput(false);
        } catch (err) {
            console.error('URL import failed:', err);
        } finally {
            setImportingUrl(false);
        }
    };

    const toggleExpandAll = () => {
        if (allExpanded) {
            setAllExpanded(false);
            setExpandedFolders(new Set());
        } else {
            setAllExpanded(true);
            const all = new Set(filteredData.map(f => f.folder_name));
            setExpandedFolders(all);
        }
    };

    // Sync expandedFolders when data changes or expand/collapse all
    useEffect(() => {
        if (allExpanded) {
            setExpandedFolders(new Set(filteredData.map(f => f.folder_name)));
        }
    }, [filteredData, allExpanded]);

    const toggleFolder = (folderName) => {
        setExpandedFolders(prev => {
            const next = new Set(prev);
            if (next.has(folderName)) {
                next.delete(folderName);
                // If any folder is collapsed, we're not "all expanded"
                setAllExpanded(false);
            } else {
                next.add(folderName);
                // Check if all are now expanded
                if (next.size === filteredData.length) {
                    setAllExpanded(true);
                }
            }
            return next;
        });
    };

    return (
        <Box sx={(theme) => ({
            height: '100%', display: 'flex', flexDirection: 'column',
            bgcolor: 'transparent',
            backgroundImage: `linear-gradient(to right, ${alpha(theme.palette.primary.main, theme.palette.mode === 'dark' ? 0.04 : 0.06)} 1px, transparent 1px), linear-gradient(to bottom, ${alpha(theme.palette.primary.main, theme.palette.mode === 'dark' ? 0.04 : 0.06)} 1px, transparent 1px)`,
            backgroundSize: '24px 24px',
        })}>
            {/* ── Header ─────────────────────────────────────── */}
            <Box sx={(theme) => ({
                px: 3, py: 1.75,
                bgcolor: alpha(theme.palette.background.default, 0.3),
                display: 'flex', alignItems: 'center', gap: 1.5, flexWrap: 'wrap',
            })}>
                <Box sx={(theme) => ({
                    width: 28, height: 28, borderRadius: 1.5,
                    background: `linear-gradient(135deg, ${alpha(theme.palette.primary.main, 0.2)} 0%, ${alpha(theme.palette.primary.light, 0.12)} 100%)`,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                })}>
                    <LibraryIcon sx={(theme) => ({ fontSize: 15, color: theme.palette.primary.light })} />
                </Box>
                <Typography sx={{ fontWeight: 700, fontSize: '0.925rem', color: 'text.primary' }}>
                    Library
                </Typography>
                {totalEntries > 0 && (
                    <Chip label={`${totalEntries} file${totalEntries !== 1 ? 's' : ''}`} size="small"
                        sx={(theme) => ({
                            height: 20, fontSize: '0.6rem', fontWeight: 700, borderRadius: '6px',
                            bgcolor: alpha(theme.palette.primary.main, 0.15),
                            color: theme.palette.primary.light,
                            '& .MuiChip-label': { px: 0.8 },
                        })} />
                )}
                {totalEntries > 0 && (
                    <>
                        <Tooltip title={allExpanded ? 'Collapse all' : 'Expand all'} arrow>
                            <IconButton onClick={toggleExpandAll} size="small"
                                sx={(theme) => ({
                                    width: 28, height: 28, borderRadius: 1,
                                    color: alpha(theme.palette.text.secondary, 0.5),
                                    '&:hover': {
                                        bgcolor: alpha(theme.palette.primary.main, 0.08),
                                        color: theme.palette.primary.light,
                                    },
                                })}>
                                {allExpanded ? <CollapseAllIcon sx={{ fontSize: 14 }} /> : <ExpandAllIcon sx={{ fontSize: 14 }} />}
                            </IconButton>
                        </Tooltip>
                        <Tooltip title="Import web page" arrow>
                            <IconButton
                                size="small"
                                onClick={() => setShowUrlInput(v => !v)}
                                sx={(theme) => ({
                                    width: 28, height: 28, borderRadius: 1,
                                    color: alpha(theme.palette.text.secondary, 0.5),
                                    '&:hover': {
                                        bgcolor: alpha(theme.palette.primary.main, 0.08),
                                        color: theme.palette.primary.light,
                                    },
                                })}
                            >
                                <ImportIcon sx={{ fontSize: 14 }} />
                            </IconButton>
                        </Tooltip>
                        <Tooltip title="Export as OPML (mind map)" arrow>
                            <IconButton
                                size="small"
                                onClick={async () => {
                                    try {
                                        const res = await exportOPML(brainstormId);
                                        const url = window.URL.createObjectURL(new Blob([res.data]));
                                        const a = document.createElement('a');
                                        a.href = url;
                                        a.download = 'brainstorm_export.opml';
                                        a.click();
                                        window.URL.revokeObjectURL(url);
                                    } catch (err) {
                                        console.error('OPML export failed:', err);
                                    }
                                }}
                                sx={(theme) => ({
                                    width: 28, height: 28, borderRadius: 1,
                                    color: alpha(theme.palette.text.secondary, 0.5),
                                    '&:hover': {
                                        bgcolor: alpha(theme.palette.primary.main, 0.08),
                                        color: theme.palette.primary.light,
                                    },
                                })}
                            >
                                <DownloadIcon sx={{ fontSize: 13 }} />
                            </IconButton>
                        </Tooltip>
                        <Tooltip title="Export all as Markdown .zip" arrow>
                            <IconButton
                                size="small"
                                onClick={async () => {
                                    try {
                                        const res = await exportMarkdown(brainstormId);
                                        const url = window.URL.createObjectURL(new Blob([res.data]));
                                        const a = document.createElement('a');
                                        a.href = url;
                                        a.download = 'brainstorm_export.zip';
                                        a.click();
                                        window.URL.revokeObjectURL(url);
                                    } catch (err) {
                                        console.error('Export failed:', err);
                                    }
                                }}
                                sx={(theme) => ({
                                    ml: 'auto',
                                    width: 28, height: 28, borderRadius: 1,
                                    color: alpha(theme.palette.text.secondary, 0.5),
                                    '&:hover': {
                                        bgcolor: alpha(theme.palette.primary.main, 0.08),
                                        color: theme.palette.primary.light,
                                        borderColor: alpha(theme.palette.primary.main, 0.15),
                                    },
                                })}
                            >
                                <DownloadIcon sx={{ fontSize: 14 }} />
                            </IconButton>
                        </Tooltip>
                    </>
                )}
            </Box>

            {/* ── URL Import ──────────────────────────────────── */}
            {showUrlInput && (
                <Box sx={(theme) => ({
                    mx: 2.5, mt: 1.5, p: 1.5, borderRadius: 2,
                    bgcolor: alpha(theme.palette.background.paper, 0.4),
                    border: '1px solid', borderColor: alpha(theme.palette.primary.main, 0.12),
                    display: 'flex', gap: 1,
                })}>
                    <TextField
                        fullWidth
                        size="small"
                        placeholder="https://example.com/article"
                        value={urlInput}
                        onChange={e => setUrlInput(e.target.value)}
                        onKeyDown={e => { if (e.key === 'Enter') handleImportUrl(); }}
                        disabled={importingUrl}
                        slotProps={{
                            input: {
                                sx: (theme) => ({
                                    fontSize: '0.78rem', borderRadius: 1.5,
                                    bgcolor: alpha(theme.palette.background.default, 0.3),
                                    '& fieldset': { border: 'none' },
                                    '& input': { py: 1, '&::placeholder': { color: alpha(theme.palette.text.secondary, 0.35), opacity: 1 } },
                                }),
                            },
                        }}
                    />
                    <Button
                        size="small"
                        disabled={!urlInput.trim() || importingUrl}
                        onClick={handleImportUrl}
                        variant="outlined"
                        sx={{ minWidth: 72, fontSize: '0.75rem', borderRadius: 1.5, textTransform: 'none', whiteSpace: 'nowrap' }}
                    >
                        {importingUrl ? '...' : 'Import'}
                    </Button>
                </Box>
            )}

            {/* ── Search ──────────────────────────────────────── */}
            {totalEntries > 3 && (
                <Box sx={{ px: 2.5, pt: 1.5 }}>
                    <TextField
                        fullWidth
                        size="small"
                        placeholder="Search entries..."
                        value={searchQuery}
                        onChange={e => setSearchQuery(e.target.value)}
                        slotProps={{
                            input: {
                                startAdornment: <SearchIcon sx={(theme) => ({ fontSize: 16, color: alpha(theme.palette.text.secondary, 0.4), mr: 0.5 })} />,
                                endAdornment: searchQuery ? (
                                    <IconButton size="small" onClick={() => setSearchQuery('')} sx={{ p: 0.25 }}>
                                        <CloseIcon sx={{ fontSize: 14 }} />
                                    </IconButton>
                                ) : undefined,
                                sx: (theme) => ({
                                    borderRadius: 1.5,
                                    fontSize: '0.8rem',
                                    bgcolor: alpha(theme.palette.background.paper, 0.4),
                                    '& fieldset': { border: 'none' },
                                    '& input': { py: 0.75 },
                                }),
                            },
                        }}
                    />
                </Box>
            )}

            {/* ── Content ─────────────────────────────────────── */}
            <Box sx={(theme) => ({
                flex: 1, overflow: 'auto',
                px: { xs: 1.5, md: 2.5 }, py: 2,
                display: 'flex', flexDirection: 'column', gap: 1.5,
            })}>
                {libraryData.length === 0 ? (
                    <Box sx={(theme) => ({
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        height: '100%', flexDirection: 'column', gap: 2,
                    })}>
                        <Box sx={(theme) => ({
                            width: 64, height: 64, borderRadius: 3,
                            background: `linear-gradient(135deg, ${alpha(theme.palette.primary.main, 0.18)} 0%, ${alpha(theme.palette.primary.light, 0.1)} 100%)`,
                            border: '1px solid', borderColor: alpha(theme.palette.primary.main, 0.12),
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                        })}>
                            <LibraryIcon sx={(theme) => ({ fontSize: 26, color: alpha(theme.palette.text.secondary, 0.5) })} />
                        </Box>
                        <Box sx={{ textAlign: 'center', maxWidth: 260 }}>
                            <Typography sx={(theme) => ({
                                fontWeight: 600, color: alpha(theme.palette.text.primary, 0.8),
                                mb: 0.5, fontSize: '0.9rem',
                            })}>
                                No library entries yet
                            </Typography>
                            <Typography variant="body2" sx={(theme) => ({
                                color: alpha(theme.palette.text.secondary, 0.65), lineHeight: 1.6,
                            })}>
                                Topics will appear here as you chat.
                            </Typography>
                        </Box>
                    </Box>
                ) : filteredData.length === 0 ? (
                    <Box sx={(theme) => ({
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        height: '100%', flexDirection: 'column', gap: 2,
                    })}>
                        <SearchIcon sx={(theme) => ({ fontSize: 32, color: alpha(theme.palette.text.secondary, 0.3) })} />
                        <Typography sx={(theme) => ({ color: alpha(theme.palette.text.secondary, 0.5), fontSize: '0.85rem' })}>
                            No entries match "{searchQuery}"
                        </Typography>
                    </Box>
                ) : (
                    filteredData.map((folder) => {
                        const isExpanded = expandedFolders.has(folder.folder_name);
                        return (
                        <Accordion key={folder.folder_name} expanded={isExpanded} onChange={() => toggleFolder(folder.folder_name)}
                            sx={(theme) => ({
                                bgcolor: alpha(theme.palette.background.paper, 0.4),
                                boxShadow: 'none',
                                borderRadius: '12px !important',
                                overflow: 'hidden',
                                border: '1px solid',
                                borderColor: alpha(theme.palette.divider, 0.08),
                                transition: 'border-color 0.2s ease',
                                '&:hover': {
                                    borderColor: alpha(theme.palette.primary.main, 0.2),
                                },
                                '&:before': { display: 'none' },
                                '&.Mui-expanded': { margin: '0 0 8px 0' },
                            })}
                        >
                            <AccordionSummary
                                expandIcon={<ExpandIcon sx={(theme) => ({ color: alpha(theme.palette.text.secondary, 0.5), fontSize: 20 })} />}
                                sx={(theme) => ({
                                    minHeight: 48, px: 2,
                                    borderRadius: '12px',
                                    '&.Mui-expanded': { minHeight: 48, borderBottomLeftRadius: 0, borderBottomRightRadius: 0 },
                                    '& .MuiAccordionSummary-content': { margin: '12px 0' },
                                    '&:hover': { bgcolor: alpha(theme.palette.action.hover, 0.4) },
                                })}>
                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                                    <FolderIcon sx={(theme) => ({ color: theme.palette.primary.light, fontSize: 20, opacity: 0.85 })} />
                                    <Typography sx={{ fontWeight: 600, color: 'text.primary', fontSize: '0.825rem' }}>
                                        {folder.folder_name.replace(/-/g, ' ')}
                                    </Typography>
                                    <Chip label={`${folder.entries.length} file${folder.entries.length !== 1 ? 's' : ''}`} size="small"
                                        sx={(theme) => ({
                                            height: 18, fontSize: '0.6rem', fontWeight: 600, borderRadius: '5px',
                                            bgcolor: alpha(theme.palette.text.secondary, 0.12),
                                            color: alpha(theme.palette.text.secondary, 0.7),
                                            '& .MuiChip-label': { px: 0.6 },
                                        })} />
                                </Box>
                            </AccordionSummary>
                            <AccordionDetails sx={{ pt: 0, pb: 2, px: 2 }}>
                                {folder.entries.map((entry) => (
                                    <Box key={entry.id}
                                        sx={(theme) => ({
                                            mb: 1.5,
                                            borderRadius: 2,
                                            bgcolor: alpha(theme.palette.background.paper, 0.5),
                                            border: '1px solid',
                                            borderColor: alpha(theme.palette.divider, 0.06),
                                            overflow: 'hidden',
                                            transition: 'border-color 0.2s ease',
                                            '&:hover': {
                                                borderColor: alpha(theme.palette.primary.main, 0.15),
                                            },
                                            '&:last-child': { mb: 0 },
                                        })}
                                    >
                                        {/* Entry Header */}
                                        <Box sx={(theme) => ({
                                            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                                            px: 1.5, py: 1,
                                            bgcolor: alpha(theme.palette.action.hover, 0.25),
                                        })}>
                                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, minWidth: 0 }}>
                                                <FileIcon sx={(theme) => ({ fontSize: 14, color: alpha(theme.palette.primary.light, 0.5), flexShrink: 0 })} />
                                                <Typography variant="caption" sx={(theme) => ({
                                                    color: alpha(theme.palette.text.secondary, 0.8),
                                                    fontWeight: 600, fontSize: '0.7rem',
                                                    overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                                                })}>
                                                    {entry.file_name}
                                                </Typography>
                                                {entry.created_at && (
                                                    <Typography variant="caption" sx={(theme) => ({
                                                        color: alpha(theme.palette.text.secondary, 0.35),
                                                        fontSize: '0.6rem', flexShrink: 0,
                                                    })}>
                                                        {new Date(entry.created_at).toLocaleDateString([], { month: 'short', day: 'numeric' })}
                                                    </Typography>
                                                )}
                                            </Box>
                                            <Box sx={{ display: 'flex', gap: 0.25, flexShrink: 0 }}>
                                                {editingEntry === entry.id ? (
                                                    <>
                                                        <Tooltip title="Save changes" arrow>
                                                            <IconButton size="small" onClick={handleSave}
                                                                sx={(theme) => ({
                                                                    color: theme.palette.success.light,
                                                                    width: 28, height: 28, borderRadius: 1,
                                                                    '&:hover': { bgcolor: alpha(theme.palette.success.main, 0.15) },
                                                                })}>
                                                                <SaveIcon sx={{ fontSize: 14 }} />
                                                            </IconButton>
                                                        </Tooltip>
                                                        <Tooltip title="Cancel" arrow>
                                                            <IconButton size="small" onClick={handleCancel}
                                                                sx={(theme) => ({
                                                                    color: alpha(theme.palette.text.secondary, 0.6),
                                                                    width: 28, height: 28, borderRadius: 1,
                                                                    '&:hover': { bgcolor: alpha(theme.palette.action.hover, 0.6) },
                                                                })}>
                                                                <CancelIcon sx={{ fontSize: 14 }} />
                                                            </IconButton>
                                                        </Tooltip>
                                                    </>
                                                ) : (
                                                    <>
                                                        <Tooltip title="Edit content" arrow>
                                                            <IconButton size="small" onClick={() => handleStartEdit(entry)}
                                                                sx={(theme) => ({
                                                                    color: alpha(theme.palette.text.secondary, 0.4),
                                                                    width: 28, height: 28, borderRadius: 1,
                                                                    '&:hover': {
                                                                        color: theme.palette.primary.light,
                                                                        bgcolor: alpha(theme.palette.primary.main, 0.15),
                                                                    },
                                                                })}>
                                                                <EditIcon sx={{ fontSize: 14 }} />
                                                            </IconButton>
                                                        </Tooltip>
                                                        <Tooltip title="Delete entry" arrow>
                                                            <IconButton size="small" onClick={() => setDeleteTarget(entry.id)}
                                                                sx={(theme) => ({
                                                                    color: alpha(theme.palette.text.secondary, 0.3),
                                                                    width: 28, height: 28, borderRadius: 1,
                                                                    '&:hover': {
                                                                        color: theme.palette.error.light,
                                                                        bgcolor: alpha(theme.palette.error.main, 0.12),
                                                                    },
                                                                })}>
                                                                <DeleteIcon sx={{ fontSize: 14 }} />
                                                            </IconButton>
                                                        </Tooltip>
                                                    </>
                                                )}
                                            </Box>
                                        </Box>

                                        {/* Entry Content */}
                                        {editingEntry === entry.id ? (
                                            <TextField
                                                fullWidth multiline minRows={6} maxRows={20}
                                                value={editContent}
                                                onChange={(e) => setEditContent(e.target.value)}
                                                variant="outlined" size="small"
                                                sx={(theme) => ({
                                                    '& .MuiOutlinedInput-root': {
                                                        borderRadius: 0, border: 'none',
                                                        fontFamily: '"JetBrains Mono", monospace',
                                                        fontSize: '0.78rem', lineHeight: 1.7,
                                                        bgcolor: 'transparent',
                                                        '& fieldset': { border: 'none' },
                                                        '& textarea': {
                                                            padding: '12px 16px !important',
                                                            color: theme.palette.text.primary,
                                                        },
                                                    },
                                                })}
                                            />
                                        ) : (
                                            <Box sx={(theme) => ({
                                                fontSize: '0.82rem', lineHeight: 1.75,
                                                color: theme.palette.text.primary,
                                                maxHeight: 420, overflow: 'auto',
                                                px: 2, py: 1.5,
                                                '&::-webkit-scrollbar': { width: 4 },
                                                '& h1, & h2, & h3, & h4': {
                                                    mt: 2, mb: 0.75,
                                                    fontWeight: 700,
                                                    color: theme.palette.text.primary,
                                                    '&:first-child': { mt: 0 },
                                                },
                                                '& h1': { fontSize: '1.2rem' },
                                                '& h2': { fontSize: '1rem', color: theme.palette.primary.light },
                                                '& h3': { fontSize: '0.9rem' },
                                                '& p': { mb: 0.75 },
                                                '& ul, & ol': { pl: 2.5, mb: 0.75 },
                                                '& li': { mb: 0.25 },
                                                '& code': {
                                                    px: 0.6, py: 0.2,
                                                    borderRadius: 0.75,
                                                    bgcolor: alpha(theme.palette.primary.main, theme.palette.mode === 'dark' ? 0.12 : 0.06),
                                                    fontSize: '0.78rem',
                                                    fontFamily: '"JetBrains Mono", monospace',
                                                },
                                                '& pre': {
                                                    p: 1.5, borderRadius: 1.5,
                                                    bgcolor: alpha(theme.palette.background.default, 0.6),
                                                    overflow: 'auto',
                                                    mb: 0.75,
                                                },
                                                '& pre code': {
                                                    bgcolor: 'transparent', p: 0,
                                                },
                                                '& blockquote': {
                                                    pl: 1.5,
                                                    borderLeft: `3px solid ${alpha(theme.palette.primary.main, 0.35)}`,
                                                    color: alpha(theme.palette.text.secondary, 0.85),
                                                    mb: 0.75,
                                                },
                                                '& strong': { fontWeight: 700, color: theme.palette.text.primary },
                                                '& a': { color: theme.palette.primary.light },
                                                '& hr': {
                                                    border: 'none',
                                                    borderTop: `1px solid ${alpha(theme.palette.divider, 0.08)}`,
                                                    my: 1.5,
                                                },
                                            })}>
                                                <ReactMarkdown>{entry.content || '*No content yet.*'}</ReactMarkdown>
                                            </Box>
                                        )}
                                    </Box>
                                ))}
                            </AccordionDetails>
                        </Accordion>
                    );
                }
                )
                )}
            </Box>

            {/* ── Delete Confirmation Dialog ────────────────── */}
            <Dialog open={Boolean(deleteTarget)} onClose={() => setDeleteTarget(null)} maxWidth="xs">
                <DialogTitle sx={{ fontWeight: 700, fontSize: '1rem' }}>Delete entry?</DialogTitle>
                <DialogContent>
                    <DialogContentText sx={{ fontSize: '0.8rem' }}>
                        This will permanently remove this library entry. This action cannot be undone.
                    </DialogContentText>
                </DialogContent>
                <DialogActions sx={{ px: 2.5, pb: 2, gap: 1 }}>
                    <Button onClick={() => setDeleteTarget(null)} sx={{ borderRadius: 1.5, textTransform: 'none', fontSize: '0.8rem' }}>
                        Cancel
                    </Button>
                    <Button onClick={handleDelete} variant="contained" color="error"
                        sx={{ borderRadius: 1.5, textTransform: 'none', fontSize: '0.8rem', fontWeight: 600 }}>
                        Delete
                    </Button>
                </DialogActions>
            </Dialog>
        </Box>
    );
}

export default LibraryTab;