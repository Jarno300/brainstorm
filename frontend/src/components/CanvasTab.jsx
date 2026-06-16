import { useRef, useState, useCallback, useEffect, useMemo, memo } from 'react';
import {
    Box, Typography, IconButton, Tooltip, Chip, alpha, useTheme, TextField, CircularProgress, LinearProgress,
} from '@mui/material';
import {
    Add as AddIcon,
    Refresh as RefreshIcon,
    AutoAwesome as HubIcon,
    Delete as DeleteIcon,
    Close as CloseIcon,
    Link as LinkIcon,
} from '@mui/icons-material';
import { createEdge as apiCreateEdge, deleteEdge as apiDeleteEdge } from '../api';
import MarkdownRenderer from './MarkdownRenderer';
import logger from '../utils/logger';

// ─── Helpers ──────────────────────────────────────────────────

function formatLabel(value) {
    return String(value || '')
        .replace(/-/g, ' ')
        .replace(/\b\w/g, c => c.toUpperCase());
}

function getImportanceColor(importance, theme) {
    const isDark = theme.palette.mode === 'dark';
    const colors = {
        core: isDark ? '#fbbf24' : '#b45309',
        high: isDark ? '#5eead4' : '#0f766e',
        medium: isDark ? '#a78bfa' : '#7c3aed',
        low: isDark ? '#94a3b8' : '#475569',
    };
    return colors[importance] || colors.low;
}

function computeImportance(confidence) {
    if (confidence >= 0.8) return 'core';
    if (confidence >= 0.6) return 'high';
    if (confidence >= 0.3) return 'medium';
    return 'low';
}

function randomOffset(seed) {
    const angle = ((seed * 137.5) % 360) * (Math.PI / 180);
    const dist = 180 + (seed % 3) * 60;
    return { x: Math.cos(angle) * dist, y: Math.sin(angle) * dist };
}

function getCardCenter(topic) {
    return {
        x: (topic.position_x || 0) + 90,
        y: (topic.position_y || 0) + 35,
    };
}

// Card rectangle — uses DOM for real height, falls back to 90px estimate
function getCardRect(topic) {
    const el = document.querySelector(`[data-topic-id="${topic.id}"]`);
    const w = el?.offsetWidth || 220;
    const h = el?.offsetHeight || 90;
    return {
        x: topic.position_x || 0,
        y: topic.position_y || 0,
        w,
        h,
    };
}

// 4 anchor positions for a card: top, bottom, left, right
function getAnchors(topic) {
    const r = getCardRect(topic);
    return [
        { side: 'top',    x: r.x + r.w / 2, y: r.y },
        { side: 'bottom', x: r.x + r.w / 2, y: r.y + r.h },
        { side: 'left',   x: r.x,           y: r.y + r.h / 2 },
        { side: 'right',  x: r.x + r.w,     y: r.y + r.h / 2 },
    ];
}

/** Find the closest anchor pair between two cards. Returns { ax, ay, bx, by }. */
function closestAnchors(topicA, topicB) {
    const anchorsA = getAnchors(topicA);
    const anchorsB = getAnchors(topicB);
    let bestDist = Infinity;
    let bestA = anchorsA[0];
    let bestB = anchorsB[0];
    for (const a of anchorsA) {
        for (const b of anchorsB) {
            const d = (a.x - b.x) ** 2 + (a.y - b.y) ** 2;
            if (d < bestDist) {
                bestDist = d;
                bestA = a;
                bestB = b;
            }
        }
    }
    return { ax: bestA.x, ay: bestA.y, bx: bestB.x, by: bestB.y };
}

// ─── Manual Edge Lines ────────────────────────────────────────

function EdgeLines({ edges, topics, onDeleteEdge, brainstormingId, onExploreEdge }) {
    const theme = useTheme();
    const [hoveredEdge, setHoveredEdge] = useState(null);
    const topicMap = {};
    topics.forEach(t => { topicMap[t.id] = t; });
    const isConnectionCard = (id) => {
        const t = topicMap[id];
        return t?.name?.endsWith('-connection');
    };

    return (
        <svg style={{
            position: 'absolute', inset: 0,
            pointerEvents: 'none', zIndex: 1,
            width: '100%', height: '100%',
        }}>
            {edges.map(edge => {
                const source = topicMap[edge.source_topic_id];
                const target = topicMap[edge.target_topic_id];
                if (!source || !target) return null;

                const pts = closestAnchors(source, target);
                const s = { x: pts.ax, y: pts.ay };
                const t = { x: pts.bx, y: pts.by };
                const midX = (s.x + t.x) / 2;
                const midY = (s.y + t.y) / 2;
                const linkedToConnection = isConnectionCard(edge.source_topic_id) || isConnectionCard(edge.target_topic_id);

                return (
                    <g key={edge.id} style={{ pointerEvents: 'auto' }}
                        data-edge-id={edge.id}
                        data-edge-from={edge.source_topic_id}
                        data-edge-to={edge.target_topic_id}
                        onMouseEnter={() => setHoveredEdge(edge.id)}
                        onMouseLeave={() => setHoveredEdge(null)}
                    >
                        {/* Visible line — highlights on hover */}
                        <line data-line="visible"
                            x1={s.x} y1={s.y} x2={t.x} y2={t.y}
                            stroke={hoveredEdge === edge.id ? alpha(theme.palette.primary.light, 0.6) : alpha(theme.palette.primary.light, 0.3)}
                            strokeWidth={hoveredEdge === edge.id ? 3 : 2}
                            style={{ pointerEvents: 'none', transition: 'stroke 0.15s, stroke-width 0.15s' }}
                        />
                        {/* Invisible wide hit area */}
                        <line
                            x1={s.x} y1={s.y} x2={t.x} y2={t.y}
                            stroke="transparent"
                            strokeWidth={16}
                            style={{ cursor: 'pointer' }}
                        />
                        {/* Action buttons on hover */}
                        {hoveredEdge === edge.id && (
                            <>
                                {/* Explore button — hidden when edge connects a connection card */}
                                {!linkedToConnection && (
                                    <Tooltip title={`Explore connection between ${formatLabel(source.name)} and ${formatLabel(target.name)}`} arrow placement="top">
                                        <foreignObject
                                            x={midX - 34} y={midY - 14} width={28} height={28}
                                            style={{ pointerEvents: 'auto' }}
                                        >
                                        <Box
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                onExploreEdge?.(edge.source_topic_id, edge.target_topic_id, midX, midY);
                                                setHoveredEdge(null);
                                            }}
                                            sx={{
                                                width: 28, height: 28, borderRadius: '50%',
                                                bgcolor: alpha(theme.palette.primary.main, 0.85),
                                                display: 'flex', alignItems: 'center', justifyContent: 'center',
                                                cursor: 'pointer',
                                                '&:hover': { bgcolor: theme.palette.primary.main },
                                            }}
                                        >
                                            <HubIcon sx={{ fontSize: 14, color: '#fff' }} />
                                        </Box>
                                    </foreignObject>
                                    </Tooltip>
                                )}
                                {/* Delete button */}
                                <foreignObject
                                    x={linkedToConnection ? midX - 14 : midX + 6} y={midY - 14} width={28} height={28}
                                    style={{ pointerEvents: 'auto' }}
                                >
                                    <Box
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            onDeleteEdge(edge);
                                            setHoveredEdge(null);
                                        }}
                                        sx={{
                                            width: 28, height: 28, borderRadius: '50%',
                                            bgcolor: alpha(theme.palette.error.main, 0.9),
                                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                                            cursor: 'pointer',
                                            '&:hover': { bgcolor: theme.palette.error.main },
                                        }}
                                    >
                                        <DeleteIcon sx={{ fontSize: 14, color: '#fff' }} />
                                    </Box>
                                </foreignObject>
                            </>
                        )}
                    </g>
                );
            })}
        </svg>
    );
}

const CARD_COLORS = [
    { key: 'amber', light: '#f59e0b', dark: '#fbbf24' },
    { key: 'teal', light: '#0d9488', dark: '#5eead4' },
    { key: 'violet', light: '#7c3aed', dark: '#a78bfa' },
    { key: 'rose', light: '#e11d48', dark: '#fb7185' },
    { key: 'sky', light: '#0284c7', dark: '#38bdf8' },
    { key: 'emerald', light: '#059669', dark: '#34d399' },
];

const TopicCard = memo(function TopicCard({ topic, isSelected, exploringName, libraryEntry, onSelect, onDragStart, onLinkStart, onDelete, onUpdate, brainstormingId, onGenerate, onOutlineChange, generating, generatedContent }) {
    const theme = useTheme();
    const isDark = theme.palette.mode === 'dark';
    const importance = topic.importance || computeImportance(topic.confidence);
    const defaultColor = getImportanceColor(importance, theme);
    const [customColor, setCustomColor] = useState(null);
    const color = customColor || defaultColor;
    const [hovered, setHovered] = useState(false);
    const [showColorPicker, setShowColorPicker] = useState(false);
    const [cardSize, setCardSize] = useState({ w: 220, h: null });

    // Edit mode state
    const titleInputRef = useRef(null);
    const [newSectionTitle, setNewSectionTitle] = useState('');

    const cardW = cardSize.w;

    // Edit mode: card has no library entry (no generated content yet)
    const isEditMode = !libraryEntry;
    const outlineSections = (topic.outline && Array.isArray(topic.outline)) ? topic.outline : [];
    const isConnectionCard = topic.name.endsWith('-connection');

    // ── Library sections ──────────────────────────────────

    const TAXONOMY_SECTIONS = ['parent topics', 'child topics', 'related topics'];

    const librarySections = useMemo(() => {
        if (!libraryEntry?.content) return [];
        const text = libraryEntry.content.trim();
        if (!text) return [];

        const sections = [];
        const lines = text.split('\n');
        let current = null;
        for (const line of lines) {
            if (line.match(/^##\s+/)) {
                if (current) sections.push(current);
                current = { title: line.replace(/^##\s*/, '').trim(), body: '' };
            } else if (current && line.trim()) {
                current.body += (current.body ? '\n' : '') + line.trim();
            } else if (current) {
                current.body += '\n';
            }
        }
        if (current) sections.push(current);

        // Filter out taxonomy sections — they're shown as clickable pills instead
        const contentSections = sections.filter(
            s => !TAXONOMY_SECTIONS.includes(s.title.toLowerCase())
        );

        // Fallback: no ## headings — split first paragraph as a single section
        if (contentSections.length === 0 && sections.length === 0) {
            const firstPara = text.split('\n\n')[0] || text.slice(0, 150);
            contentSections.push({ title: 'Overview', body: firstPara });
        }
        return contentSections;
    }, [libraryEntry]);

    // Summary blockquote from library, or topic.description
    const summaryText = (() => {
        if (libraryEntry?.content) {
            const m = libraryEntry.content.match(/^>\s*(.+)/m);
            if (m) return m[1].trim();
        }
        return topic.description || '';
    })();

    // ── Outline editing handlers ─────────────────────────

    const handleTitleSave = useCallback(() => {
        const input = titleInputRef.current;
        if (!input) return;
        const trimmed = (input.value || '').trim();
        if (trimmed && trimmed !== formatLabel(topic.name)) {
            onUpdate?.(topic.id, { name: trimmed.toLowerCase().replace(/\s+/g, '-') });
        } else {
            // Reset to current topic name if unchanged or empty
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

    // ── Resize drag ────────────────────────────────────────

    const handleResizeStart = useCallback((e) => {
        e.stopPropagation(); e.preventDefault();
        const startX = e.clientX;
        const startW = cardW;
        const onMove = (ev) => setCardSize({ w: Math.max(200, Math.min(500, startW + (ev.clientX - startX))), h: null });
        const onUp = () => { window.removeEventListener('mousemove', onMove); window.removeEventListener('mouseup', onUp); };
        window.addEventListener('mousemove', onMove);
        window.addEventListener('mouseup', onUp);
    }, [cardW]);

    return (
        <Box
            onMouseEnter={() => setHovered(true)}
            onMouseLeave={() => { setHovered(false); setShowColorPicker(false); }}
            onMouseDown={(e) => {
                if (e.target.closest('.card-action') || e.target.closest('.link-handle') || e.target.closest('.resize-handle')) return;
                onDragStart(e, topic);
            }}
            data-topic-id={topic.id}
            sx={{
                position: 'absolute',
                left: topic.position_x || 0, top: topic.position_y || 0,
                width: cardW,
                px: 2.5, py: 2,
                borderRadius: 2,
                bgcolor: isDark ? alpha(color, 0.06) : alpha('#fff', 0.95),
                border: '1.5px solid',
                borderColor: isSelected ? color : (isDark ? alpha(color, 0.15) : alpha('#e2e8f0', 0.9)),
                cursor: 'grab', userSelect: 'none',
                boxShadow: isSelected
                    ? `0 0 24px ${alpha(color, 0.25)}, 0 8px 24px rgba(0,0,0,0.1)`
                    : `0 2px 8px rgba(0,0,0,0.04), 0 1px 2px rgba(0,0,0,0.03)`,
                '&:hover': {
                    borderColor: alpha(color, 0.4),
                    boxShadow: `0 4px 20px rgba(0,0,0,0.08)`,
                },
                zIndex: isSelected ? 10 : 1,
                pointerEvents: 'auto',
                transition: 'width 0.15s ease',
            }}
        >
            {/* Link handles */}
            {hovered && ['top', 'bottom', 'left', 'right'].map(side => {
                const pos = {
                    top: { top: -7, left: '50%', ml: '-7px' },
                    bottom: { bottom: -7, left: '50%', ml: '-7px' },
                    left: { left: -7, top: '50%', mt: '-7px' },
                    right: { right: -7, top: '50%', mt: '-7px' },
                }[side];
                return (
                    <Box key={side} className="link-handle" onMouseDown={(e) => { e.stopPropagation(); e.preventDefault(); onLinkStart(topic, side, e); }}
                        sx={{
                            position: 'absolute', width: 14, height: 14, borderRadius: '50%',
                            bgcolor: alpha(color, 0.5), border: `2px solid ${color}`,
                            cursor: 'crosshair', zIndex: 20, opacity: 0.7,
                            transition: 'transform 0.15s, opacity 0.15s',
                            '&:hover': { transform: 'scale(1.4)', opacity: 1 },
                            ...pos,
                        }} />
                );
            })}

            {/* Action buttons — top-right, on hover */}
            {hovered && (
                <Box sx={{ position: 'absolute', top: 4, right: 8, display: 'flex', gap: 0.5, zIndex: 25 }}>
                    {/* Color picker */}
                    <Box className="card-action" sx={{ position: 'relative' }}>
                        <Box onClick={() => setShowColorPicker(!showColorPicker)}
                            sx={{
                                width: 18, height: 18, borderRadius: '50%', bgcolor: color, cursor: 'pointer',
                                border: '2px solid', borderColor: alpha(theme.palette.background.paper, 0.6),
                                boxShadow: '0 1px 3px rgba(0,0,0,0.12)',
                            }} />
                        {showColorPicker && (
                            <Box sx={{
                                position: 'absolute', top: 24, right: 0, display: 'flex', gap: 0.5, p: 0.75,
                                borderRadius: 2, bgcolor: alpha(theme.palette.background.paper, 0.97),
                                border: '1px solid', borderColor: alpha(theme.palette.divider, 0.15),
                                boxShadow: '0 4px 16px rgba(0,0,0,0.15)', zIndex: 30,
                            }}>
                                {CARD_COLORS.map(c => (
                                    <Box key={c.key} onClick={() => { setCustomColor(isDark ? c.dark : c.light); setShowColorPicker(false); }}
                                        sx={{
                                            width: 18, height: 18, borderRadius: '50%', bgcolor: isDark ? c.dark : c.light,
                                            cursor: 'pointer',
                                            border: color === (isDark ? c.dark : c.light) ? '2px solid #fff' : '2px solid transparent',
                                            '&:hover': { transform: 'scale(1.15)' },
                                        }} />
                                ))}
                            </Box>
                        )}
                    </Box>

                    {/* Delete */}
                    <Box className="card-action" onClick={(e) => { e.stopPropagation(); onDelete(topic.id); }}
                        sx={{
                            width: 18, height: 18, borderRadius: '50%',
                            bgcolor: alpha(theme.palette.error.main, 0.75),
                            display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer',
                            '&:hover': { bgcolor: theme.palette.error.main },
                        }}>
                        <DeleteIcon sx={{ fontSize: 11, color: '#fff' }} />
                    </Box>
                </Box>
            )}

            {/* ── Card body ─────────────────────────────── */}

            {isEditMode ? (
                /* ── Edit Mode: outline editor ──────────── */
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
                            lineHeight: 1.3, mb: 1.5, py: 0, px: 0,
                            fontFamily: 'inherit',
                            '&::placeholder': { color: alpha(theme.palette.text.secondary, 0.4), opacity: 1 },
                        })}
                    />

                    {/* Section list */}
                    {outlineSections.map((section, i) => (
                        <Box key={i} sx={{
                            display: 'flex', alignItems: 'center', gap: 0.5,
                            mb: 0.75,
                            pl: 1.5, borderLeft: `2px solid ${alpha(color, 0.2)}`,
                        }}>
                            <Typography sx={{
                                flex: 1, fontSize: '0.72rem', fontWeight: 500,
                                color: alpha(theme.palette.text.secondary, 0.7),
                                py: 0.25,
                            }}>
                                {section.title}
                            </Typography>
                            <IconButton
                                size="small"
                                onClick={(e) => { e.stopPropagation(); handleRemoveSection(i); }}
                                onMouseDown={(e) => e.stopPropagation()}
                                className="card-action"
                                sx={{ width: 18, height: 18, borderRadius: 0.5, opacity: 0.4, '&:hover': { opacity: 0.8, bgcolor: alpha(theme.palette.error.main, 0.1) } }}
                            >
                                <CloseIcon sx={{ fontSize: 10 }} />
                            </IconButton>
                        </Box>
                    ))}

                    {/* Add section input */}
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mt: 0.5 }}>
                        <TextField
                            fullWidth
                            variant="standard"
                            size="small"
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
                                        color: alpha(theme.palette.text.secondary, 0.5),
                                        py: 0.25,
                                        '& input::placeholder': { color: alpha(theme.palette.text.secondary, 0.35), opacity: 1 },
                                    }),
                                },
                            }}
                        />
                        {newSectionTitle.trim() && (
                            <IconButton
                                size="small"
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
                        <Box sx={(theme) => ({
                            mt: 2, px: 1.5, py: 1.5, borderRadius: 1,
                            bgcolor: alpha(theme.palette.background.default, 0.5),
                            maxHeight: 160, overflow: 'auto',
                        })}>
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
                    <Box sx={(theme) => ({
                        mt: 2.5, pt: 1.5,
                        borderTop: `1px solid ${alpha(theme.palette.divider, 0.15)}`,
                        display: 'flex', justifyContent: 'center',
                    })}>
                        <Box
                            className="card-action"
                            onClick={generating ? undefined : handleGenerate}
                            sx={(theme) => ({
                                display: 'inline-flex', alignItems: 'center', gap: 0.75,
                                px: 2, py: 0.6, borderRadius: 1.5,
                                bgcolor: generating
                                    ? alpha(theme.palette.action.disabled, 0.1)
                                    : alpha(theme.palette.primary.main, 0.12),
                                border: '1px solid',
                                borderColor: generating
                                    ? 'transparent'
                                    : alpha(theme.palette.primary.main, 0.2),
                                cursor: generating ? 'default' : 'pointer',
                                transition: 'all 0.15s ease',
                                opacity: generating ? 0.6 : 1,
                                '&:hover': generating ? {} : {
                                    bgcolor: alpha(theme.palette.primary.main, 0.2),
                                    borderColor: alpha(theme.palette.primary.main, 0.35),
                                },
                            })}
                        >
                            <HubIcon sx={{ fontSize: 13, color: theme.palette.primary.light }} />
                            <Typography sx={{
                                fontSize: '0.7rem', fontWeight: 700,
                                color: theme.palette.primary.light,
                                textTransform: 'uppercase', letterSpacing: '0.04em',
                            }}>
                                Generate
                            </Typography>
                        </Box>
                    </Box>
                </Box>
            ) : (
                /* ── Display Mode ─────────────────────────── */
                <>
                    {/* Connection card header */}
                    {isConnectionCard && (
                        <Box sx={(theme) => ({
                            mx: -2.5, mt: -2, mb: 1.5, px: 2.5, py: 0.6,
                            borderTopLeftRadius: 7, borderTopRightRadius: 7,
                            bgcolor: alpha(theme.palette.primary.main, 0.06),
                            borderBottom: '1px solid',
                            borderColor: alpha(theme.palette.primary.main, 0.08),
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                            gap: 0.5,
                        })}>
                            <LinkIcon sx={(t) => ({ fontSize: 12, color: alpha(t.palette.primary.light, 0.55) })} />
                            <Typography sx={{
                                fontSize: '0.6rem', fontWeight: 600,
                                color: alpha(theme.palette.primary.light, 0.55),
                                textTransform: 'uppercase', letterSpacing: '0.05em',
                            }}>
                                Connection
                            </Typography>
                        </Box>
                    )}

                    {/* Title */}
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, mb: summaryText ? 0.5 : 1, pr: 4 }}>
                        <Typography sx={{
                            fontSize: '0.85rem', fontWeight: 700, color: 'text.primary',
                            lineHeight: 1.3,
                        }}>
                            {formatLabel(isConnectionCard ? topic.name.replace(/-connection$/, '') : topic.name)}
                        </Typography>
                    </Box>

                    {/* Short description — always visible, no Read more */}
                    {summaryText && (
                        <Box sx={{ mb: librarySections.length > 0 ? 1 : 0 }}>
                            <MarkdownRenderer content={summaryText} variant="card" />
                        </Box>
                    )}

                    {/* Library sections — title only, full body on hover */}
                    {librarySections.length > 0 && (
                        <Box sx={{ mb: 0 }}>
                            {librarySections.slice(0, 5).map((section, i) => (
                                <Tooltip
                                    key={i}
                                    title={
                                        <Box sx={{ maxWidth: 360, p: 0.5 }}>
                                            <Typography sx={{ fontSize: '0.72rem', fontWeight: 700, mb: 0.75, color: '#fff' }}>
                                                {section.title}
                                            </Typography>
                                            <MarkdownRenderer content={section.body} />
                                        </Box>
                                    }
                                    arrow
                                    placement="right"
                                    enterDelay={300}
                                    leaveDelay={100}
                                    slotProps={{
                                        tooltip: {
                                            sx: {
                                                bgcolor: alpha(theme.palette.background.default, 0.97),
                                                backdropFilter: 'blur(12px)',
                                                border: '1px solid',
                                                borderColor: alpha(color, 0.2),
                                                borderRadius: 2,
                                                boxShadow: '0 8px 32px rgba(0,0,0,0.25)',
                                                p: 1.5,
                                                maxWidth: 360,
                                                '& .MuiTooltip-arrow': {
                                                    color: alpha(theme.palette.background.default, 0.97),
                                                },
                                            },
                                        },
                                    }}
                                >
                                    <Box sx={{
                                        mb: i < Math.min(librarySections.length - 1, 4) - 1 ? 0.5 : 0,
                                        pl: 1.5, borderLeft: `2px solid ${alpha(color, 0.2)}`,
                                        cursor: 'help',
                                        '&:hover': { borderLeftColor: alpha(color, 0.5) },
                                    }}>
                                        <Typography sx={{
                                            fontSize: '0.65rem', fontWeight: 600, color: alpha(color, 0.7),
                                            textTransform: 'uppercase', letterSpacing: '0.03em',
                                        }}>
                                            {section.title}
                                        </Typography>
                                    </Box>
                                </Tooltip>
                            ))}
                        </Box>
                    )}

                    {/* Suggestion pills — colored by category (hidden for connection cards) */}
                    {!isConnectionCard && topic.suggestions && topic.suggestions.length > 0 && (
                        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                            {topic.suggestions.slice(0, 4).map((s, i) => {
                                const isExploring = exploringName && formatLabel(s.name) === exploringName;
                                const kindMatch = (s.description || '').match(/^\[(Parent|Child|Related)\]/);
                                const kindLabel = kindMatch ? kindMatch[1] : '';
                                const kindColors = {
                                    Parent: { bg: 'rgba(124,58,237,0.12)', border: 'rgba(124,58,237,0.3)', text: '#a78bfa' },
                                    Child: { bg: 'rgba(5,150,105,0.12)', border: 'rgba(5,150,105,0.3)', text: '#34d399' },
                                    Related: { bg: 'rgba(2,132,199,0.12)', border: 'rgba(2,132,199,0.3)', text: '#38bdf8' },
                                };
                                const kc = kindColors[kindLabel] || { bg: alpha(color, 0.08), border: 'transparent', text: alpha(color, 0.75) };
                                return (
                                    <Chip key={s.id || i}
                                        label={formatLabel(s.name)}
                                        size="small"
                                        onClick={(e) => { e.stopPropagation(); if (!isExploring) onSelect(s, true); }}
                                        sx={{
                                            height: 20, fontSize: '0.62rem', fontWeight: 600, borderRadius: '5px',
                                            bgcolor: isExploring ? alpha('#888', 0.06) : kc.bg,
                                            color: isExploring ? alpha('#888', 0.3) : kc.text,
                                            border: '1px solid',
                                            borderColor: isExploring ? 'transparent' : kc.border,
                                            cursor: isExploring ? 'default' : 'pointer', transition: 'all 0.2s',
                                            '&:hover': isExploring ? {} : {
                                                bgcolor: kindLabel ? kc.bg.replace('0.12', '0.22') : alpha(color, 0.16),
                                            },
                                            '& .MuiChip-label': { px: 0.8 },
                                        }} />
                                );
                            })}
                        </Box>
                    )}
                </>
            )}

            {/* Resize handle */}
            <Box className="resize-handle" onMouseDown={handleResizeStart}
                sx={{
                    position: 'absolute', bottom: 2, right: 2, width: 16, height: 16,
                    cursor: 'se-resize', opacity: hovered ? 0.35 : 0, transition: 'opacity 0.15s',
                    '&::after': {
                        content: '""', position: 'absolute', bottom: 3, right: 3,
                        width: 8, height: 8,
                        borderRight: `2px solid ${alpha(theme.palette.text.secondary, 0.4)}`,
                        borderBottom: `2px solid ${alpha(theme.palette.text.secondary, 0.4)}`,
                    },
                }}
            />
        </Box>
    );
}, (prev, next) => {
    // Only re-render if this card's data actually changed
    return prev.topic.position_x === next.topic.position_x
        && prev.topic.position_y === next.topic.position_y
        && prev.topic.name === next.topic.name
        && prev.topic.description === next.topic.description
        && prev.topic.outline === next.topic.outline
        && prev.isSelected === next.isSelected
        && prev.exploringName === next.exploringName
        && prev.generating === next.generating
        && prev.generatedContent === next.generatedContent
        && prev.libraryEntry?.content === next.libraryEntry?.content;
});

TopicCard.displayName = 'TopicCard';

// ─── Main Canvas ──────────────────────────────────────────────

function CanvasTab({ mapData, libraryData, brainstormingId, onRefresh, onSuggestionClick, onTopicClick, onTopicMove, onDeleteTopic, onUpdateTopic, onEdgeCreate, onEdgeDelete, selectedTopic, exploringSuggestion, hasClassified, onAddBlankTopic, onGenerateContent, onUpdateOutline, onExploreConnection }) {
    const theme = useTheme();
    const canvasRef = useRef(null);
    const [view, setView] = useState({ x: 0, y: 0, scale: 1 });
    const viewRef = useRef(view);
    useEffect(() => { viewRef.current = view; }, [view]);
    const [panning, setPanning] = useState(false);
    const dragRef = useRef(null);
    const isPanning = useRef(false);
    const panStart = useRef(null);
    const linkDrag = useRef(null);
    const [linkLine, setLinkLine] = useState(null);

    // Creation prompt state
    const [showCreatePrompt, setShowCreatePrompt] = useState(false);
    const [newTopicName, setNewTopicName] = useState('');
    const createInputRef = useRef(null);

    // Generation state per topic
    const [generatingTopicId, setGeneratingTopicId] = useState(null);
    const [generatedContent, setGeneratedContent] = useState('');
    const generateAbortRef = useRef(null);

    // Exploring connection edge state
    const [exploringEdge, setExploringEdge] = useState(null);  // { sourceId, targetId, x, y, sourceName, targetName }

    const topics = mapData?.topics || [];
    const allEdges = mapData?.edges || [];
    // Regular edges: hoverable, deletable, explorable
    const regularEdges = allEdges.filter(e =>
        !e.relationship?.startsWith('suggestion') && e.relationship !== 'connection_link'
    );
    // Suggestion edges: shown only when exploring a suggestion
    const suggestionEdges = allEdges.filter(e =>
        e.relationship?.startsWith('suggestion')
    );
    // Connection edges: fixed, non-interactive lines
    const connectionEdges = allEdges.filter(e => e.relationship === 'connection_link');
    // Edges to show: regular + suggestion edges when exploring
    const visibleEdges = exploringSuggestion
        ? [...regularEdges, ...suggestionEdges.filter(e => {
            const prop = propositionTopics.find(p => p.name === exploringSuggestion.name);
            return prop && (e.target_topic_id === prop.id || e.source_topic_id === prop.id);
        })]
        : regularEdges;
    const suggestions = mapData?.suggestions || [];
    const mainTopics = topics.filter(t => !t.is_proposition);

    const topicsWithSuggestions = mainTopics.map(topic => ({
        ...topic,
        suggestions: suggestions.filter(s => s.source_topic_id === topic.id),
    }));

    useEffect(() => {
        const needsPosition = mainTopics.filter(t => !t.position_x && !t.position_y);
        if (needsPosition.length === 0) return;
        needsPosition.forEach((topic, i) => {
            const offset = randomOffset(i);
            onTopicMove(topic.id, offset.x, offset.y);
        });
    }, [mapData]);

    // ── Link drag: start from the anchor the user clicked ──

    const handleLinkStart = useCallback((topic, side, e) => {
        const anchors = getAnchors(topic);
        const anchor = anchors.find(a => a.side === side) || anchors[0];

        linkDrag.current = {
            sourceTopic: topic,
            sourceSide: side,
            anchorX: anchor.x,
            anchorY: anchor.y,
        };
        setLinkLine({ x1: anchor.x, y1: anchor.y, x2: anchor.x, y2: anchor.y });
    }, []);

    // ── Window-level mouse handlers ────────────────────────────

    useEffect(() => {
        const handleMove = (e) => {
            if (dragRef.current) {
                const { topic, startX, startY, origX, origY, cardEl, edgeLines } = dragRef.current;
                const dx = (e.clientX - startX) / view.scale;
                const dy = (e.clientY - startY) / view.scale;
                const nx = origX + dx;
                const ny = origY + dy;
                // Direct DOM update — card position
                if (cardEl) {
                    cardEl.style.left = `${nx}px`;
                    cardEl.style.top = `${ny}px`;
                }
                // Direct DOM update — edge lines (absolute, same as card)
                edgeLines.forEach(({ g, line, x1, y1, x2, y2 }) => {
                    const isFrom = g.dataset.edgeFrom === topic.id;
                    if (isFrom) {
                        line.setAttribute('x1', x1 + dx);
                        line.setAttribute('y1', y1 + dy);
                    } else {
                        line.setAttribute('x2', x2 + dx);
                        line.setAttribute('y2', y2 + dy);
                    }
                });
                return;
            }
            if (isPanning.current && panStart.current) {
                setView(prev => ({
                    ...prev,
                    x: e.clientX - panStart.current.x,
                    y: e.clientY - panStart.current.y,
                }));
            }
            if (linkDrag.current) {
                const rect = canvasRef.current.getBoundingClientRect();
                const v = viewRef.current;
                const canvasX = (e.clientX - rect.left - v.x) / v.scale;
                const canvasY = (e.clientY - rect.top - v.y) / v.scale;
                setLinkLine(prev => prev ? { ...prev, x2: canvasX, y2: canvasY } : null);
            }
        };

        const handleUp = (e) => {
            // Commit card drag to state (single update)
            if (dragRef.current) {
                const { topic, startX, startY, origX, origY } = dragRef.current;
                const dx = (e.clientX - startX) / view.scale;
                const dy = (e.clientY - startY) / view.scale;
                dragRef.current = null;
                onTopicMove(topic.id, origX + dx, origY + dy);
            }

            // Check if we were link-dragging and released over a card
            if (linkDrag.current) {
                const { sourceTopic } = linkDrag.current;
                linkDrag.current = null;
                setLinkLine(null);
                const els = document.elementsFromPoint(e.clientX, e.clientY);
                for (const el of els) {
                    const card = el.closest?.('[data-topic-id]');
                    if (card) {
                        const targetId = card.getAttribute('data-topic-id');
                        if (targetId && targetId !== sourceTopic.id) {
                            onEdgeCreate(sourceTopic.id, targetId);
                        }
                        break;
                    }
                }
            }

            isPanning.current = false;
            setPanning(false);
        };

        window.addEventListener('mousemove', handleMove);
        window.addEventListener('mouseup', handleUp);
        return () => {
            window.removeEventListener('mousemove', handleMove);
            window.removeEventListener('mouseup', handleUp);
        };
    }, [view.scale, onTopicMove, onEdgeCreate]);

    // ── Pan ────────────────────────────────────────────────────

    const handleCanvasMouseDown = useCallback((e) => {
        const isCanvas = e.target === canvasRef.current || e.target.dataset.canvas === 'true';
        if (isCanvas && e.button === 0) {
            isPanning.current = true;
            setPanning(true);
            panStart.current = { x: e.clientX - view.x, y: e.clientY - view.y };
            e.preventDefault();
        }
    }, [view]);

    const handleWheel = useCallback((e) => {
        e.preventDefault();
        const delta = e.deltaY > 0 ? 0.9 : 1.1;
        const newScale = Math.min(2.5, Math.max(0.15, view.scale * delta));
        const rect = canvasRef.current.getBoundingClientRect();
        const mx = e.clientX - rect.left;
        const my = e.clientY - rect.top;
        setView({
            scale: newScale,
            x: mx - (mx - view.x) * (newScale / view.scale),
            y: my - (my - view.y) * (newScale / view.scale),
        });
    }, [view]);

    // Attach wheel listener non-passively so preventDefault works for zoom
    useEffect(() => {
        const el = canvasRef.current;
        if (!el) return;
        el.addEventListener('wheel', handleWheel, { passive: false });
        return () => el.removeEventListener('wheel', handleWheel);
    }, [handleWheel]);

    const handleDragStart = useCallback((e, topic) => {
        if (e.button !== 0 || e.ctrlKey) return;
        e.preventDefault();
        e.stopPropagation();
        const cardEl = e.currentTarget.closest('[data-topic-id]');
        // Find all edge lines connected to this topic
        const edgeLines = [];
        const canvas = canvasRef.current;
        if (canvas) {
            const edgeGs = canvas.querySelectorAll(
                `[data-edge-from="${topic.id}"], [data-edge-to="${topic.id}"]`
            );
            edgeGs.forEach(g => {
                const visLine = g.querySelector('[data-line="visible"]');
                if (visLine) edgeLines.push({ g, line: visLine });
            });
        }
        dragRef.current = {
            topic,
            startX: e.clientX,
            startY: e.clientY,
            origX: topic.position_x || 0,
            origY: topic.position_y || 0,
            cardEl,
            edgeLines: edgeLines.map(({ g, line }) => ({
                g,
                line,
                x1: parseFloat(line.getAttribute('x1')),
                y1: parseFloat(line.getAttribute('y1')),
                x2: parseFloat(line.getAttribute('x2')),
                y2: parseFloat(line.getAttribute('y2')),
            })),
        };
    }, []);

    const handleSelect = useCallback((topic, sourceTopicId, isSuggestion = false) => {
        if (isSuggestion) {
            onSuggestionClick?.(formatLabel(topic.name), sourceTopicId);
        } else {
            onTopicClick?.(topic);
        }
    }, [onSuggestionClick, onTopicClick]);

    // ── Create blank topic ────────────────────────────────

    const handleCreateTopic = useCallback(async () => {
        const name = newTopicName.trim();
        if (!name || !brainstormingId) return;
        try {
            await onAddBlankTopic?.(brainstormingId, name);
        } catch {
            // Error already logged in store
        }
        setNewTopicName('');
        setShowCreatePrompt(false);
    }, [newTopicName, brainstormingId, onAddBlankTopic]);

    const handleOpenCreate = useCallback(() => {
        setShowCreatePrompt(true);
        setTimeout(() => createInputRef.current?.focus(), 50);
    }, []);

    // ── Generate content ──────────────────────────────────

    const handleGenerate = useCallback((brainstormId, topicId) => {
        if (!onGenerateContent || !brainstormId || !topicId) return;
        setGeneratingTopicId(topicId);
        setGeneratedContent('');
        onGenerateContent(brainstormId, topicId, {
            onToken: (token) => {
                setGeneratedContent(prev => prev + token);
            },
            onDone: () => {
                setGeneratingTopicId(null);
                setGeneratedContent('');
            },
            onError: (err) => {
                logger.error('Generate error:', err);
                setGeneratingTopicId(null);
                setGeneratedContent('');
            },
        }).then(controller => {
            generateAbortRef.current = controller;
        });
    }, [onGenerateContent]);

    // Cleanup generation on unmount
    useEffect(() => {
        return () => {
            if (generateAbortRef.current) {
                generateAbortRef.current.abort();
            }
        };
    }, []);

    // ── Explore edge connection ───────────────────────────

    const handleExploreEdge = useCallback((sourceId, targetId, x, y) => {
        if (!brainstormingId || !onExploreConnection) return;
        // Find topic names for the popup
        const sourceName = formatLabel(mainTopics.find(t => t.id === sourceId)?.name || '');
        const targetName = formatLabel(mainTopics.find(t => t.id === targetId)?.name || '');
        setExploringEdge({ sourceId, targetId, x, y, sourceName, targetName });
        onExploreConnection(brainstormingId, sourceId, targetId, x, y)
            .finally(() => setExploringEdge(null));
    }, [brainstormingId, onExploreConnection, mainTopics]);

    const hasTopics = mainTopics.length > 0;
    const propositionTopics = topics.filter(t => t.is_proposition);
    const hasPropositions = propositionTopics.length > 0;
    const hasContent = hasTopics || hasPropositions;

    return (
        <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
            <Box sx={(theme) => ({
                px: 3, py: 1.75,
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                bgcolor: alpha(theme.palette.background.default, 0.3),
            })}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                    <HubIcon sx={(theme) => ({ fontSize: 15, color: theme.palette.primary.light })} />
                    <Typography sx={{ fontWeight: 700, fontSize: '0.925rem', color: 'text.primary' }}>
                        Canvas
                    </Typography>
                    {hasTopics && (
                        <Chip label={`${mainTopics.length} topic${mainTopics.length !== 1 ? 's' : ''}`} size="small"
                            sx={(theme) => ({
                                height: 20, fontSize: '0.6rem', fontWeight: 700, borderRadius: '6px',
                                bgcolor: alpha(theme.palette.primary.main, 0.1),
                                color: theme.palette.primary.light,
                            })} />
                    )}
                </Box>
                <Box sx={{ display: 'flex', gap: 0.5 }}>
                    <Tooltip title="Add topic" arrow>
                        <IconButton onClick={handleOpenCreate} size="small"
                            sx={(theme) => ({
                                width: 30, height: 30, borderRadius: 1.5,
                                color: alpha(theme.palette.text.secondary, 0.4),
                                '&:hover': { bgcolor: alpha(theme.palette.primary.main, 0.08), color: theme.palette.primary.light },
                            })}>
                            <AddIcon sx={{ fontSize: 14 }} />
                        </IconButton>
                    </Tooltip>
                    {hasTopics && (
                        <Tooltip title="Reset view" arrow>
                            <IconButton onClick={() => setView({ x: 0, y: 0, scale: 1 })} size="small"
                                sx={(theme) => ({
                                    width: 30, height: 30, borderRadius: 1.5,
                                    color: alpha(theme.palette.text.secondary, 0.4),
                                    '&:hover': { bgcolor: alpha(theme.palette.primary.main, 0.08), color: theme.palette.primary.light },
                                })}>
                                <RefreshIcon sx={{ fontSize: 14 }} />
                            </IconButton>
                        </Tooltip>
                    )}
                </Box>
            </Box>

            {/* ── Create Topic Prompt ──────────────────────────── */}
            {showCreatePrompt && (
                <Box sx={(theme) => ({
                    mx: 3, mb: 0, p: 1.5,
                    borderRadius: 2,
                    bgcolor: alpha(theme.palette.background.paper, 0.5),
                    border: '1px solid',
                    borderColor: alpha(theme.palette.primary.main, 0.15),
                    display: 'flex', alignItems: 'center', gap: 1,
                })}>
                    <TextField
                        inputRef={createInputRef}
                        fullWidth
                        size="small"
                        placeholder="Topic name..."
                        value={newTopicName}
                        onChange={(e) => setNewTopicName(e.target.value)}
                        onKeyDown={(e) => {
                            if (e.key === 'Enter') handleCreateTopic();
                            if (e.key === 'Escape') { setShowCreatePrompt(false); setNewTopicName(''); }
                        }}
                        variant="outlined"
                        slotProps={{
                            input: {
                                sx: (theme) => ({
                                    fontSize: '0.8rem', borderRadius: 1.5,
                                    bgcolor: alpha(theme.palette.background.default, 0.3),
                                    '& fieldset': { border: 'none' },
                                    '& input': { py: 1, '&::placeholder': { color: alpha(theme.palette.text.secondary, 0.35), opacity: 1 } },
                                }),
                            },
                        }}
                    />
                    <Tooltip title="Create" arrow>
                        <IconButton
                            size="small"
                            disabled={!newTopicName.trim()}
                            onClick={handleCreateTopic}
                            sx={(theme) => ({
                                width: 34, height: 34, borderRadius: 1.5,
                                bgcolor: newTopicName.trim() ? alpha(theme.palette.primary.main, 0.15) : 'transparent',
                                color: newTopicName.trim() ? theme.palette.primary.light : alpha(theme.palette.text.disabled, 0.3),
                                transition: 'all 0.15s ease',
                                '&:hover': newTopicName.trim() ? {
                                    bgcolor: alpha(theme.palette.primary.main, 0.25),
                                } : {},
                            })}
                        >
                            <AddIcon sx={{ fontSize: 16 }} />
                        </IconButton>
                    </Tooltip>
                </Box>
            )}

            <Box
                ref={canvasRef}
                data-canvas="true"
                onMouseDown={handleCanvasMouseDown}
                sx={{
                    flex: 1, position: 'relative', overflow: 'hidden',
                    cursor: panning ? 'grabbing' : 'grab',
                    bgcolor: alpha(theme.palette.background.default, 0.2),
                }}
            >
                {!hasContent ? (
                    <Box sx={{
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        height: '100%', flexDirection: 'column', gap: 2.5,
                    }}>
                        <Box sx={(theme) => ({
                            width: 72, height: 72, borderRadius: 2,
                            background: `linear-gradient(135deg, ${alpha(theme.palette.primary.main, 0.15)} 0%, ${alpha(theme.palette.primary.light, 0.08)} 100%)`,
                            border: '1px solid', borderColor: alpha(theme.palette.primary.main, 0.1),
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                            animation: 'pulseGlow 2s ease-in-out infinite',
                            '@keyframes pulseGlow': {
                                '0%, 100%': { boxShadow: `0 0 20px ${alpha(theme.palette.primary.main, 0.1)}` },
                                '50%': { boxShadow: `0 0 40px ${alpha(theme.palette.primary.main, 0.25)}` },
                            },
                        })}>
                            <AddIcon sx={(theme) => ({ fontSize: 28, color: theme.palette.primary.light })} />
                        </Box>
                        <Typography sx={(theme) => ({
                            fontWeight: 600, color: alpha(theme.palette.text.primary, 0.6),
                            fontSize: '0.9rem',
                        })}>
                            {hasClassified ? 'No topics extracted yet' : 'Building your canvas...'}
                        </Typography>
                    </Box>
                ) : !hasTopics && hasPropositions ? (
                    /* Propositions only — show as clickable suggestion pills */
                    <Box sx={{
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        height: '100%', flexDirection: 'column', gap: 3,
                        px: 4,
                    }}>
                        <Box sx={{ textAlign: 'center' }}>
                            <Typography sx={(theme) => ({
                                fontWeight: 600, color: alpha(theme.palette.text.primary, 0.7),
                                fontSize: '0.95rem', mb: 0.5,
                            })}>
                                {propositionTopics.length} suggestion{propositionTopics.length !== 1 ? 's' : ''} found
                            </Typography>
                            <Typography sx={(theme) => ({
                                fontWeight: 400, color: alpha(theme.palette.text.secondary, 0.5),
                                fontSize: '0.78rem', lineHeight: 1.6,
                            })}>
                                Click a topic to explore it and add it to your canvas.
                            </Typography>
                        </Box>
                        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, justifyContent: 'center', maxWidth: 400 }}>
                            {propositionTopics.map(topic => (
                                <Chip
                                    key={topic.id}
                                    label={formatLabel(topic.name)}
                                    onClick={() => onSuggestionClick?.(formatLabel(topic.name), topic.id)}
                                    sx={(theme) => ({
                                        height: 32, fontSize: '0.78rem', fontWeight: 600,
                                        borderRadius: '8px', px: 1,
                                        bgcolor: alpha(theme.palette.primary.main, 0.08),
                                        color: theme.palette.primary.light,
                                        border: '1px solid',
                                        borderColor: alpha(theme.palette.primary.main, 0.15),
                                        cursor: 'pointer',
                                        transition: 'all 0.2s',
                                        '&:hover': {
                                            bgcolor: alpha(theme.palette.primary.main, 0.16),
                                            borderColor: alpha(theme.palette.primary.main, 0.3),
                                            transform: 'translateY(-1px)',
                                        },
                                    })}
                                />
                            ))}
                        </Box>
                    </Box>
                ) : (
                    <Box sx={{
                        position: 'absolute',
                        inset: 0,
                        transform: `translate(${view.x}px, ${view.y}px) scale(${view.scale})`,
                        transformOrigin: '0 0',
                        pointerEvents: 'none',
                    }}>
                        {/* Edge lines — interactive, hover shows delete/explore */}
                        <EdgeLines
                            edges={visibleEdges}
                            topics={[...mainTopics, ...(exploringSuggestion ? propositionTopics.filter(p => p.name === exploringSuggestion.name) : [])]}
                            onDeleteEdge={onEdgeDelete}
                            brainstormingId={brainstormingId}
                            onExploreEdge={handleExploreEdge}
                        />

                        {/* Connection edges — fixed, non-interactive */}
                        {connectionEdges.length > 0 && (
                            <svg style={{
                                position: 'absolute', top: 0, left: 0,
                                width: '100%', height: '100%',
                                pointerEvents: 'none', zIndex: 0,
                            }}>
                                {connectionEdges.map(edge => {
                                    const source = mainTopics.find(t => t.id === edge.source_topic_id);
                                    const target = mainTopics.find(t => t.id === edge.target_topic_id);
                                    if (!source || !target) return null;
                                    const pts = closestAnchors(source, target);
                                    return (
                                        <line key={edge.id}
                                            x1={pts.ax} y1={pts.ay} x2={pts.bx} y2={pts.by}
                                            stroke={alpha(theme.palette.primary.light, 0.18)}
                                            strokeWidth={2}
                                            strokeDasharray="5 4"
                                        />
                                    );
                                })}
                            </svg>
                        )}

                        {/* Link drag line */}
                        {linkLine && (
                            <svg style={{
                                position: 'absolute', top: 0, left: 0,
                                width: '100%', height: '100%',
                                pointerEvents: 'none', zIndex: 15,
                            }}>
                                <line
                                    x1={linkLine.x1}
                                    y1={linkLine.y1}
                                    x2={linkLine.x2}
                                    y2={linkLine.y2}
                                    stroke="#94a3b8" strokeWidth={2} strokeDasharray="6 4" opacity={0.7} />
                            </svg>
                        )}

                        {/* Topic cards */}
                        {topicsWithSuggestions.map(topic => {
                            const sourceId = topic.id;
                            const libEntry = (libraryData || []).flatMap(f => f.entries || []).find(e => e.topic_id === topic.id);
                            const isGenerating = generatingTopicId === topic.id;
                            const content = isGenerating ? generatedContent : '';
                            return (
                                <Box key={topic.id} sx={{ pointerEvents: 'auto' }}>
                                    <TopicCard
                                        topic={topic}
                                        isSelected={selectedTopic?.id === topic.id}
                                        exploringName={exploringSuggestion?.name}
                                        libraryEntry={libEntry}
                                        onSelect={(t, isSuggestion) => handleSelect(t, sourceId, isSuggestion)}
                                        onDragStart={handleDragStart}
                                        onLinkStart={handleLinkStart}
                                        onDelete={onDeleteTopic}
                                        onUpdate={onUpdateTopic}
                                        brainstormingId={brainstormingId}
                                        onGenerate={handleGenerate}
                                        onOutlineChange={onUpdateOutline}
                                        generating={isGenerating}
                                        generatedContent={content}
                                    />
                                </Box>
                            );
                        })}

                        {/* Loading card for suggestion exploration */}
                        {exploringSuggestion && (() => {
                            const source = mainTopics.find(t => t.id === exploringSuggestion.sourceTopicId);
                            if (!source) return null;
                            return (
                                <Box sx={{
                                    position: 'absolute',
                                    left: (source.position_x || 0) + 260,
                                    top: (source.position_y || 0) + 60,
                                    px: 2.5, py: 2,
                                    borderRadius: 2,
                                    minWidth: 160, maxWidth: 240,
                                    border: '1.5px solid',
                                    borderColor: alpha(theme.palette.primary.main, 0.2),
                                    bgcolor: alpha(theme.palette.background.paper, 0.8),
                                    pointerEvents: 'none',
                                    zIndex: 5,
                                    boxShadow: `0 2px 12px ${alpha(theme.palette.primary.main, 0.08)}`,
                                }}>
                                    <Typography sx={{
                                        fontSize: '0.825rem', fontWeight: 600,
                                        color: alpha(theme.palette.text.primary, 0.6),
                                        lineHeight: 1.3, mb: 1.5,
                                    }}>
                                        {formatLabel(exploringSuggestion.name)}
                                    </Typography>
                                    <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                                        <CircularProgress size={20} sx={(t) => ({ color: alpha(t.palette.primary.light, 0.7) })} />
                                    </Box>
                                </Box>
                            );
                        })()}

                        {/* Loading card for connection exploration */}
                        {exploringEdge && (() => {
                            const { x, y, sourceName, targetName, sourceId, targetId } = exploringEdge;
                            const sourceTopic = mainTopics.find(t => t.id === sourceId);
                            const targetTopic = mainTopics.find(t => t.id === targetId);
                            return (
                                <>
                                    {/* Temporary connection lines */}
                                    <svg style={{
                                        position: 'absolute', top: 0, left: 0,
                                        width: '100%', height: '100%',
                                        pointerEvents: 'none', zIndex: 4,
                                    }}>
                                        {sourceTopic && (
                                            <line
                                                x1={(sourceTopic.position_x || 0) + 90} y1={(sourceTopic.position_y || 0) + 35}
                                                x2={x} y2={y}
                                                stroke={alpha(theme.palette.primary.light, 0.18)}
                                                strokeWidth={2}
                                                strokeDasharray="5 4"
                                            />
                                        )}
                                        {targetTopic && (
                                            <line
                                                x1={(targetTopic.position_x || 0) + 90} y1={(targetTopic.position_y || 0) + 35}
                                                x2={x} y2={y}
                                                stroke={alpha(theme.palette.primary.light, 0.18)}
                                                strokeWidth={2}
                                                strokeDasharray="5 4"
                                            />
                                        )}
                                    </svg>

                                    {/* Loading card */}
                                    <Box sx={{
                                    position: 'absolute',
                                    left: x - 100, top: y - 10,
                                    width: 200, minHeight: 60,
                                    px: 2.5, py: 2,
                                    borderRadius: 2,
                                    border: '1.5px solid',
                                    borderColor: alpha(theme.palette.primary.main, 0.2),
                                    bgcolor: alpha(theme.palette.background.paper, 0.8),
                                    pointerEvents: 'none',
                                    zIndex: 5,
                                    boxShadow: `0 2px 12px ${alpha(theme.palette.primary.main, 0.08)}`,
                                }}>
                                    <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 0.5, mb: 1.5 }}>
                                        <LinkIcon sx={(t) => ({ fontSize: 12, color: alpha(t.palette.primary.light, 0.5) })} />
                                        <Typography sx={{
                                            fontSize: '0.68rem', fontWeight: 600,
                                            color: alpha(theme.palette.text.primary, 0.5),
                                        }}>
                                            {sourceName} ↔ {targetName}
                                        </Typography>
                                    </Box>
                                    <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                                        <CircularProgress size={18} sx={(t) => ({ color: alpha(t.palette.primary.light, 0.7) })} />
                                    </Box>
                                </Box>
                                </>
                            );
                        })()}
                    </Box>
                )}
            </Box>
        </Box>
    );
}

export default CanvasTab;
