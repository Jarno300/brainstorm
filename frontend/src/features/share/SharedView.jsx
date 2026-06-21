import { useState, useEffect } from 'react';
import {
    Box, Typography, Chip, alpha, CircularProgress,
    ThemeProvider, CssBaseline, IconButton, Tooltip,
} from '@mui/material';
import {
    ArrowBack as BackIcon,
    Public as PublicIcon,
} from '@mui/icons-material';
import { createAppTheme } from '../../theme';
import api from '../../api';
import { formatLabel } from '../canvas/canvasUtils';

/**
 * SharedView — public read-only view of a published brainstorm.
 *
 * Renders at /shared/:token with no auth required.
 * Shows the canvas (static), library contents, and chat transcript.
 */

const CARD_COLORS = [
    '#fbbf24', '#5eead4', '#a78bfa', '#fb7185',
    '#38bdf8', '#34d399', '#f472b6', '#f97316',
];

function getColor(index) {
    return CARD_COLORS[index % CARD_COLORS.length];
}

export default function SharedView() {
    const token = window.location.pathname.split('/shared/')[1]?.split('?')[0];
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [mode, setMode] = useState(() =>
        window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
    );
    const theme = createAppTheme(mode, mode === 'dark' ? 0 : 1);

    useEffect(() => {
        if (!token) {
            setError('No share token provided.');
            setLoading(false);
            return;
        }
        api.get(`/share/${token}`)
            .then(res => { setData(res.data); setLoading(false); })
            .catch(err => {
                setError(err?.response?.status === 404
                    ? 'This brainstorm is not available or has been unpublished.'
                    : 'Failed to load brainstorm.');
                setLoading(false);
            });
    }, [token]);

    const toggleTheme = () => setMode(m => m === 'dark' ? 'light' : 'dark');

    if (loading) {
        return (
            <ThemeProvider theme={theme}>
                <CssBaseline />
                <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', flexDirection: 'column', gap: 2 }}>
                    <CircularProgress size={32} sx={{ color: alpha(theme.palette.primary.main, 0.6) }} />
                    <Typography sx={{ fontSize: '0.85rem', color: 'text.secondary' }}>Loading shared brainstorm...</Typography>
                </Box>
            </ThemeProvider>
        );
    }

    if (error) {
        return (
            <ThemeProvider theme={theme}>
                <CssBaseline />
                <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', flexDirection: 'column', gap: 2, px: 3 }}>
                    <PublicIcon sx={{ fontSize: 48, color: alpha(theme.palette.text.secondary, 0.3) }} />
                    <Typography sx={{ fontSize: '1.1rem', fontWeight: 500, color: 'text.primary', textAlign: 'center' }}>
                        {error}
                    </Typography>
                    <Typography sx={{ fontSize: '0.8rem', color: 'text.secondary', textAlign: 'center' }}>
                        Ask the owner to share it again, or create your own brainstorm.
                    </Typography>
                </Box>
            </ThemeProvider>
        );
    }

    const topics = data?.topics || [];
    const edges = data?.edges || [];
    const libraries = data?.libraries || [];

    // Group library entries by folder
    const folders = {};
    for (const lib of libraries) {
        const folder = lib.folder_name || 'Uncategorized';
        if (!folders[folder]) folders[folder] = [];
        folders[folder].push(lib);
    }

    return (
        <ThemeProvider theme={theme}>
            <CssBaseline />
            <Box sx={{ display: 'flex', flexDirection: 'column', height: '100vh', bgcolor: 'background.default' }}>
                {/* Header */}
                <Box sx={(t) => ({
                    px: 3, py: 1.5,
                    display: 'flex', alignItems: 'center', gap: 1.5,
                    borderBottom: '1px solid', borderColor: alpha(t.palette.divider, 0.1),
                    bgcolor: alpha(t.palette.background.paper, 0.3),
                    backdropFilter: 'blur(12px)',
                })}>
                    <IconButton size="small" onClick={toggleTheme} sx={{ borderRadius: 1 }}>
                        <BackIcon sx={{ fontSize: 16 }} />
                    </IconButton>
                    <PublicIcon sx={{ fontSize: 14, color: 'text.secondary' }} />
                    <Typography sx={{ fontSize: '0.9rem', fontWeight: 600 }}>
                        {data?.title || 'Shared Brainstorm'}
                    </Typography>
                    {data?.summary && (
                        <Typography sx={{ fontSize: '0.75rem', color: 'text.secondary', ml: 1, maxWidth: 400, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            {data.summary}
                        </Typography>
                    )}
                    <Chip label="Read only" size="small"
                        sx={(t) => ({ ml: 'auto', fontSize: '0.65rem', height: 20, bgcolor: alpha(t.palette.warning.main, 0.1), color: t.palette.warning.light })} />
                </Box>

                {/* Body: Canvas + Library side-by-side */}
                <Box sx={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
                    {/* Canvas area */}
                    <Box sx={{ flex: 3, position: 'relative', overflow: 'auto', p: 3 }}>
                        <svg style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', pointerEvents: 'none', zIndex: 0 }}>
                            {edges.map((e, i) => {
                                const src = topics.find(t => t.id === e.source);
                                const tgt = topics.find(t => t.id === e.target);
                                if (!src || !tgt) return null;
                                const sx = (src.position_x || 100 + i * 240);
                                const sy = (src.position_y || 200 + (i % 3) * 160);
                                const tx = (tgt.position_x || 340 + i * 240);
                                const ty = (tgt.position_y || 200 + ((i + 1) % 3) * 160);
                                return (
                                    <line key={i}
                                        x1={sx + 110} y1={sy + 45}
                                        x2={tx + 110} y2={ty + 45}
                                        stroke={alpha(theme.palette.mode === 'dark' ? '#ffffff' : '#000000', 0.1)}
                                        strokeWidth={2}
                                    />
                                );
                            })}
                        </svg>
                        {topics.map((t, i) => {
                            const color = getColor(i);
                            return (
                                <Box key={t.id} sx={{
                                    position: 'absolute',
                                    left: t.position_x || 100 + i * 260,
                                    top: t.position_y || 200 + (i % 3) * 180,
                                    width: 220, minHeight: 80,
                                    p: 2, borderRadius: 2,
                                    border: '1.5px solid',
                                    borderColor: alpha(color, 0.2),
                                    borderLeft: `4px solid ${color}`,
                                    bgcolor: alpha(theme.palette.background.paper, 0.7),
                                    backdropFilter: 'blur(8px)',
                                    boxShadow: `0 2px 12px ${alpha(color, 0.06)}`,
                                }}>
                                    <Typography sx={{ fontSize: '0.8rem', fontWeight: 600, color: 'text.primary', mb: 0.5 }}>
                                        {formatLabel(t.name)}
                                    </Typography>
                                    {t.description && (
                                        <Typography sx={{ fontSize: '0.7rem', color: 'text.secondary', lineHeight: 1.4 }}>
                                            {t.description}
                                        </Typography>
                                    )}
                                    <Chip label={`${Math.round((t.confidence || 0) * 100)}%`} size="small"
                                        sx={{ mt: 1, fontSize: '0.6rem', height: 18, bgcolor: alpha(color, 0.1), color }} />
                                </Box>
                            );
                        })}
                        {topics.length === 0 && (
                            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
                                <Typography sx={{ color: 'text.secondary', fontSize: '0.85rem' }}>No topics in this brainstorm.</Typography>
                            </Box>
                        )}
                    </Box>

                    {/* Library panel */}
                    <Box sx={(t) => ({
                        flex: 1, maxWidth: 380,
                        borderLeft: '1px solid', borderColor: alpha(t.palette.divider, 0.1),
                        overflow: 'auto', p: 2.5,
                        bgcolor: alpha(t.palette.background.paper, 0.2),
                    })}>
                        <Typography sx={{ fontSize: '0.75rem', fontWeight: 600, color: 'text.secondary', textTransform: 'uppercase', letterSpacing: '0.05em', mb: 2 }}>
                            Library ({libraries.length} entries)
                        </Typography>
                        {Object.entries(folders).map(([folderName, entries]) => (
                            <Box key={folderName} sx={{ mb: 2.5 }}>
                                <Typography sx={{ fontSize: '0.75rem', fontWeight: 600, color: 'text.primary', mb: 0.75 }}>
                                    📁 {formatLabel(folderName)}
                                </Typography>
                                {entries.map(entry => (
                                    <Box key={entry.file_name} sx={(t) => ({
                                        p: 1.5, mb: 0.75, borderRadius: 1.5,
                                        border: '1px solid', borderColor: alpha(t.palette.divider, 0.08),
                                        bgcolor: alpha(t.palette.background.paper, 0.4),
                                    })}>
                                        <Typography sx={{ fontSize: '0.72rem', fontWeight: 500, mb: 0.5 }}>
                                            {entry.file_name.replace('.md', '').replace(/_/g, ' ')}
                                        </Typography>
                                        <Typography sx={{
                                            fontSize: '0.68rem', color: 'text.secondary', lineHeight: 1.5,
                                            whiteSpace: 'pre-wrap', maxHeight: 120, overflow: 'hidden',
                                        }}>
                                            {(entry.content || '').slice(0, 400)}
                                            {(entry.content || '').length > 400 ? '...' : ''}
                                        </Typography>
                                    </Box>
                                ))}
                            </Box>
                        ))}
                        {libraries.length === 0 && (
                            <Typography sx={{ fontSize: '0.78rem', color: 'text.secondary' }}>No library entries.</Typography>
                        )}
                    </Box>
                </Box>
            </Box>
        </ThemeProvider>
    );
}
