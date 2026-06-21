import { useState, useEffect } from 'react';
import { Box, Tooltip, alpha, useTheme } from '@mui/material';
import { AutoAwesome as HubIcon, Delete as DeleteIcon } from '@mui/icons-material';
import { formatLabel, closestAnchors } from './canvasUtils';

function EdgeLines({ edges, topics, onDeleteEdge, brainstormingId, onExploreEdge }) {
    const theme = useTheme();
    const [hoveredEdge, setHoveredEdge] = useState(null);
    const [drawnEdges, setDrawnEdges] = useState(new Set());
    const topicMap = {};
    topics.forEach(t => { topicMap[t.id] = t; });
    const isConnectionCard = (id) => {
        const t = topicMap[id];
        return t?.name?.endsWith('-connection');
    };

    // Edge draw animation — mark edges as drawn after mount
    useEffect(() => {
        const timer = setTimeout(() => {
            setDrawnEdges(new Set(edges.map(e => e.id)));
        }, 50);
        return () => clearTimeout(timer);
    }, []);

    // Track new edges for draw animation
    useEffect(() => {
        setDrawnEdges(prev => {
            const next = new Set(prev);
            edges.forEach(e => next.add(e.id));
            return next;
        });
    }, [edges]);

    return (
        <svg style={{
            position: 'absolute', inset: 0,
            pointerEvents: 'none', zIndex: 1,
            width: '100%', height: '100%',
        }}>
            <style>{`@keyframes drawEdge { from { stroke-dashoffset: var(--edge-len, 1000); } to { stroke-dashoffset: 0; } }`}</style>
            <defs>
                {edges.map(edge => {
                    const s = topicMap[edge.source_topic_id];
                    const t = topicMap[edge.target_topic_id];
                    if (!s || !t) return null;
                    const pts = closestAnchors(s, t);
                    return (
                        <linearGradient key={`g-${edge.id}`} id={`edge-grad-${edge.id}`} gradientUnits="userSpaceOnUse"
                            x1={pts.ax} y1={pts.ay} x2={pts.bx} y2={pts.by}>
                            <stop offset="0%" stopColor={theme.palette.primary.light} stopOpacity="0.08" />
                            <stop offset="20%" stopColor={theme.palette.primary.light} stopOpacity="0.3" />
                            <stop offset="80%" stopColor={theme.palette.primary.light} stopOpacity="0.3" />
                            <stop offset="100%" stopColor={theme.palette.primary.light} stopOpacity="0.08" />
                        </linearGradient>
                    );
                })}
            </defs>
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
                        {/* Visible line */}
                        <line data-line="visible"
                            x1={s.x} y1={s.y} x2={t.x} y2={t.y}
                            stroke={hoveredEdge === edge.id
                                ? alpha(theme.palette.primary.light, 0.65)
                                : `url(#edge-grad-${edge.id})`}
                            strokeWidth={hoveredEdge === edge.id ? 3 : 2}
                            style={{
                                pointerEvents: 'none',
                                transition: 'stroke 0.25s ease, stroke-width 0.2s ease',
                                ...(!drawnEdges.has(edge.id) ? {
                                    strokeDasharray: Math.sqrt((t.x - s.x) ** 2 + (t.y - s.y) ** 2),
                                    strokeDashoffset: Math.sqrt((t.x - s.x) ** 2 + (t.y - s.y) ** 2),
                                    animation: `drawEdge 0.45s cubic-bezier(0.4, 0, 0.2, 1) forwards`,
                                } : {}),
                            }}
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

export default EdgeLines;
