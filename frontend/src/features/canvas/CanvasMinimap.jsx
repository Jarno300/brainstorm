import { useRef, useEffect, useState } from 'react';
import { Box, alpha, useTheme } from '@mui/material';

/**
 * Minimap — small overview of the full knowledge map canvas.
 *
 * Shows topic positions as dots, edges as lines, and a viewport rectangle
 * showing what's currently visible. Click/drag the viewport to navigate.
 */
export default function CanvasMinimap({ topics, edges, view, canvasSize, onNavigate }) {
    const theme = useTheme();
    const mapRef = useRef(null);
    const [dragging, setDragging] = useState(false);
    const dragStart = useRef(null);
    const viewAtStart = useRef(null);

    const SIZE = 160;
    const PADDING = 8;

    // Only main topics (not propositions)
    const mainTopics = (topics || []).filter(t => !t.is_proposition);
    if (mainTopics.length === 0) return null;

    // Compute content bounds
    const xs = mainTopics.map(t => t.position_x || 0);
    const ys = mainTopics.map(t => t.position_y || 0);
    const minX = Math.min(...xs);
    const minY = Math.min(...ys);
    const maxX = Math.max(...xs);
    const maxY = Math.max(...ys);
    const contentW = Math.max(maxX - minX + 220, 400);  // card width
    const contentH = Math.max(maxY - minY + 90, 300);   // card height

    const mapW = SIZE - PADDING * 2;
    const mapH = SIZE - PADDING * 2;
    const scaleX = mapW / contentW;
    const scaleY = mapH / contentH;
    const scale = Math.min(scaleX, scaleY);
    const offsetX = PADDING + (mapW - contentW * scale) / 2;
    const offsetY = PADDING + (mapH - contentH * scale) / 2;

    const toMap = (cx, cy) => ({
        x: offsetX + (cx - minX) * scale,
        y: offsetY + (cy - minY) * scale,
    });

    // Viewport rectangle
    const vpW = (canvasSize?.w || 800) / view.scale;
    const vpH = (canvasSize?.h || 600) / view.scale;
    const vpLeft = -view.x / view.scale;
    const vpTop = -view.y / view.scale;
    const vpMap = toMap(vpLeft, vpTop);
    const vpWMap = vpW * scale;
    const vpHMap = vpH * scale;

    // Non-suggestion edges
    const realEdges = (edges || []).filter(e =>
        !e.relationship?.startsWith('suggestion') && e.relationship !== 'connection_link'
    );

    const topicMap = Object.fromEntries(
        (topics || []).map(t => [t.id, t])
    );

    // Click-to-navigate
    const handleClick = (e) => {
        if (dragging) return;
        const rect = mapRef.current.getBoundingClientRect();
        const mx = e.clientX - rect.left;
        const my = e.clientY - rect.top;
        const cx = (mx - offsetX) / scale + minX;
        const cy = (my - offsetY) / scale + minY;
        const canvasW = canvasSize?.w || 800;
        const canvasH = canvasSize?.h || 600;
        onNavigate({
            x: canvasW / 2 - cx * view.scale,
            y: canvasH / 2 - cy * view.scale,
            scale: view.scale,
        });
    };

    const handleMouseDown = (e) => {
        setDragging(true);
        dragStart.current = { x: e.clientX, y: e.clientY };
        viewAtStart.current = { x: view.x, y: view.y };
    };

    useEffect(() => {
        if (!dragging) return;
        const handleMove = (e) => {
            const dx = (e.clientX - dragStart.current.x) * (contentW / mapW);
            const dy = (e.clientY - dragStart.current.y) * (contentH / mapH);
            onNavigate({
                x: viewAtStart.current.x - dx * view.scale,
                y: viewAtStart.current.y - dy * view.scale,
                scale: view.scale,
            });
        };
        const handleUp = () => setDragging(false);
        window.addEventListener('mousemove', handleMove);
        window.addEventListener('mouseup', handleUp);
        return () => {
            window.removeEventListener('mousemove', handleMove);
            window.removeEventListener('mouseup', handleUp);
        };
    }, [dragging, view.scale, onNavigate, contentW, mapW, contentH, mapH]);

    const dotColor = theme.palette.mode === 'dark'
        ? alpha(theme.palette.primary.light, 0.6)
        : alpha(theme.palette.primary.main, 0.5);
    const edgeColor = theme.palette.mode === 'dark'
        ? alpha('#fff', 0.12)
        : alpha('#000', 0.1);
    const vpColor = alpha(theme.palette.primary.main, 0.25);
    const bgColor = theme.palette.mode === 'dark'
        ? alpha('#000', 0.4)
        : alpha('#fff', 0.6);

    return (
        <Box
            ref={mapRef}
            onClick={handleClick}
            onMouseDown={handleMouseDown}
            sx={{
                position: 'absolute',
                bottom: 12,
                right: 12,
                width: SIZE,
                height: SIZE,
                borderRadius: 1.5,
                bgcolor: bgColor,
                backdropFilter: 'blur(12px)',
                border: '1px solid',
                borderColor: alpha(theme.palette.divider, 0.15),
                cursor: dragging ? 'grabbing' : 'pointer',
                zIndex: 10,
                overflow: 'hidden',
            }}
        >
            <svg width={SIZE} height={SIZE} style={{ display: 'block' }}>
                {/* Edges */}
                {realEdges.map(e => {
                    const s = topicMap[e.source_topic_id];
                    const t = topicMap[e.target_topic_id];
                    if (!s || !t) return null;
                    const a = toMap(s.position_x || 0, s.position_y || 0);
                    const b = toMap(t.position_x || 0, t.position_y || 0);
                    return (
                        <line key={`${e.source_topic_id}-${e.target_topic_id}`}
                            x1={a.x} y1={a.y} x2={b.x} y2={b.y}
                            stroke={edgeColor} strokeWidth={1}
                        />
                    );
                })}
                {/* Topic dots */}
                {mainTopics.map(t => {
                    const p = toMap(t.position_x || 0, t.position_y || 0);
                    return (
                        <circle key={t.id} cx={p.x} cy={p.y} r={3}
                            fill={dotColor}
                        />
                    );
                })}
                {/* Viewport rectangle */}
                <rect
                    x={vpMap.x} y={vpMap.y}
                    width={vpWMap} height={vpHMap}
                    fill={vpColor}
                    stroke={alpha(theme.palette.primary.main, 0.4)}
                    strokeWidth={1}
                    rx={2}
                />
            </svg>
        </Box>
    );
}
