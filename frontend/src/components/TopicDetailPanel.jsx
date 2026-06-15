import { useState } from 'react';
import {
    Box, Typography, TextField, IconButton, Button, Chip, Divider,
    alpha, useTheme, CircularProgress, Tooltip, Dialog, DialogTitle,
    DialogContent, DialogContentText, DialogActions,
} from '@mui/material';
import {
    Close as CloseIcon,
    Delete as DeleteIcon,
    Edit as EditIcon,
    Check as CheckIcon,
    AutoAwesome as ExploreIcon,
    Description as DescriptionIcon,
    Link as LinkIcon,
    Psychology as ConfidenceIcon,
} from '@mui/icons-material';

function TopicDetailPanel({
    topic,
    mapData,
    libraryData,
    onClose,
    onUpdate,
    onDelete,
    onExplore,
    onSwitchToLibrary,
}) {
    const theme = useTheme();
    const isDark = theme.palette.mode === 'dark';

    const [isEditing, setIsEditing] = useState(false);
    const [editName, setEditName] = useState('');
    const [editDescription, setEditDescription] = useState('');
    const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
    const [exploring, setExploring] = useState(false);
    const [deleting, setDeleting] = useState(false);
    const [saving, setSaving] = useState(false);

    if (!topic) return null;

    const topicData = mapData?.topics?.find(t => t.id === topic.id) || topic;
    const edges = mapData?.edges || [];
    const connectedEdges = edges.filter(
        e => e.source_topic_id === topicData.id || e.target_topic_id === topicData.id
    );
    const connectedTopicIds = new Set();
    connectedEdges.forEach(e => {
        if (e.source_topic_id !== topicData.id) connectedTopicIds.add(e.source_topic_id);
        if (e.target_topic_id !== topicData.id) connectedTopicIds.add(e.target_topic_id);
    });
    const connectedTopics = (mapData?.topics || []).filter(
        t => connectedTopicIds.has(t.id) && !t.is_proposition
    );

    const libraryEntry = libraryData?.find(
        entry => entry.topic_id === topicData.id
    );

    const handleStartEdit = () => {
        setEditName(topicData.name.replace(/-/g, ' '));
        setEditDescription(topicData.description || '');
        setIsEditing(true);
    };

    const handleSave = async () => {
        setSaving(true);
        try {
            await onUpdate(topicData.id, {
                name: editName.toLowerCase().replace(/\s+/g, '-'),
                description: editDescription,
            });
            setIsEditing(false);
        } catch (err) {
            console.error('Failed to update topic:', err);
        } finally {
            setSaving(false);
        }
    };

    const handleDelete = async () => {
        setDeleting(true);
        try {
            await onDelete(topicData.id);
            setDeleteDialogOpen(false);
            onClose();
        } catch (err) {
            console.error('Failed to delete topic:', err);
        } finally {
            setDeleting(false);
        }
    };

    const handleExplore = async () => {
        setExploring(true);
        try {
            await onExplore(topicData.id);
        } catch (err) {
            console.error('Failed to explore topic:', err);
        } finally {
            setExploring(false);
        }
    };

    return (
        <>
            <Box
                sx={{
                    width: 320,
                    height: '100%',
                    display: 'flex',
                    flexDirection: 'column',
                    borderLeft: '1px solid',
                    borderColor: alpha(theme.palette.divider, 0.1),
                    bgcolor: alpha(theme.palette.background.paper, isDark ? 0.3 : 0.5),
                    backdropFilter: 'blur(12px)',
                    overflow: 'hidden',
                }}
            >
                {/* ── Header ──────────────────────────────────── */}
                <Box sx={{
                    px: 2, py: 1.5,
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                    borderBottom: '1px solid',
                    borderColor: alpha(theme.palette.divider, 0.08),
                }}>
                    <Typography sx={{ fontWeight: 700, fontSize: '0.85rem', color: 'text.primary' }}>
                        Topic Details
                    </Typography>
                    <IconButton onClick={onClose} size="small" sx={{ borderRadius: 1 }}>
                        <CloseIcon sx={{ fontSize: 16 }} />
                    </IconButton>
                </Box>

                {/* ── Content ─────────────────────────────────── */}
                <Box sx={{ flex: 1, overflow: 'auto', px: 2, py: 2, display: 'flex', flexDirection: 'column', gap: 2 }}>
                    {/* Name */}
                    {isEditing ? (
                        <TextField
                            label="Name"
                            value={editName}
                            onChange={e => setEditName(e.target.value)}
                            size="small"
                            fullWidth
                            sx={{ '& .MuiOutlinedInput-root': { borderRadius: 1.5 } }}
                        />
                    ) : (
                        <Box>
                            <Typography sx={{ fontSize: '0.65rem', fontWeight: 600, color: alpha(theme.palette.text.secondary, 0.5), textTransform: 'uppercase', letterSpacing: '0.05em', mb: 0.5 }}>
                                Name
                            </Typography>
                            <Typography sx={{ fontWeight: 700, fontSize: '1rem', color: 'text.primary' }}>
                                {topicData.name.replace(/-/g, ' ')}
                            </Typography>
                        </Box>
                    )}

                    {/* Confidence */}
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <ConfidenceIcon sx={{ fontSize: 14, color: alpha(theme.palette.primary.light, 0.6) }} />
                        <Typography sx={{ fontSize: '0.75rem', color: 'text.secondary' }}>
                            Confidence: {Math.round((topicData.confidence || 0) * 100)}%
                        </Typography>
                    </Box>

                    {/* Description */}
                    {isEditing ? (
                        <TextField
                            label="Description"
                            value={editDescription}
                            onChange={e => setEditDescription(e.target.value)}
                            size="small"
                            multiline
                            minRows={3}
                            fullWidth
                            sx={{ '& .MuiOutlinedInput-root': { borderRadius: 1.5 } }}
                        />
                    ) : (
                        <Box>
                            <Typography sx={{ fontSize: '0.65rem', fontWeight: 600, color: alpha(theme.palette.text.secondary, 0.5), textTransform: 'uppercase', letterSpacing: '0.05em', mb: 0.5 }}>
                                Description
                            </Typography>
                            <Typography sx={{ fontSize: '0.8rem', color: alpha(theme.palette.text.primary, 0.7), lineHeight: 1.6 }}>
                                {topicData.description || 'No description yet.'}
                            </Typography>
                        </Box>
                    )}

                    <Divider sx={{ borderColor: alpha(theme.palette.divider, 0.06) }} />

                    {/* Library Entry */}
                    <Box>
                        <Typography sx={{ fontSize: '0.65rem', fontWeight: 600, color: alpha(theme.palette.text.secondary, 0.5), textTransform: 'uppercase', letterSpacing: '0.05em', mb: 1 }}>
                            Library
                        </Typography>
                        {libraryEntry ? (
                            <Button
                                variant="outlined"
                                size="small"
                                startIcon={<DescriptionIcon sx={{ fontSize: 14 }} />}
                                onClick={onSwitchToLibrary}
                                sx={{
                                    borderRadius: 1.5,
                                    textTransform: 'none',
                                    fontSize: '0.75rem',
                                    borderColor: alpha(theme.palette.primary.main, 0.2),
                                    color: 'primary.light',
                                }}
                            >
                                View library entry
                            </Button>
                        ) : (
                            <Typography sx={{ fontSize: '0.75rem', color: alpha(theme.palette.text.secondary, 0.5) }}>
                                No library entry yet. Explore this topic to generate one.
                            </Typography>
                        )}
                    </Box>

                    <Divider sx={{ borderColor: alpha(theme.palette.divider, 0.06) }} />

                    {/* Connected Topics */}
                    {connectedTopics.length > 0 && (
                        <Box>
                            <Typography sx={{ fontSize: '0.65rem', fontWeight: 600, color: alpha(theme.palette.text.secondary, 0.5), textTransform: 'uppercase', letterSpacing: '0.05em', mb: 1 }}>
                                Connected Topics
                            </Typography>
                            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.75 }}>
                                {connectedTopics.map(ct => (
                                    <Chip
                                        key={ct.id}
                                        label={ct.name.replace(/-/g, ' ')}
                                        size="small"
                                        sx={{
                                            height: 24, fontSize: '0.7rem', borderRadius: '6px',
                                            bgcolor: alpha(theme.palette.primary.main, 0.08),
                                            color: 'primary.light',
                                        }}
                                    />
                                ))}
                            </Box>
                        </Box>
                    )}
                </Box>

                {/* ── Actions ─────────────────────────────────── */}
                <Box sx={{
                    px: 2, py: 1.5,
                    borderTop: '1px solid',
                    borderColor: alpha(theme.palette.divider, 0.08),
                    display: 'flex', gap: 1,
                }}>
                    {isEditing ? (
                        <>
                            <Button
                                fullWidth
                                size="small"
                                variant="contained"
                                startIcon={saving ? <CircularProgress size={14} /> : <CheckIcon sx={{ fontSize: 16 }} />}
                                onClick={handleSave}
                                disabled={saving}
                                sx={{ borderRadius: 1.5, textTransform: 'none', fontWeight: 600 }}
                            >
                                Save
                            </Button>
                            <Button
                                size="small"
                                variant="outlined"
                                onClick={() => setIsEditing(false)}
                                sx={{ borderRadius: 1.5, textTransform: 'none', minWidth: 0 }}
                            >
                                <CloseIcon sx={{ fontSize: 16 }} />
                            </Button>
                        </>
                    ) : (
                        <>
                            <Tooltip title="Edit topic" arrow>
                                <IconButton onClick={handleStartEdit} size="small" sx={{ borderRadius: 1 }}>
                                    <EditIcon sx={{ fontSize: 16 }} />
                                </IconButton>
                            </Tooltip>
                            <Tooltip title="Explore (generate library entry)" arrow>
                                <IconButton
                                    onClick={handleExplore}
                                    disabled={exploring}
                                    size="small"
                                    sx={{ borderRadius: 1, color: 'primary.light' }}
                                >
                                    {exploring ? <CircularProgress size={16} /> : <ExploreIcon sx={{ fontSize: 16 }} />}
                                </IconButton>
                            </Tooltip>
                            <Box sx={{ flex: 1 }} />
                            <Tooltip title="Delete topic" arrow>
                                <IconButton
                                    onClick={() => setDeleteDialogOpen(true)}
                                    size="small"
                                    sx={{ borderRadius: 1, color: alpha(theme.palette.error.light, 0.6) }}
                                >
                                    <DeleteIcon sx={{ fontSize: 16 }} />
                                </IconButton>
                            </Tooltip>
                        </>
                    )}
                </Box>
            </Box>

            {/* ── Delete Confirmation Dialog ────────────────── */}
            <Dialog open={deleteDialogOpen} onClose={() => setDeleteDialogOpen(false)} maxWidth="xs">
                <DialogTitle sx={{ fontWeight: 700, fontSize: '1rem' }}>
                    Delete topic?
                </DialogTitle>
                <DialogContent>
                    <DialogContentText sx={{ fontSize: '0.8rem' }}>
                        This will remove "{topicData.name.replace(/-/g, ' ')}" from the map, including its library entry and connections.
                    </DialogContentText>
                </DialogContent>
                <DialogActions sx={{ px: 2.5, pb: 2, gap: 1 }}>
                    <Button
                        onClick={() => setDeleteDialogOpen(false)}
                        disabled={deleting}
                        sx={{ borderRadius: 1.5, textTransform: 'none', fontSize: '0.8rem' }}
                    >
                        Cancel
                    </Button>
                    <Button
                        onClick={handleDelete}
                        disabled={deleting}
                        variant="contained"
                        color="error"
                        sx={{ borderRadius: 1.5, textTransform: 'none', fontSize: '0.8rem', fontWeight: 600 }}
                    >
                        {deleting ? 'Deleting...' : 'Delete'}
                    </Button>
                </DialogActions>
            </Dialog>
        </>
    );
}

export default TopicDetailPanel;
