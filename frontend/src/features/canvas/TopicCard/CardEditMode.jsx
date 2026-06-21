import { useRef, useState, useCallback } from 'react';
import { Box, Typography, IconButton, alpha, useTheme, TextField, CircularProgress, LinearProgress } from '@mui/material';
import { Add as AddIcon, AutoAwesome as HubIcon, Close as CloseIcon } from '@mui/icons-material';
import MarkdownRenderer from '../../../components/MarkdownRenderer';
import { formatLabel } from '../canvasUtils';

function CardEditMode({ topic, brainstormingId, color, generating, generatedContent, onUpdate, onOutlineChange, onGenerate }) {
    const theme = useTheme();
    const titleInputRef = useRef(null);
    const [newSectionTitle, setNewSectionTitle] = useState('');
    const outlineSections = (topic.outline && Array.isArray(topic.outline)) ? topic.outline : [];

    const handleTitleSave = useCallback(() => {
        const input = titleInputRef.current;
        if (!input) return;
        const trimmed = (input.value || '').trim();
        if (trimmed && trimmed !== formatLabel(topic.name)) {
            onUpdate?.(topic.id, { name: trimmed.toLowerCase().replace(/\s+/g, '-') });
        } else {
            input.value = formatLabel(topic.name);
        }
    }, [topic, onUpdate]);

    const handleAddSection = useCallback(() => {
        const title = newSectionTitle.trim();
        if (!title) return;
        const updated = [...(topic.outline || []), { title }];
        onOutlineChange?.(brainstormingId, topic.id, updated);
        setNewSectionTitle('');
    }, [newSectionTitle, topic, onOutlineChange, brainstormingId]);

    const handleRemoveSection = useCallback((index) => {
        const updated = (topic.outline || []).filter((_, i) => i !== index);
        onOutlineChange?.(brainstormingId, topic.id, updated.length > 0 ? updated : null);
    }, [topic, onOutlineChange, brainstormingId]);

    const handleGenerate = useCallback((e) => {
        e.stopPropagation();
        onGenerate?.(brainstormingId, topic.id);
    }, [brainstormingId, topic.id, onGenerate]);

    return (
        <Box sx={{ pr: 4 }}>
            {/* Editable title */}
            <Box
                component="input"
                ref={titleInputRef}
                defaultValue={formatLabel(topic.name)}
                onBlur={handleTitleSave}
                onKeyDown={(e) => { if (e.key === 'Enter') e.target.blur(); }}
                onClick={(e) => e.stopPropagation()}
                onMouseDown={(e) => e.stopPropagation()}
                placeholder="Topic title..."
                sx={(theme) => ({
                    width: '100%', border: 'none', outline: 'none', background: 'transparent',
                    fontSize: '0.85rem', fontWeight: 700, color: theme.palette.text.primary,
                    lineHeight: 1.3, mb: 1.5, py: 0, px: 0, fontFamily: 'inherit',
                    '&::placeholder': { color: alpha(theme.palette.text.secondary, 0.4), opacity: 1 },
                })}
            />

            {/* Section list */}
            {outlineSections.map((section, i) => (
                <Box key={i} sx={{
                    display: 'flex', alignItems: 'center', gap: 0.5, mb: 0.75,
                    pl: 1.5, borderLeft: `2px solid ${alpha(color, 0.2)}`,
                }}>
                    <Typography sx={{ flex: 1, fontSize: '0.72rem', fontWeight: 500, color: alpha(theme.palette.text.secondary, 0.7), py: 0.25 }}>
                        {section.title}
                    </Typography>
                    <IconButton size="small"
                        onClick={(e) => { e.stopPropagation(); handleRemoveSection(i); }}
                        onMouseDown={(e) => e.stopPropagation()}
                        className="card-action"
                        sx={{ width: 18, height: 18, borderRadius: 0.5, opacity: 0.4, '&:hover': { opacity: 0.8, bgcolor: 'rgba(211,47,47,0.1)' } }}
                    >
                        <CloseIcon sx={{ fontSize: 10 }} />
                    </IconButton>
                </Box>
            ))}

            {/* Add section input */}
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mt: 0.5 }}>
                <TextField fullWidth variant="standard" size="small"
                    value={newSectionTitle}
                    onChange={(e) => setNewSectionTitle(e.target.value)}
                    onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); handleAddSection(); } }}
                    onClick={(e) => e.stopPropagation()}
                    onMouseDown={(e) => e.stopPropagation()}
                    placeholder="+ Add section..."
                    slotProps={{
                        input: {
                            disableUnderline: true,
                            sx: (theme) => ({
                                fontSize: '0.7rem', fontWeight: 500,
                                color: alpha(theme.palette.text.secondary, 0.5), py: 0.25,
                                '& input::placeholder': { color: alpha(theme.palette.text.secondary, 0.35), opacity: 1 },
                            }),
                        },
                    }}
                />
                {newSectionTitle.trim() && (
                    <IconButton size="small"
                        onClick={(e) => { e.stopPropagation(); handleAddSection(); }}
                        onMouseDown={(e) => e.stopPropagation()}
                        className="card-action"
                        sx={{ width: 22, height: 22, borderRadius: 0.5, bgcolor: alpha(color, 0.12), '&:hover': { bgcolor: alpha(color, 0.25) } }}
                    >
                        <AddIcon sx={{ fontSize: 14, color }} />
                    </IconButton>
                )}
            </Box>

            {/* Streaming preview */}
            {generating && generatedContent ? (
                <Box sx={(theme) => ({ mt: 2, px: 1.5, py: 1.5, borderRadius: 1, bgcolor: alpha(theme.palette.background.default, 0.5), maxHeight: 160, overflow: 'auto' })}>
                    <MarkdownRenderer content={generatedContent} variant="card" />
                    <LinearProgress sx={{ mt: 1, height: 2, borderRadius: 1 }} />
                </Box>
            ) : generating ? (
                <Box sx={{ mt: 2, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 1, py: 1 }}>
                    <CircularProgress size={14} sx={(t) => ({ color: t.palette.primary.light })} />
                    <Typography sx={(theme) => ({ fontSize: '0.68rem', color: alpha(theme.palette.text.secondary, 0.5), fontWeight: 500 })}>
                        Generating...
                    </Typography>
                </Box>
            ) : null}

            {/* Generate button */}
            <Box sx={(theme) => ({ mt: 2.5, pt: 1.5, borderTop: `1px solid ${alpha(theme.palette.divider, 0.15)}`, display: 'flex', justifyContent: 'center' })}>
                <Box className="card-action"
                    onClick={generating ? undefined : handleGenerate}
                    sx={(theme) => ({
                        display: 'inline-flex', alignItems: 'center', gap: 0.75, px: 2, py: 0.6, borderRadius: 1.5,
                        bgcolor: generating ? alpha(theme.palette.action.disabled, 0.1) : alpha(theme.palette.primary.main, 0.12),
                        border: '1px solid', borderColor: generating ? 'transparent' : alpha(theme.palette.primary.main, 0.2),
                        cursor: generating ? 'default' : 'pointer', transition: 'all 0.15s ease',
                        opacity: generating ? 0.6 : 1, position: 'relative', overflow: 'hidden',
                        '@keyframes shimmer': { '0%': { transform: 'translateX(-100%)' }, '100%': { transform: 'translateX(100%)' } },
                        '&::after': generating ? {} : { content: '""', position: 'absolute', inset: 0, background: `linear-gradient(90deg, transparent 0%, ${alpha(theme.palette.primary.main, 0.08)} 40%, ${alpha(theme.palette.primary.main, 0.12)} 50%, ${alpha(theme.palette.primary.main, 0.08)} 60%, transparent 100%)`, animation: 'shimmer 2.8s ease-in-out infinite' },
                        '&:hover': generating ? {} : { bgcolor: alpha(theme.palette.primary.main, 0.2), borderColor: alpha(theme.palette.primary.main, 0.35) },
                    })}
                >
                    <HubIcon sx={{ fontSize: 13, color: theme.palette.primary.light }} />
                    <Typography sx={{ fontSize: '0.7rem', fontWeight: 700, color: theme.palette.primary.light, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                        Generate
                    </Typography>
                </Box>
            </Box>
        </Box>
    );
}

export default CardEditMode;
