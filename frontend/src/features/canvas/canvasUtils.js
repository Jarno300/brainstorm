/**
 * Canvas geometry utilities — card positioning, anchors, edge routing.
 */

export function formatLabel(value) {
    return String(value || '')
        .replace(/-/g, ' ')
        .replace(/\b\w/g, c => c.toUpperCase());
}

export function getImportanceColor(importance, theme) {
    const isDark = theme.palette.mode === 'dark';
    const colors = {
        core: isDark ? '#fbbf24' : '#b45309',
        high: isDark ? '#5eead4' : '#0f766e',
        medium: isDark ? '#a78bfa' : '#7c3aed',
        low: isDark ? '#94a3b8' : '#475569',
    };
    return colors[importance] || colors.low;
}

export function computeImportance(confidence) {
    if (confidence >= 0.8) return 'core';
    if (confidence >= 0.6) return 'high';
    if (confidence >= 0.3) return 'medium';
    return 'low';
}

export function randomOffset(seed) {
    const angle = ((seed * 137.5) % 360) * (Math.PI / 180);
    const dist = 180 + (seed % 3) * 60;
    return { x: Math.cos(angle) * dist, y: Math.sin(angle) * dist };
}

export function getCardCenter(topic) {
    return {
        x: (topic.position_x || 0) + 90,
        y: (topic.position_y || 0) + 35,
    };
}

/** Card rectangle — uses DOM for real dimensions, falls back to estimates. */
export function getCardRect(topic) {
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

/** 4 anchor positions for a card: top, bottom, left, right. */
export function getAnchors(topic) {
    const r = getCardRect(topic);
    return [
        { side: 'top',    x: r.x + r.w / 2, y: r.y },
        { side: 'bottom', x: r.x + r.w / 2, y: r.y + r.h },
        { side: 'left',   x: r.x,           y: r.y + r.h / 2 },
        { side: 'right',  x: r.x + r.w,     y: r.y + r.h / 2 },
    ];
}

/** Find the closest anchor pair between two cards. Returns { ax, ay, bx, by }. */
export function closestAnchors(topicA, topicB) {
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

