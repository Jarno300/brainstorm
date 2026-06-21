import { useState, useCallback, useEffect, useMemo, memo } from 'react';
import { Box, alpha, useTheme } from '@mui/material';
import { Delete as DeleteIcon } from '@mui/icons-material';
import { formatLabel, getImportanceColor, computeImportance } from '../canvasUtils';
import { CARD_COLORS } from './cardConstants';
import CardColorPicker from './CardColorPicker';
import CardEditMode from './CardEditMode';
import CardDisplayMode from './CardDisplayMode';

function LinkHandles({ color, hovered, topic, onLinkStart }) {
    if (!hovered) return null;
    return ['top', 'bottom', 'left', 'right'].map(side => {
        const pos = {
            top: { top: -7, left: '50%', ml: '-7px' },
            bottom: { bottom: -7, left: '50%', ml: '-7px' },
            left: { left: -7, top: '50%', mt: '-7px' },
            right: { right: -7, top: '50%', mt: '-7px' },
        }[side];
        return (
            <Box key={side} className="link-handle"
                onMouseDown={(e) => { e.stopPropagation(); e.preventDefault(); onLinkStart(topic, side, e); }}
                sx={{
                    position: 'absolute', width: 14, height: 14, borderRadius: '50%',
                    bgcolor: alpha(color, 0.5), border: `2px solid ${color}`,
                    cursor: 'crosshair', zIndex: 20, opacity: 0.7,
                    transition: 'transform 0.15s, opacity 0.15s',
                    '&:hover': { transform: 'scale(1.4)', opacity: 1 },
                    ...pos,
                }}
            />
        );
    });
}

function HoverActions({ hovered, color, isDark, showColorPicker, setShowColorPicker, setCustomColor, onDelete, topic }) {
    const theme = useTheme();
    if (!hovered) return null;
    return (
        <Box sx={{ position: 'absolute', top: 4, right: 8, display: 'flex', gap: 0.5, zIndex: 25 }}>
            <CardColorPicker color={color} isDark={isDark} showColorPicker={showColorPicker}
                setShowColorPicker={setShowColorPicker} setCustomColor={setCustomColor} />
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
    );
}

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
    const [fresh, setFresh] = useState(true);

    useEffect(() => {
        const timer = setTimeout(() => setFresh(false), 600);
        return () => clearTimeout(timer);
    }, []);

    const cardW = cardSize.w;
    const isEditMode = !libraryEntry;

    // ── Library sections ──────────────────────────────────
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
        const contentSections = sections.filter(s => !['parent topics', 'child topics', 'related topics'].includes(s.title.toLowerCase()));
        if (contentSections.length === 0 && sections.length === 0) {
            const firstPara = text.split('\n\n')[0] || text.slice(0, 150);
            contentSections.push({ title: 'Overview', body: firstPara });
        }
        return contentSections;
    }, [libraryEntry]);

    const summaryText = (() => {
        if (libraryEntry?.content) {
            const m = libraryEntry.content.match(/^>\s*(.+)/m);
            if (m) return m[1].trim();
        }
        return topic.description || '';
    })();

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
            sx={(theme) => ({
                position: 'absolute',
                left: topic.position_x || 0, top: topic.position_y || 0,
                width: cardW, px: 2.5, py: 2, borderRadius: 2,
                bgcolor: isDark ? alpha(color, 0.06) : alpha('#fff', 0.95),
                border: '1.5px solid',
                borderColor: isSelected ? color : (isDark ? alpha(color, 0.15) : alpha('#e2e8f0', 0.9)),
                cursor: 'grab', userSelect: 'none',
                boxShadow: isSelected
                    ? (importance === 'core'
                        ? `0 0 32px ${alpha(color, 0.3)}, 0 8px 24px rgba(0,0,0,0.12), inset 0 1px 0 ${alpha(color, 0.08)}`
                        : `0 0 24px ${alpha(color, 0.25)}, 0 8px 24px rgba(0,0,0,0.1)`)
                    : (importance === 'low'
                        ? `0 1px 4px rgba(0,0,0,0.02), 0 0.5px 1px rgba(0,0,0,0.02)`
                        : `0 2px 8px rgba(0,0,0,0.04), 0 1px 2px rgba(0,0,0,0.03)`),
                '&:hover': { borderColor: alpha(color, 0.4), boxShadow: `0 8px 28px rgba(0,0,0,0.12)`, transform: 'translateY(-2px)' },
                zIndex: isSelected ? 10 : 1, pointerEvents: 'auto',
                transition: 'width 0.15s ease, box-shadow 0.25s ease, transform 0.2s ease, opacity 0.5s ease, filter 0.5s ease',
                '@keyframes cardBloom': {
                    '0%': { opacity: 0, transform: 'scale(0.88) translateY(12px)', filter: 'blur(4px)' },
                    '60%': { opacity: 1, filter: 'blur(0)' },
                    '100%': { opacity: 1, transform: 'scale(1) translateY(0)', filter: 'blur(0)' },
                },
                ...(fresh ? { animation: `cardBloom ${importance === 'core' ? '0.35s' : importance === 'high' ? '0.45s' : '0.55s'} cubic-bezier(0.34, 1.56, 0.64, 1) both` } : {}),
            })}
        >
            <LinkHandles color={color} hovered={hovered} topic={topic} onLinkStart={onLinkStart} />

            <HoverActions hovered={hovered} color={color} isDark={isDark}
                showColorPicker={showColorPicker} setShowColorPicker={setShowColorPicker}
                setCustomColor={setCustomColor} onDelete={onDelete} topic={topic} />

            {isEditMode ? (
                <CardEditMode topic={topic} brainstormingId={brainstormingId} color={color}
                    generating={generating} generatedContent={generatedContent}
                    onUpdate={onUpdate} onOutlineChange={onOutlineChange} onGenerate={onGenerate} />
            ) : (
                <CardDisplayMode topic={topic} exploringName={exploringName}
                    libraryEntry={libraryEntry} librarySections={librarySections}
                    summaryText={summaryText} color={color} onSelect={onSelect} />
            )}

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

export default TopicCard;
