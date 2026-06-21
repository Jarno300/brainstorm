import { useRef, useState, useCallback, useEffect } from 'react';
import {
    Box, Typography, IconButton, Tooltip, Chip, alpha, useTheme, TextField, CircularProgress,
} from '@mui/material';
import {
    Add as AddIcon,
    Link as LinkIcon,
} from '@mui/icons-material';
import logger from '../../utils/logger';
import { researchTopic } from '../../api';
import EdgeLines from './EdgeLines';
import TopicCard from './TopicCard/TopicCard';
import CanvasMinimap from './CanvasMinimap';
import { formatLabel, randomOffset, closestAnchors, getAnchors } from './canvasUtils';
import useMapStore from '../../stores/mapStore';
import useLibraryStore from '../../stores/libraryStore';

// ─── Main Canvas ──────────────────────────────────────────────

function CanvasTab({ brainstormingId }) {
    const theme = useTheme();

    // ── Map store ──────────────────────────────────────────
    const mapData = useMapStore(s => s.mapData);
    const selectedTopic = useMapStore(s => s.selectedTopic);
    const exploringSuggestion = useMapStore(s => s.exploringTopic);
    const hasClassified = useMapStore(s => s.hasClassified);
    const selectTopic = useMapStore(s => s.selectTopic);
    const handleTopicMove = useMapStore(s => s.handleTopicMove);
    const deleteTopic = useMapStore(s => s.deleteTopic);
    const updateTopic = useMapStore(s => s.updateTopic);
    const createEdge = useMapStore(s => s.createEdge);
    const deleteEdge = useMapStore(s => s.deleteEdge);
    const addBlankTopic = useMapStore(s => s.addBlankTopic);
    const generateContent = useMapStore(s => s.generateContent);
    const updateOutline = useMapStore(s => s.updateOutline);
    const exploreConnection = useMapStore(s => s.exploreConnection);
    const exploringEdge = useMapStore(s => s.exploringEdge);
    const setExploringEdge = useMapStore(s => s.setExploringEdge);
    const setExploringTopic = useMapStore(s => s.setExploringTopic);
    const setHasClassified = useMapStore(s => s.setHasClassified);

    // ── Library store ──────────────────────────────────────
    const libraryData = useLibraryStore(s => s.libraryData);
    const loadLibrary = useLibraryStore(s => s.loadLibrary);

    // ── Canvas state ───────────────────────────────────────
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

    const [showCreatePrompt, setShowCreatePrompt] = useState(false);
    const [newTopicName, setNewTopicName] = useState('');
    const createInputRef = useRef(null);

    const [generatingTopicId, setGeneratingTopicId] = useState(null);
    const [generatedContent, setGeneratedContent] = useState('');
    const generateAbortRef = useRef(null);
    const exploreTimeoutRef = useRef(null);
    const removedEdgePairsRef = useRef(new Set());
    const [canvasSize, setCanvasSize] = useState({ w: 800, h: 600 });

    const topics = mapData?.topics || [];
    const allEdges = mapData?.edges || [];
    const edgePairKey = (a, b) => [a, b].sort().join('::');
    const regularEdges = allEdges.filter(e =>
        !e.relationship?.startsWith('suggestion') &&
        e.relationship !== 'connection_link' &&
        !removedEdgePairsRef.current.has(edgePairKey(e.source_topic_id, e.target_topic_id))
    );
    const suggestionEdges = allEdges.filter(e =>
        e.relationship?.startsWith('suggestion')
    );
    const connectionEdges = allEdges.filter(e => e.relationship === 'connection_link');
    const propositionTopics = topics.filter(t => t.is_proposition);
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

    // Clear client-side removed edges when backend refreshes mapData
    useEffect(() => {
        removedEdgePairsRef.current.clear();
    }, [mapData]);

    // Auto-layout unpositioned topics
    useEffect(() => {
        const needsPosition = mainTopics.filter(t => !t.position_x && !t.position_y);
        if (needsPosition.length === 0) return;
        needsPosition.forEach((topic, i) => {
            const offset = randomOffset(i);
            handleTopicMove(brainstormingId, topic.id, offset.x, offset.y);
        });
    }, [mapData]);

    // ── Suggestion click ──────────────────────────────────

    const handleSuggestionClick = useCallback((topicName, sourceTopicId) => {
        if (!brainstormingId) return;
        setExploringTopic({ name: topicName, sourceTopicId });
        setHasClassified(false);
        researchTopic(brainstormingId, topicName).catch(err =>
            logger.error('Research failed:', err)
        );
    }, [brainstormingId, setExploringTopic, setHasClassified]);

    // ── Topic actions (with library refresh) ──────────────

    const handleDeleteTopic = useCallback(async (topicId) => {
        if (!brainstormingId) return;
        await deleteTopic(brainstormingId, topicId);
        if (brainstormingId) await loadLibrary(brainstormingId);
    }, [brainstormingId, deleteTopic, loadLibrary]);

    const handleTopicClick = useCallback((topic) => {
        selectTopic(topic);
    }, [selectTopic]);

    // ── Link drag ──────────────────────────────────────────

    const handleLinkStart = useCallback((topic, side, e) => {
        const anchors = getAnchors(topic);
        const anchor = anchors.find(a => a.side === side) || anchors[0];
        linkDrag.current = { sourceTopic: topic, sourceSide: side, anchorX: anchor.x, anchorY: anchor.y };
        setLinkLine({ x1: anchor.x, y1: anchor.y, x2: anchor.x, y2: anchor.y });
    }, []);

    // ── Window-level mouse handlers ──────────────────────────

    useEffect(() => {
        const handleMove = (e) => {
            if (dragRef.current) {
                const { topic, startX, startY, origX, origY, cardEl, edgeLines } = dragRef.current;
                const dx = (e.clientX - startX) / view.scale;
                const dy = (e.clientY - startY) / view.scale;
                if (cardEl) {
                    cardEl.style.left = `${origX + dx}px`;
                    cardEl.style.top = `${origY + dy}px`;
                }
                edgeLines.forEach(({ g, line, x1, y1, x2, y2 }) => {
                    const isFrom = g.dataset.edgeFrom === topic.id;
                    if (isFrom) { line.setAttribute('x1', x1 + dx); line.setAttribute('y1', y1 + dy); }
                    else { line.setAttribute('x2', x2 + dx); line.setAttribute('y2', y2 + dy); }
                });
                return;
            }
            if (isPanning.current && panStart.current) {
                setView(prev => ({ ...prev, x: e.clientX - panStart.current.x, y: e.clientY - panStart.current.y }));
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
            if (dragRef.current) {
                const { topic, startX, startY, origX, origY } = dragRef.current;
                const dx = (e.clientX - startX) / view.scale;
                const dy = (e.clientY - startY) / view.scale;
                dragRef.current = null;
                handleTopicMove(brainstormingId, topic.id, origX + dx, origY + dy);
            }
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
                            createEdge(brainstormingId, sourceTopic.id, targetId);
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
    }, [view.scale, brainstormingId, handleTopicMove, createEdge]);

    // ── Pan ────────────────────────────────────────────────

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

    useEffect(() => {
        const el = canvasRef.current;
        if (!el) return;
        el.addEventListener('wheel', handleWheel, { passive: false });
        return () => el.removeEventListener('wheel', handleWheel);
    }, [handleWheel]);

    const handleDragStart = useCallback((e, topic) => {
        if (e.button !== 0 || e.ctrlKey) return;
        e.preventDefault(); e.stopPropagation();
        const cardEl = e.currentTarget.closest('[data-topic-id]');
        const edgeLines = [];
        const canvas = canvasRef.current;
        if (canvas) {
            canvas.querySelectorAll(`[data-edge-from="${topic.id}"], [data-edge-to="${topic.id}"]`)
                .forEach(g => { const vl = g.querySelector('[data-line="visible"]'); if (vl) edgeLines.push({ g, line: vl }); });
        }
        dragRef.current = {
            topic, startX: e.clientX, startY: e.clientY,
            origX: topic.position_x || 0, origY: topic.position_y || 0,
            cardEl,
            edgeLines: edgeLines.map(({ g, line }) => ({
                g, line,
                x1: parseFloat(line.getAttribute('x1')), y1: parseFloat(line.getAttribute('y1')),
                x2: parseFloat(line.getAttribute('x2')), y2: parseFloat(line.getAttribute('y2')),
            })),
        };
    }, []);

    const handleSelect = useCallback((topic, sourceTopicId, isSuggestion = false) => {
        if (isSuggestion) {
            handleSuggestionClick(formatLabel(topic.name), sourceTopicId);
        } else {
            handleTopicClick(topic);
        }
    }, [handleSuggestionClick, handleTopicClick]);

    // ── Create blank topic ────────────────────────────────

    const handleCreateTopic = useCallback(async () => {
        const name = newTopicName.trim();
        if (!name || !brainstormingId) return;
        try { await addBlankTopic(brainstormingId, name); } catch { /* logged in store */ }
        setNewTopicName('');
        setShowCreatePrompt(false);
    }, [newTopicName, brainstormingId, addBlankTopic]);

    const handleOpenCreate = useCallback(() => {
        setShowCreatePrompt(true);
        setTimeout(() => createInputRef.current?.focus(), 50);
    }, []);

    // ── Generate content ──────────────────────────────────

    const handleGenerate = useCallback((brainId, topicId) => {
        if (!brainId || !topicId) return;
        setGeneratingTopicId(topicId);
        setGeneratedContent('');
        generateContent(brainId, topicId, {
            onToken: (token) => setGeneratedContent(prev => prev + token),
            onDone: () => { setGeneratingTopicId(null); setGeneratedContent(''); },
            onError: (err) => { logger.error('Generate error:', err); setGeneratingTopicId(null); setGeneratedContent(''); },
        }).then(controller => { generateAbortRef.current = controller; });
    }, [generateContent]);

    useEffect(() => {
        return () => {
            if (generateAbortRef.current) generateAbortRef.current.abort();
            if (exploreTimeoutRef.current) clearTimeout(exploreTimeoutRef.current);
        };
    }, []);

    // ── Canvas resize tracking (for minimap viewport) ────

    useEffect(() => {
        const el = canvasRef.current;
        if (!el) return;
        const update = () => setCanvasSize({ w: el.clientWidth, h: el.clientHeight });
        update();
        const ro = new ResizeObserver(update);
        ro.observe(el);
        return () => ro.disconnect();
    }, []);

    // ── Explore edge connection ───────────────────────────

    // Timeout fallback: clear loading state if WebSocket event never arrives
    const CONNECTION_EXPLORE_TIMEOUT_MS = 60_000;

    const handleExploreEdge = useCallback((sourceId, targetId, x, y) => {
        if (!brainstormingId) return;
        const sourceName = formatLabel(mainTopics.find(t => t.id === sourceId)?.name || '');
        const targetName = formatLabel(mainTopics.find(t => t.id === targetId)?.name || '');

        // Immediately remove the edge between these two topics on the client
        removedEdgePairsRef.current.add(edgePairKey(sourceId, targetId));

        setExploringEdge({ sourceId, targetId, x, y, sourceName, targetName });

        // Clear any previous timeout
        if (exploreTimeoutRef.current) clearTimeout(exploreTimeoutRef.current);

        // Fallback: if WebSocket topic_generated never fires, clear loading after timeout
        exploreTimeoutRef.current = setTimeout(() => {
            setExploringEdge(null);
        }, CONNECTION_EXPLORE_TIMEOUT_MS);

        exploreConnection(brainstormingId, sourceId, targetId, x, y)
            .catch(() => setExploringEdge(null));
    }, [brainstormingId, exploreConnection, setExploringEdge, mainTopics]);

    const hasTopics = mainTopics.length > 0;
    const hasPropositions = propositionTopics.length > 0;
    const hasContent = hasTopics || hasPropositions;

    return (
        <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
            <Box sx={{ position: 'absolute', top: 12, right: 12, zIndex: 5 }}>
                <Tooltip title="Add topic" arrow>
                    <IconButton onClick={handleOpenCreate} size="small"
                        sx={(theme) => ({
                            width: 30, height: 30, borderRadius: 1.5,
                            bgcolor: alpha(theme.palette.background.paper, 0.6),
                            backdropFilter: 'blur(8px)',
                            color: alpha(theme.palette.text.secondary, 0.5),
                            '&:hover': { bgcolor: alpha(theme.palette.primary.main, 0.1), color: theme.palette.primary.light },
                        })}>
                        <AddIcon sx={{ fontSize: 14 }} />
                    </IconButton>
                </Tooltip>
            </Box>

            {showCreatePrompt && (
                <Box sx={(theme) => ({
                    mx: 3, mb: 0, p: 1.5, borderRadius: 2,
                    bgcolor: alpha(theme.palette.background.paper, 0.5),
                    border: '1px solid', borderColor: alpha(theme.palette.primary.main, 0.15),
                    display: 'flex', alignItems: 'center', gap: 1,
                })}>
                    <TextField inputRef={createInputRef} fullWidth size="small" placeholder="Topic name..."
                        value={newTopicName} onChange={(e) => setNewTopicName(e.target.value)}
                        onKeyDown={(e) => { if (e.key === 'Enter') handleCreateTopic(); if (e.key === 'Escape') { setShowCreatePrompt(false); setNewTopicName(''); } }}
                        variant="outlined"
                        slotProps={{ input: { sx: (theme) => ({ fontSize: '0.8rem', borderRadius: 1.5, bgcolor: alpha(theme.palette.background.default, 0.3), '& fieldset': { border: 'none' }, '& input': { py: 1, '&::placeholder': { color: alpha(theme.palette.text.secondary, 0.35), opacity: 1 } } }) } }}
                    />
                    <Tooltip title="Create" arrow>
                        <IconButton size="small" disabled={!newTopicName.trim()} onClick={handleCreateTopic}
                            sx={(theme) => ({ width: 34, height: 34, borderRadius: 1.5, bgcolor: newTopicName.trim() ? alpha(theme.palette.primary.main, 0.15) : 'transparent', color: newTopicName.trim() ? theme.palette.primary.light : alpha(theme.palette.text.disabled, 0.3), transition: 'all 0.15s ease', '&:hover': newTopicName.trim() ? { bgcolor: alpha(theme.palette.primary.main, 0.25) } : {} })}>
                            <AddIcon sx={{ fontSize: 16 }} />
                        </IconButton>
                    </Tooltip>
                </Box>
            )}

            <Box ref={canvasRef} data-canvas="true" onMouseDown={handleCanvasMouseDown}
                sx={(t) => ({
                    flex: 1, position: 'relative', overflow: 'hidden',
                    cursor: panning ? 'grabbing' : 'grab',
                    bgcolor: 'transparent',
                    backgroundImage: (() => {
                        const gridColor = t.palette.mode === 'dark'
                            ? alpha(t.palette.primary.main, 0.04)
                            : alpha(t.palette.primary.main, 0.06);
                        return `linear-gradient(to right, ${gridColor} 1px, transparent 1px), linear-gradient(to bottom, ${gridColor} 1px, transparent 1px)`;
                    })(),
                    backgroundSize: '24px 24px',
                })}
            >
                {!hasContent ? (
                    <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', flexDirection: 'column', gap: 2.5 }}>
                        <Box sx={(theme) => ({ width: 72, height: 72, borderRadius: 2, background: `linear-gradient(135deg, ${alpha(theme.palette.primary.main, 0.15)} 0%, ${alpha(theme.palette.primary.light, 0.08)} 100%)`, border: '1px solid', borderColor: alpha(theme.palette.primary.main, 0.1), display: 'flex', alignItems: 'center', justifyContent: 'center', animation: 'pulseGlow 2s ease-in-out infinite', '@keyframes pulseGlow': { '0%, 100%': { boxShadow: `0 0 20px ${alpha(theme.palette.primary.main, 0.1)}` }, '50%': { boxShadow: `0 0 40px ${alpha(theme.palette.primary.main, 0.25)}` } } })}>
                            <AddIcon sx={(theme) => ({ fontSize: 28, color: theme.palette.primary.light })} />
                        </Box>
                        <Typography sx={(theme) => ({ fontWeight: 600, color: alpha(theme.palette.text.primary, 0.6), fontSize: '0.9rem' })}>
                            {hasClassified ? 'No topics extracted yet' : 'Building your canvas...'}
                        </Typography>
                    </Box>
                ) : !hasTopics && hasPropositions ? (
                    <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', flexDirection: 'column', gap: 3, px: 4 }}>
                        <Box sx={{ textAlign: 'center' }}>
                            <Typography sx={(theme) => ({ fontWeight: 600, color: alpha(theme.palette.text.primary, 0.7), fontSize: '0.95rem', mb: 0.5 })}>
                                {propositionTopics.length} suggestion{propositionTopics.length !== 1 ? 's' : ''} found
                            </Typography>
                            <Typography sx={(theme) => ({ fontWeight: 400, color: alpha(theme.palette.text.secondary, 0.5), fontSize: '0.78rem', lineHeight: 1.6 })}>
                                Click a topic to explore it and add it to your canvas.
                            </Typography>
                        </Box>
                        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, justifyContent: 'center', maxWidth: 400 }}>
                            {propositionTopics.map(topic => (
                                <Chip key={topic.id} label={formatLabel(topic.name)} onClick={() =>handleSuggestionClick(formatLabel(topic.name), topic.id)}
                                    sx={(theme) => ({ height: 32, fontSize: '0.78rem', fontWeight: 600, borderRadius: '8px', px: 1, bgcolor: alpha(theme.palette.primary.main, 0.08), color: theme.palette.primary.light, border: '1px solid', borderColor: alpha(theme.palette.primary.main, 0.15), cursor: 'pointer', transition: 'all 0.2s', '&:hover': { bgcolor: alpha(theme.palette.primary.main, 0.16), borderColor: alpha(theme.palette.primary.main, 0.3), transform: 'translateY(-1px)' } })}
                                />
                            ))}
                        </Box>
                    </Box>
                ) : (
                    <Box sx={{ position: 'absolute', inset: 0, transform: `translate(${view.x}px, ${view.y}px) scale(${view.scale})`, transformOrigin: '0 0', pointerEvents: 'none' }}>
                        <EdgeLines edges={visibleEdges} topics={[...mainTopics, ...(exploringSuggestion ? propositionTopics.filter(p => p.name === exploringSuggestion.name) : [])]} onDeleteEdge={deleteEdge} brainstormingId={brainstormingId} onExploreEdge={handleExploreEdge} />

                        {connectionEdges.length > 0 && (
                            <svg style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', pointerEvents: 'none', zIndex: 0 }}>
                                {connectionEdges.map(edge => {
                                    const source = mainTopics.find(t => t.id === edge.source_topic_id);
                                    const target = mainTopics.find(t => t.id === edge.target_topic_id);
                                    if (!source || !target) return null;
                                    const pts = closestAnchors(source, target);
                                    return <line key={edge.id} x1={pts.ax} y1={pts.ay} x2={pts.bx} y2={pts.by} stroke={alpha(theme.palette.primary.light, 0.18)} strokeWidth={2} strokeDasharray="5 4" />;
                                })}
                            </svg>
                        )}

                        {linkLine && (
                            <svg style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', pointerEvents: 'none', zIndex: 15 }}>
                                <line x1={linkLine.x1} y1={linkLine.y1} x2={linkLine.x2} y2={linkLine.y2} stroke="#94a3b8" strokeWidth={2} strokeDasharray="6 4" opacity={0.7} />
                            </svg>
                        )}

                        {topicsWithSuggestions.map(topic => {
                            const libEntry = (libraryData || []).flatMap(f => f.entries || []).find(e => e.topic_id === topic.id);
                            return (
                                <Box key={topic.id} sx={{ pointerEvents: 'auto' }}>
                                    <TopicCard topic={topic}
                                        isSelected={selectedTopic?.id === topic.id}
                                        exploringName={exploringSuggestion?.name}
                                        libraryEntry={libEntry}
                                        onSelect={(t, isSuggestion) => handleSelect(t, topic.id, isSuggestion)}
                                        onDragStart={handleDragStart}
                                        onLinkStart={handleLinkStart}
                                        onDelete={handleDeleteTopic}
                                        onUpdate={updateTopic}
                                        brainstormingId={brainstormingId}
                                        onGenerate={handleGenerate}
                                        onOutlineChange={updateOutline}
                                        generating={generatingTopicId === topic.id}
                                        generatedContent={generatingTopicId === topic.id ? generatedContent : ''}
                                    />
                                </Box>
                            );
                        })}

                        {exploringSuggestion && (() => {
                            const source = mainTopics.find(t => t.id === exploringSuggestion.sourceTopicId);
                            if (!source) return null;
                            return (
                                <Box sx={{ position: 'absolute', left: (source.position_x || 0) + 260, top: (source.position_y || 0) + 60, px: 2.5, py: 2, borderRadius: 2, minWidth: 160, maxWidth: 240, border: '1.5px solid', borderColor: alpha(theme.palette.primary.main, 0.2), bgcolor: alpha(theme.palette.background.paper, 0.8), pointerEvents: 'none', zIndex: 5, boxShadow: `0 2px 12px ${alpha(theme.palette.primary.main, 0.08)}` }}>
                                    <Typography sx={{ fontSize: '0.825rem', fontWeight: 600, color: alpha(theme.palette.text.primary, 0.6), lineHeight: 1.3, mb: 1.5 }}>{formatLabel(exploringSuggestion.name)}</Typography>
                                    <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}><CircularProgress size={20} sx={(t) => ({ color: alpha(t.palette.primary.light, 0.7) })} /></Box>
                                </Box>
                            );
                        })()}

                        {exploringEdge && (() => {
                            const { x, y, sourceName, targetName, sourceId, targetId } = exploringEdge;
                            const sourceTopic = mainTopics.find(t => t.id === sourceId);
                            const targetTopic = mainTopics.find(t => t.id === targetId);
                            return (<>
                                <svg style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', pointerEvents: 'none', zIndex: 4 }}>
                                    {sourceTopic && <line x1={(sourceTopic.position_x || 0) + 90} y1={(sourceTopic.position_y || 0) + 35} x2={x} y2={y} stroke={alpha(theme.palette.primary.light, 0.18)} strokeWidth={2} strokeDasharray="5 4" />}
                                    {targetTopic && <line x1={(targetTopic.position_x || 0) + 90} y1={(targetTopic.position_y || 0) + 35} x2={x} y2={y} stroke={alpha(theme.palette.primary.light, 0.18)} strokeWidth={2} strokeDasharray="5 4" />}
                                </svg>
                                <Box sx={{ position: 'absolute', left: x - 100, top: y - 10, width: 200, minHeight: 60, px: 2.5, py: 2, borderRadius: 2, border: '1.5px solid', borderColor: alpha(theme.palette.primary.main, 0.2), bgcolor: alpha(theme.palette.background.paper, 0.8), pointerEvents: 'none', zIndex: 5, boxShadow: `0 2px 12px ${alpha(theme.palette.primary.main, 0.08)}` }}>
                                    <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 0.5, mb: 1.5 }}>
                                        <LinkIcon sx={(t) => ({ fontSize: 12, color: alpha(t.palette.primary.light, 0.5) })} />
                                        <Typography sx={{ fontSize: '0.68rem', fontWeight: 600, color: alpha(theme.palette.text.primary, 0.5) }}>{sourceName} ↔ {targetName}</Typography>
                                    </Box>
                                    <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}><CircularProgress size={18} sx={(t) => ({ color: alpha(t.palette.primary.light, 0.7) })} /></Box>
                                </Box>
                            </>);
                        })()}
                    </Box>
                )}
                {hasTopics && (
                    <CanvasMinimap
                        topics={topics}
                        edges={allEdges}
                        view={view}
                        canvasSize={canvasSize}
                        onNavigate={setView}
                    />
                )}
            </Box>
        </Box>
    );
}

export default CanvasTab;
