import { Box, ListItemButton, ListItemIcon, ListItemText, TextField, Tooltip, IconButton, alpha, Chip } from '@mui/material';
import { Chat as ChatIcon, Delete as DeleteIcon, Edit as EditIcon } from '@mui/icons-material';

function BrainstormItem({ brainstorm: b, isActive, onSelect, onStartEdit, onDelete, editingId, editTitle, editingRef, onEditTitleChange, onEditKeyDown, onSaveEdit }) {
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
                        secondary={`${b.explored_topic_count ?? b.message_count ?? 0} explored topic${(b.explored_topic_count ?? b.message_count ?? 0) !== 1 ? 's' : ''}`}
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

export default BrainstormItem;
