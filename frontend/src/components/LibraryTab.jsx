import { useState } from 'react';
import {
    Box, Typography, Accordion, AccordionSummary, AccordionDetails,
    TextField, IconButton, Tooltip, Chip, alpha, Divider,
} from '@mui/material';
import {
    Folder as FolderIcon, ExpandMore as ExpandIcon,
    Edit as EditIcon, Save as SaveIcon, Cancel as CancelIcon,
    Description as FileIcon, LibraryBooks as LibraryIcon,
    Download as DownloadIcon,
} from '@mui/icons-material';

function LibraryTab({ libraryData, onUpdateEntry, brainstormId }) {
    const [editingEntry, setEditingEntry] = useState(null);
    const [editContent, setEditContent] = useState('');

    const totalEntries = libraryData.reduce((sum, folder) => sum + folder.entries.length, 0);

    const handleStartEdit = (entry) => {
        setEditingEntry(entry.id);
        setEditContent(entry.content);
    };

    const handleSave = async () => {
        if (editingEntry) {
            await onUpdateEntry(editingEntry, editContent);
            setEditingEntry(null);
            setEditContent('');
        }
    };

    const handleCancel = () => {
        setEditingEntry(null);
        setEditContent('');
    };

    return (
        <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
            {/* ── Header ─────────────────────────────────────── */}
            <Box sx={(theme) => ({
                px: 3, py: 1.75,
                borderBottom: '1px solid', borderColor: alpha(theme.palette.divider, 0.5),
                bgcolor: alpha(theme.palette.background.default, 0.3),
                display: 'flex', alignItems: 'center', gap: 1.5,
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
                {totalEntries > 0 && brainstormId && (
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
                            border: '1px solid', borderColor: alpha(theme.palette.divider, 0.5),
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
                )}
            </Box>

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
                ) : (
                    libraryData.map((folder) => (
                        <Accordion key={folder.folder_name} defaultExpanded
                            sx={(theme) => ({
                                bgcolor: alpha(theme.palette.background.paper, 0.4),
                                boxShadow: 'none',
                                border: '1px solid',
                                borderColor: alpha(theme.palette.divider, 0.5),
                                borderRadius: '12px !important',
                                overflow: 'hidden',
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
                                        {folder.folder_name}
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
                            <AccordionDetails sx={(theme) => ({ pt: 0, pb: 2, px: 2 })}>
                                <Divider sx={(theme) => ({ mb: 1.5, borderColor: alpha(theme.palette.divider, 0.5) })} />
                                {folder.entries.map((entry) => (
                                    <Box key={entry.id}
                                        sx={(theme) => ({
                                            mb: 1.5,
                                            borderRadius: 2.5,
                                            bgcolor: alpha(theme.palette.background.paper, 0.3),
                                            border: '1px solid',
                                            borderColor: alpha(theme.palette.divider, 0.4),
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
                                            borderBottom: '1px solid',
                                            borderColor: alpha(theme.palette.divider, 0.4),
                                            bgcolor: alpha(theme.palette.action.hover, 0.3),
                                        })}>
                                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, minWidth: 0 }}>
                                                <FileIcon sx={(theme) => ({ fontSize: 14, color: alpha(theme.palette.text.secondary, 0.5), flexShrink: 0 })} />
                                                <Typography variant="caption" sx={(theme) => ({
                                                    color: alpha(theme.palette.text.secondary, 0.8),
                                                    fontWeight: 600, fontSize: '0.7rem',
                                                    overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                                                })}>
                                                    {entry.file_name}
                                                </Typography>
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
                                                fontFamily: '"JetBrains Mono", monospace',
                                                fontSize: '0.78rem', lineHeight: 1.7,
                                                color: alpha(theme.palette.text.primary, 0.8),
                                                whiteSpace: 'pre-wrap', wordBreak: 'break-word',
                                                maxHeight: 300, overflow: 'auto',
                                                px: 2, py: 1.5,
                                                '&::-webkit-scrollbar': { width: 4 },
                                            })}>
                                                {entry.content}
                                            </Box>
                                        )}
                                    </Box>
                                ))}
                            </AccordionDetails>
                        </Accordion>
                    ))
                )}
            </Box>
        </Box>
    );
}

export default LibraryTab;