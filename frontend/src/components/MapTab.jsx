import { useEffect, useMemo } from 'react';
import {
    Box, Typography, IconButton, Tooltip, Chip, alpha, useTheme, CircularProgress,
} from '@mui/material';
import {
    Hub as HubIcon,
    Refresh as RefreshIcon,
} from '@mui/icons-material';
import ReactFlow, {
    Background,
    Handle,
    Position,
    MarkerType,
    MiniMap,
    useEdgesState,
    useNodesState,
} from 'reactflow';
import 'reactflow/dist/style.css';

// ─── Theme-derived colour helpers ────────────────────────────
function getImportanceColors(theme) {
    const isDark = theme.palette.mode === 'dark';
    const p = theme.palette;
    return {
        core: {
            border: alpha(p.primary.main, isDark ? 0.4 : 0.35),
            text: p.primary.light,
            glow: alpha(p.primary.main, isDark ? 0.2 : 0.15),
            nodeBg: alpha(p.primary.main, isDark ? 0.08 : 0.06),
        },
        high: {
            border: alpha(p.primary.light, isDark ? 0.35 : 0.28),
            text: p.primary.light,
            glow: alpha(p.primary.light, isDark ? 0.15 : 0.1),
            nodeBg: alpha(p.primary.light, isDark ? 0.06 : 0.04),
        },
        medium: {
            border: alpha(p.secondary.main, isDark ? 0.3 : 0.25),
            text: p.secondary.light,
            glow: alpha(p.secondary.main, isDark ? 0.12 : 0.08),
            nodeBg: alpha(p.secondary.main, isDark ? 0.05 : 0.03),
        },
        low: {
            border: alpha(p.text.secondary, isDark ? 0.2 : 0.15),
            text: p.text.secondary,
            glow: alpha(p.text.secondary, isDark ? 0.08 : 0.05),
            nodeBg: alpha(p.text.secondary, isDark ? 0.04 : 0.025),
        },
    };
}

function getSuggestionColors(theme) {
    const p = theme.palette;
    return {
        border: alpha(p.text.secondary, 0.28),
        text: p.text.secondary,
        glow: alpha(p.text.secondary, 0.12),
        nodeBg: alpha(p.text.secondary, 0.06),
    };
}

function formatLabel(value) {
    return String(value || '').replace(/-/g, ' ');
}


function titleCase(value) {
    return String(value || '')
        .replace(/-/g, ' ')
        .split(' ')
        .filter(Boolean)
        .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
        .join(' ');
}

function getConnectorPositions(sourcePosition, targetPosition) {
    const deltaX = targetPosition.x - sourcePosition.x;
    const deltaY = targetPosition.y - sourcePosition.y;

    if (Math.abs(deltaX) >= Math.abs(deltaY)) {
        return {
            sourcePosition: deltaX >= 0 ? Position.Right : Position.Left,
            targetPosition: deltaX >= 0 ? Position.Left : Position.Right,
        };
    }

    return {
        sourcePosition: deltaY >= 0 ? Position.Bottom : Position.Top,
        targetPosition: deltaY >= 0 ? Position.Top : Position.Bottom,
    };
}

// ─── Helpers ──────────────────────────────────────────────────
function computeImportance(confidence) {
    if (confidence >= 0.8) return 'core';
    if (confidence >= 0.6) return 'high';
    if (confidence >= 0.3) return 'medium';
    return 'low';
}

function buildSolidAdjacency(topics, edges) {
    const adjacency = new Map(topics.map((topic) => [String(topic.id), new Set()]));

    edges.forEach((edge) => {
        if (edge.relationship === 'suggestion') return;
        const sourceId = String(edge.source_topic_id);
        const targetId = String(edge.target_topic_id);
        if (!adjacency.has(sourceId) || !adjacency.has(targetId)) return;
        adjacency.get(sourceId).add(targetId);
        adjacency.get(targetId).add(sourceId);
    });

    return adjacency;
}

function getTopicScore(topic, adjacency) {
    if (!topic) return 0;
    const degree = adjacency.get(String(topic.id))?.size || 0;
    return (topic.confidence || 0) * 100 + degree * 12 + (topic.is_proposition ? -5 : 0);
}

function getConnectedComponents(topics, adjacency) {
    const remaining = new Set(topics.map((topic) => String(topic.id)));
    const components = [];

    while (remaining.size > 0) {
        const [seed] = remaining;
        const queue = [seed];
        const component = [];
        remaining.delete(seed);

        while (queue.length > 0) {
            const current = queue.shift();
            component.push(current);
            const neighbors = adjacency.get(current) || new Set();
            neighbors.forEach((neighbor) => {
                if (remaining.has(neighbor)) {
                    remaining.delete(neighbor);
                    queue.push(neighbor);
                }
            });
        }

        components.push(component);
    }

    return components;
}

function buildTopicPositions(topics, edges) {
    const adjacency = buildSolidAdjacency(topics, edges);
    const regularTopics = topics.filter((topic) => !topic.is_proposition);
    const components = getConnectedComponents(regularTopics, adjacency);
    const positions = {};
    const componentOrbitRadius = components.length > 1 ? 560 : 0;

    components
        .sort((left, right) => right.length - left.length)
        .forEach((component, componentIndex) => {
            const componentTopics = component
                .map((id) => regularTopics.find((topic) => String(topic.id) === id))
                .filter(Boolean)
                .sort((left, right) => getTopicScore(right, adjacency) - getTopicScore(left, adjacency));

            const centerAngle = components.length === 1
                ? -Math.PI / 2
                : (2 * Math.PI * componentIndex) / components.length - Math.PI / 2;
            const center = {
                x: componentOrbitRadius * Math.cos(centerAngle),
                y: componentOrbitRadius * Math.sin(centerAngle),
            };

            const rootTopic = componentTopics[0];
            if (!rootTopic) return;
            positions[String(rootTopic.id)] = center;

            const layers = new Map();
            const visited = new Set([String(rootTopic.id)]);
            const queue = [{ id: String(rootTopic.id), depth: 0 }];

            while (queue.length > 0) {
                const current = queue.shift();
                const nextDepth = current.depth + 1;
                const neighborIds = [...(adjacency.get(current.id) || [])].sort(
                    (left, right) => getTopicScore(
                        regularTopics.find((topic) => String(topic.id) === right),
                        adjacency,
                    ) - getTopicScore(
                        regularTopics.find((topic) => String(topic.id) === left),
                        adjacency,
                    ),
                );

                neighborIds.forEach((neighbor) => {
                    if (visited.has(neighbor)) return;
                    visited.add(neighbor);
                    if (!layers.has(nextDepth)) layers.set(nextDepth, []);
                    layers.get(nextDepth).push(neighbor);
                    queue.push({ id: neighbor, depth: nextDepth });
                });
            }

            [...layers.entries()].sort((left, right) => left[0] - right[0]).forEach(([depth, layerTopicIds]) => {
                const radius = 190 + depth * 195;
                const spread = Math.min(Math.PI * 1.55, Math.PI + layerTopicIds.length * 0.18);
                const baseAngle = -Math.PI / 2;

                layerTopicIds.forEach((topicId, topicIndex) => {
                    const angle = layerTopicIds.length === 1
                        ? baseAngle
                        : baseAngle - spread / 2 + (spread * topicIndex) / (layerTopicIds.length - 1);
                    positions[topicId] = {
                        x: center.x + radius * Math.cos(angle),
                        y: center.y + radius * Math.sin(angle),
                    };
                });
            });
        });

    return { positions, adjacency };
}

function pickSuggestedTopics(sourceTopic, regularTopics, adjacency, takenNames) {
    const sourceId = String(sourceTopic.id);
    const sourceLabel = formatLabel(sourceTopic.name);
    const sourceWords = new Set(sourceLabel.toLowerCase().split(/\s+/).filter(Boolean));
    const directNeighbors = adjacency.get(sourceId) || new Set();

    const rankedCandidates = regularTopics
        .filter((candidate) => String(candidate.id) !== sourceId)
        .map((candidate) => {
            const candidateId = String(candidate.id);
            const candidateLabel = formatLabel(candidate.name);
            const candidateWords = candidateLabel.toLowerCase().split(/\s+/).filter(Boolean);
            const sharedWords = candidateWords.filter((word) => sourceWords.has(word)).length;
            const sharedNeighbors = [...(adjacency.get(candidateId) || new Set())]
                .filter((neighborId) => directNeighbors.has(neighborId)).length;

            return {
                topic: candidate,
                score: sharedWords * 3 + sharedNeighbors * 2 + (adjacency.get(candidateId)?.size || 0),
            };
        })
        .sort((left, right) => right.score - left.score);

    const picked = [];
    rankedCandidates.forEach(({ topic }) => {
        if (picked.length >= 3) return;
        const label = formatLabel(topic.name);
        const normalized = label.toLowerCase();
        if (takenNames.has(normalized)) return;
        takenNames.add(normalized);
        picked.push({
            id: `suggestion-${sourceId}-${topic.id}`,
            label,
            sourceTopicId: sourceId,
            sourceTopicName: sourceLabel,
            isSynthetic: true,
        });
    });

    return picked;

}

function buildSuggestionPosition(sourcePosition, index, total) {
    const angleByIndex = [(-150 * Math.PI) / 180, -Math.PI / 2, (-30 * Math.PI) / 180];
    const radiusByIndex = [245, 295, 245];
    const fallbackAngle = total <= 1 ? -Math.PI / 2 : (-90 + ((index - (total - 1) / 2) * 40)) * (Math.PI / 180);
    const angle = angleByIndex[index] ?? fallbackAngle;
    const radius = radiusByIndex[index] ?? 260;

    return {
        x: sourcePosition.x + radius * Math.cos(angle),
        y: sourcePosition.y + radius * Math.sin(angle),
    };
}

// ─── Topic Node ───────────────────────────────────────────────
function TopicNode({ data, selected }) {
    const theme = useTheme();
    const isDark = theme.palette.mode === 'dark';
    const impColors = getImportanceColors(theme);
    const colors = impColors[data.importance] || impColors.low;

    return (
        <Box
            sx={{
                px: 2,
                py: 1.5,
                borderRadius: 1.5,
                bgcolor: isDark
                    ? alpha(colors.nodeBg, 0.6)
                    : alpha(colors.nodeBg, 0.4),
                border: '1.5px solid',
                borderColor: selected ? colors.text : colors.border,
                cursor: 'pointer',
                minWidth: 140,
                maxWidth: 220,
                transition: 'all 0.2s ease',
                boxShadow: selected
                    ? `0 0 20px ${colors.glow}, 0 4px 12px rgba(0,0,0,0.15)`
                    : `0 2px 8px rgba(0,0,0,0.08)`,
                '&:hover': {
                    boxShadow: `0 0 24px ${colors.glow}, 0 6px 16px rgba(0,0,0,0.12)`,
                    borderColor: colors.text,
                },
                position: 'relative',
            }}
        >
            <Handle
                type="target"
                position={Position.Top}
                style={{
                    width: 8, height: 8,
                    background: colors.text,
                    border: `2px solid ${alpha(colors.text, 0.3)}`,
                    opacity: 0.6,
                }}
            />
            <Typography
                sx={{
                    fontSize: '0.825rem',
                    fontWeight: 600,
                    color: theme.palette.text.primary,
                    lineHeight: 1.4,
                }}
            >
                {data.label}
            </Typography>
            <Handle
                type="source"
                position={Position.Bottom}
                style={{
                    width: 8, height: 8,
                    background: colors.text,
                    border: `2px solid ${alpha(colors.text, 0.3)}`,
                    opacity: 0.6,
                }}
            />
        </Box>
    );
}

// ─── Suggestion Node ──────────────────────────────────────────
function SuggestionNode({ data, selected }) {
    const theme = useTheme();
    const sugColors = getSuggestionColors(theme);

    return (
        <Box
            sx={{
                px: 1.75,
                py: 1,
                borderRadius: 1.5,
                bgcolor: alpha(sugColors.nodeBg, 0.8),
                border: '1.5px dashed',
                borderColor: selected
                    ? sugColors.text
                    : sugColors.border,
                cursor: 'pointer',
                minWidth: 120,
                maxWidth: 180,
                transition: 'all 0.2s ease',
                boxShadow: selected
                    ? `0 0 20px ${sugColors.glow}, 0 4px 12px rgba(0,0,0,0.12)`
                    : `0 2px 6px rgba(0,0,0,0.06)`,
                '&:hover': {
                    boxShadow: `0 0 20px ${sugColors.glow}, 0 6px 14px rgba(0,0,0,0.1)`,
                    borderColor: sugColors.text,
                },
                position: 'relative',
                display: 'flex',
                alignItems: 'center',
                gap: 0.75,
            }}
        >
            <Handle
                type="target"
                position={Position.Top}
                style={{
                    width: 7, height: 7,
                    background: sugColors.text,
                    border: `2px solid ${alpha(sugColors.text, 0.3)}`,
                    opacity: 0.5,
                }}
            />
            <Box
                sx={{
                    width: 6, height: 6,
                    borderRadius: '50%',
                    bgcolor: alpha(sugColors.text, 0.4),
                    flexShrink: 0,
                }}
            />
            <Box sx={{ flex: 1, minWidth: 0 }}>
                <Typography
                    sx={{
                        fontSize: '0.78rem',
                        fontWeight: 500,
                        color: theme.palette.text.primary,
                        lineHeight: 1.3,
                    }}
                >
                    {data.label}
                </Typography>
            </Box>
            <Handle
                type="source"
                position={Position.Bottom}
                style={{
                    width: 7, height: 7,
                    background: sugColors.text,
                    border: `2px solid ${alpha(sugColors.text, 0.3)}`,
                    opacity: 0.5,
                }}
            />
        </Box>
    );
}

// ─── Inner canvas ────────────────────────────────────────────
function MapCanvas({ mapData, onSuggestionClick }) {
    const theme = useTheme();
    const isDark = theme.palette.mode === 'dark';

    const topics = useMemo(() => mapData?.topics || [], [mapData]);
    const edges = useMemo(() => mapData?.edges || [], [mapData]);
    const suggestions = useMemo(() => mapData?.suggestions || [], [mapData]);
    const regularTopics = useMemo(
        () => topics.filter((topic) => !topic.is_proposition),
        [topics],
    );

    // Build reactflow nodes and edges from data
    const { flowNodes, flowEdges } = useMemo(() => {
        const { positions, adjacency } = buildTopicPositions(topics, edges);

        const topicNodes = regularTopics.map((topic) => ({
            id: String(topic.id),
            type: 'topic',
            position: positions[String(topic.id)] || { x: 0, y: 0 },
            data: {
                label: formatLabel(topic.name),
                importance: topic.importance || computeImportance(topic.confidence),
                mentionCount: Math.max(1, Math.round((topic.confidence || 0.3) * 5)),
            },
        }));

        const suggestionNodes = [];
        const suggestionEdges = [];
        const sourceSuggestions = new Map();

        const PLACEHOLDER_PATTERNS = [
            /^the topic$/i, /^insert date/i, /^related topics?$/i,
            /^topic name$/i, /^your topic/i, /^example$/i,
            /^lorem ipsum/i, /^placeholder/i, /^click here/i,
            /^[•·\-—]\s*$/, /^[0-9]+\.[0-9]+$/,
        ];
        const isPlaceholder = (label) => PLACEHOLDER_PATTERNS.some((p) => p.test(label.trim()));

        suggestions.forEach((suggestion) => {
            const label = formatLabel(suggestion.name);
            if (isPlaceholder(label)) return;
            const sourceId = String(suggestion.source_topic_id);
            if (!sourceSuggestions.has(sourceId)) sourceSuggestions.set(sourceId, []);
            sourceSuggestions.get(sourceId).push({
                id: `suggestion-${sourceId}-${suggestion.id}`,
                label,
                sourceTopicId: sourceId,
                sourceTopicName: formatLabel(suggestion.source_topic_name),
                isSynthetic: false,
            });
        });

        regularTopics.forEach((topic) => {
            const sourceId = String(topic.id);
            const takenNames = new Set((sourceSuggestions.get(sourceId) || []).map((item) => item.label.toLowerCase()));
            const selectedSuggestions = [...(sourceSuggestions.get(sourceId) || [])];
            const filledSuggestions = pickSuggestedTopics(topic, regularTopics, adjacency, takenNames);

            filledSuggestions.forEach((entry) => {
                if (selectedSuggestions.length >= 3) return;
                if (selectedSuggestions.some((item) => item.label.toLowerCase() === entry.label.toLowerCase())) return;
                selectedSuggestions.push(entry);
            });

            selectedSuggestions.slice(0, 3).forEach((entry, index) => {
                const count = Math.min(selectedSuggestions.length, 3);
                const position = buildSuggestionPosition(positions[sourceId] || { x: 0, y: 0 }, index, count);
                const sourcePosition = position;
                const targetPosition = positions[sourceId] || { x: 0, y: 0 };
                const connector = getConnectorPositions(sourcePosition, targetPosition);
                suggestionNodes.push({
                    id: entry.id,
                    type: 'suggestion',
                    position,
                    data: entry,
                });
                suggestionEdges.push({
                    id: `${sourceId}--${entry.id}`,
                    source: entry.id,
                    target: sourceId,
                    type: 'smoothstep',
                    sourcePosition: connector.sourcePosition,
                    targetPosition: connector.targetPosition,
                    style: {
                        stroke: alpha(theme.palette.text.secondary, 0.55),
                        strokeWidth: 1.5,
                        strokeDasharray: '6 5',
                    },
                    markerEnd: {
                        type: MarkerType.ArrowClosed,
                        color: alpha(theme.palette.text.secondary, 0.55),
                        width: 15,
                        height: 15,
                    },
                });
            });
        });

        const builtEdges = edges
            .filter((edge) => edge.relationship !== 'suggestion')
            .map((edge) => ({
                id: String(edge.id),
                source: String(edge.source_topic_id),
                target: String(edge.target_topic_id),
                type: 'smoothstep',
                style: {
                    stroke: alpha(theme.palette.primary.light, 0.4),
                    strokeWidth: 2.25,
                },
                markerEnd: {
                    type: MarkerType.ArrowClosed,
                    color: alpha(theme.palette.primary.light, 0.45),
                    width: 16,
                    height: 16,
                },
            }))
            .concat(suggestionEdges);

        return {
            flowNodes: [...topicNodes, ...suggestionNodes],
            flowEdges: builtEdges,
        };
    }, [topics, edges, suggestions, regularTopics]);

    const [nodes, setNodes, onNodesChange] = useNodesState(flowNodes);
    const [canvasEdges, setCanvasEdges, onEdgesChange] = useEdgesState(flowEdges);

    useEffect(() => {
        setNodes(flowNodes);
        setCanvasEdges(flowEdges);
    }, [flowNodes, flowEdges, setNodes, setCanvasEdges]);

    // Create a stable key so reactflow remounts cleanly when data changes
    const dataKey = `${topics.length}-${edges.length}-${suggestions.length}-${isDark}`;

    const nodeTypes = useMemo(
        () => ({ topic: TopicNode, suggestion: SuggestionNode }),
        [],
    );

    return (
        <Box sx={{ width: '100%', height: '100%', position: 'relative' }}>
            <ReactFlow
                key={dataKey}
                nodes={nodes}
                edges={canvasEdges}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                onNodeClick={(_, node) => {
                    console.log('[DEBUG] ReactFlow node click:', node.id, 'type:', node.type, 'label:', node.data?.label);
                    if (node.type === 'suggestion') {
                        console.log('[DEBUG] Triggering onSuggestionClick with:', node.data?.label);
                        onSuggestionClick?.(node.data?.label);
                    }
                }}
                nodeTypes={nodeTypes}
                nodesDraggable
                nodesConnectable={false}
                nodesFocusable={false}
                fitView
                fitViewOptions={{ padding: 0.32, duration: 300 }}
                minZoom={0.3}
                maxZoom={2.5}
                attributionPosition="bottom-left"
                defaultEdgeOptions={{
                    type: 'smoothstep',
                    style: { strokeWidth: 2 },
                }}
                style={{ width: '100%', height: '100%' }}
                proOptions={{ hideAttribution: true }}
            >
                <Background
                    variant="dots"
                    gap={22}
                    size={1}
                    color={isDark ? 'rgba(255,255,255,0.055)' : 'rgba(148,163,184,0.09)'}
                />
                <MiniMap
                    position="bottom-left"
                    pannable
                    zoomable
                    nodeStrokeWidth={2}
                    nodeColor={(node) => (node.type === 'suggestion' ? theme.palette.warning.light : theme.palette.primary.light)}
                    maskColor={isDark ? 'rgba(14,16,23,0.7)' : 'rgba(248,250,252,0.55)'}
                    style={{
                        height: 108,
                        width: 160,
                        borderRadius: 12,
                        overflow: 'hidden',
                        border: isDark ? '1px solid rgba(255,255,255,0.08)' : '1px solid rgba(148,163,184,0.16)',
                        background: isDark ? 'rgba(26,29,36,0.95)' : 'rgba(255,255,255,0.92)',
                        boxShadow: '0 8px 24px rgba(0,0,0,0.14)',
                    }}
                />
            </ReactFlow>
        </Box>
    );
}

// ─── Main MapTab component ────────────────────────────────────
function MapTab({ mapData, onRefresh, onSuggestionClick, brainstormTitle }) {
    const theme = useTheme();
    const topics = mapData?.topics || [];
    const regularTopics = topics.filter((t) => !t.is_proposition);

    return (
        <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
            {/* ── Header ──────────────────────────────────────────── */}
            <Box
                sx={(theme) => ({
                    px: 3, py: 1.75,
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                    borderBottom: '1px solid',
                    borderColor: alpha(theme.palette.divider, 0.5),
                    bgcolor: alpha(theme.palette.background.default, 0.3),
                })}
            >
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                    <Box
                        sx={(theme) => ({
                            width: 28, height: 28, borderRadius: 1.5,
                            background: `linear-gradient(135deg, ${alpha(theme.palette.primary.main, 0.2)} 0%, ${alpha(theme.palette.primary.light, 0.12)} 100%)`,
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                        })}
                    >
                        <HubIcon
                            sx={(theme) => ({ fontSize: 15, color: theme.palette.primary.light })}
                        />
                    </Box>
                    <Typography sx={{ fontWeight: 700, fontSize: '0.925rem', color: 'text.primary' }}>
                        Knowledge Map
                    </Typography>
                    {regularTopics.length > 0 && (
                        <Chip
                            label={`${regularTopics.length} topic${regularTopics.length !== 1 ? 's' : ''}`}
                            size="small"
                            sx={(theme) => ({
                                height: 20, fontSize: '0.6rem', fontWeight: 700, borderRadius: '6px',
                                bgcolor: alpha(theme.palette.primary.main, 0.1),
                                color: theme.palette.primary.light,
                                '& .MuiChip-label': { px: 0.8 },
                            })}
                        />
                    )}
                    {regularTopics.length > 0 && (
                        <Chip
                            label="3 suggestions each"
                            size="small"
                            sx={{
                                height: 20, fontSize: '0.6rem', fontWeight: 700, borderRadius: '6px',
                                bgcolor: alpha(theme.palette.warning.main, 0.1),
                                color: theme.palette.warning.light,
                                '& .MuiChip-label': { px: 0.8 },
                            }}
                        />
                    )}
                </Box>
                <Box sx={{ display: 'flex', gap: 0.5 }}>
                    <Tooltip title="Refresh suggestions" arrow>
                        <IconButton
                            onClick={onRefresh}
                            size="small"
                            sx={(theme) => ({
                                width: 30, height: 30, borderRadius: 1.5,
                                border: '1px solid',
                                borderColor: alpha(theme.palette.divider, 0.5),
                                color: alpha(theme.palette.text.secondary, 0.5),
                                transition: 'all 0.2s ease',
                                '&:hover': {
                                    bgcolor: alpha(theme.palette.primary.main, 0.08),
                                    color: theme.palette.primary.light,
                                    borderColor: alpha(theme.palette.primary.main, 0.15),
                                },
                            })}
                        >
                            <RefreshIcon sx={{ fontSize: 14 }} />
                        </IconButton>
                    </Tooltip>
                </Box>
            </Box>

            {/* ── Content ──────────────────────────────────────────── */}
            <Box sx={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
                {regularTopics.length === 0 ? (
                    <Box
                        sx={{
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                            height: '100%', flexDirection: 'column', gap: 2.5,
                        }}
                    >
                        <Box
                            sx={(theme) => ({
                                width: 72, height: 72, borderRadius: 2,
                                background: `linear-gradient(135deg, ${alpha(theme.palette.primary.main, 0.15)} 0%, ${alpha(theme.palette.primary.light, 0.08)} 100%)`,
                                border: '1px solid',
                                borderColor: alpha(theme.palette.primary.main, 0.1),
                                display: 'flex', alignItems: 'center', justifyContent: 'center',
                                position: 'relative',
                                '@keyframes pulseGlow': {
                                    '0%, 100%': { boxShadow: `0 0 20px ${alpha(theme.palette.primary.main, 0.1)}` },
                                    '50%': { boxShadow: `0 0 40px ${alpha(theme.palette.primary.main, 0.25)}` },
                                },
                                animation: 'pulseGlow 2s ease-in-out infinite',
                            })}
                        >
                            <HubIcon
                                sx={(theme) => ({
                                    fontSize: 28,
                                    color: theme.palette.primary.light,
                                    '@keyframes spin': {
                                        '0%': { transform: 'rotate(0deg)' },
                                        '100%': { transform: 'rotate(360deg)' },
                                    },
                                    animation: 'spin 3s linear infinite',
                                })}
                            />
                        </Box>
                        <Box sx={{ textAlign: 'center', maxWidth: 300 }}>
                            <Typography
                                sx={(theme) => ({
                                    fontWeight: 700,
                                    color: theme.palette.text.primary,
                                    mb: 0.75, fontSize: '1rem',
                                })}
                            >
                                Building your knowledge map
                            </Typography>
                            <Typography
                                sx={(theme) => ({
                                    fontWeight: 500,
                                    color: theme.palette.primary.light,
                                    mb: 1, fontSize: '0.85rem',
                                    fontStyle: 'italic',
                                })}
                            >
                                "{brainstormTitle || 'Untitled'}"
                            </Typography>
                            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 0.5 }}>
                                <CircularProgress size={12} sx={(t) => ({ color: alpha(t.palette.primary.light, 0.6) })} />
                                <Typography
                                    variant="body2"
                                    sx={(theme) => ({
                                        color: alpha(theme.palette.text.secondary, 0.55),
                                        lineHeight: 1.6,
                                        fontSize: '0.78rem',
                                    })}
                                >
                                    Analyzing and structuring knowledge...
                                </Typography>
                            </Box>
                        </Box>
                    </Box>
                ) : (
                    <MapCanvas mapData={mapData} onSuggestionClick={onSuggestionClick} />
                )}
            </Box>
        </Box>
    );
}

export default MapTab;
