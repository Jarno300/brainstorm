import { useRef, useMemo } from 'react';
import { useGSAP } from '@gsap/react';
import gsap from 'gsap';

// ─── Grid configuration ──────────────────────────────────

const COLS = 20;
const ROWS = 16;
const SPACING = 50;
const W = COLS * SPACING;  // 1000
const H = ROWS * SPACING;  // 800

// Cluster shapes: array of [col, row] offsets from cluster center
const CLUSTER_SHAPES = [
  // 2x2 square
  [[0,0],[1,0],[0,1],[1,1]],
  // 3x3 compact
  [[0,0],[1,0],[2,0],[0,1],[1,1],[2,1],[0,2],[1,2],[2,2]],
  // Diamond
  [[0,0],[1,0],[0,1],[1,1],[2,1],[1,2]],
  // L-shape
  [[0,0],[1,0],[0,1],[0,2],[1,2]],
  // Cross
  [[0,0],[1,0],[2,0],[1,1],[1,2]],
  // 2x3 rectangle
  [[0,0],[1,0],[0,1],[1,1],[0,2],[1,2]],
  // Diagonal line
  [[0,0],[1,1],[2,2],[3,3]],
  // T-shape
  [[0,0],[1,0],[2,0],[1,1],[1,2]],
];

// Pre-compute cluster positions spread across the grid
function generateClusterPositions(count) {
  const positions = [];
  // Avoid edges (1 col/row margin)
  for (let i = 0; i < count; i++) {
    const col = gsap.utils.random(1, COLS - 3, 1);
    const row = gsap.utils.random(1, ROWS - 3, 1);
    positions.push({ col, row });
  }
  return positions;
}

// Compute dot positions and edges for a cluster at a given grid position
function clusterElements(cx, cy, shape) {
  const dots = shape.map(([dx, dy]) => ({
    x: (cx + dx) * SPACING,
    y: (cy + dy) * SPACING,
    id: `${cx + dx}-${cy + dy}`,
  }));

  // Edges: connect adjacent dots in the cluster (Manhattan distance = 1)
  const edges = [];
  const seen = new Set();
  for (const a of dots) {
    for (const b of dots) {
      if (a === b) continue;
      const dx = Math.abs(a.x - b.x);
      const dy = Math.abs(a.y - b.y);
      if ((dx === SPACING && dy === 0) || (dy === SPACING && dx === 0)) {
        const key = [a.id, b.id].sort().join('|');
        if (!seen.has(key)) {
          seen.add(key);
          edges.push({ x1: a.x, y1: a.y, x2: b.x, y2: b.y });
        }
      }
    }
  }

  return { dots, edges };
}

// Generate all clusters
const CLUSTER_COUNT = 20;
const clusterPositions = generateClusterPositions(CLUSTER_COUNT);
const clusters = clusterPositions.map((pos) => {
  const shape = CLUSTER_SHAPES[Math.floor(Math.random() * CLUSTER_SHAPES.length)];
  return clusterElements(pos.col, pos.row, shape);
});

// ─── Component ────────────────────────────────────────────

export default function NetworkGraph() {
  const svgRef = useRef(null);
  const clusterGroupRefs = useRef([]);

  // Generate grid dots for the static pattern background
  const gridPatternId = 'grid-dots';

  useGSAP(() => {
    if (!svgRef.current) return;

    const masterTL = gsap.timeline({ repeat: -1 });

    // Activate clusters in waves
    for (let wave = 0; wave < 5; wave++) {
      const waveClusters = clusters.slice(wave * 4, (wave + 1) * 4);
      const groupEls = clusterGroupRefs.current.slice(wave * 4, (wave + 1) * 4);

      // Stagger each cluster within the wave
      groupEls.forEach((groupEl, i) => {
        if (!groupEl) return;

        // Ensure initial state: hidden
        gsap.set(groupEl.querySelectorAll('.cluster-dot'), { scale: 0, opacity: 0, transformOrigin: '50% 50%' });
        gsap.set(groupEl.querySelectorAll('.cluster-edge'), { strokeDasharray: '100%', strokeDashoffset: '100%', opacity: 0 });

        // Build cluster animation
        const clusterTL = gsap.timeline({ delay: i * 0.6 });

        // Dots appear
        clusterTL.to(
          groupEl.querySelectorAll('.cluster-dot'),
          {
            scale: 1,
            opacity: 0.7,
            duration: 0.4,
            ease: 'back.out(1.7)',
            stagger: 0.04,
          },
          0
        );

        // Edges draw in
        clusterTL.to(
          groupEl.querySelectorAll('.cluster-edge'),
          {
            strokeDashoffset: '0%',
            opacity: 0.5,
            duration: 0.5,
            ease: 'power2.inOut',
            stagger: 0.03,
          },
          0.15
        );

        // Hold lit
        clusterTL.to({}, { duration: 1.5 });

        // Fade out dots
        clusterTL.to(
          groupEl.querySelectorAll('.cluster-dot'),
          {
            scale: 0,
            opacity: 0,
            duration: 0.5,
            ease: 'power2.in',
            stagger: 0.03,
          },
          'fade'
        );

        // Fade out edges
        clusterTL.to(
          groupEl.querySelectorAll('.cluster-edge'),
          {
            opacity: 0,
            duration: 0.4,
            ease: 'power2.in',
          },
          'fade'
        );

        // Pause before next wave
        clusterTL.to({}, { duration: 1.2 });

        masterTL.add(clusterTL, wave * 5 + i * 0.4);
      });
    }
  }, []);

  return (
    <svg
      ref={svgRef}
      viewBox={`0 0 ${W} ${H}`}
      style={{ width: '100%', height: '100%', position: 'absolute', inset: 0 }}
      preserveAspectRatio="xMidYMid slice"
    >
      <defs>
        {/* Ambient radial glow */}
        <radialGradient id="hero-glow" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="rgba(202, 111, 78, 0.12)" />
          <stop offset="50%" stopColor="rgba(202, 111, 78, 0.03)" />
          <stop offset="100%" stopColor="transparent" />
        </radialGradient>

        {/* Dot grid pattern */}
        <pattern
          id={gridPatternId}
          width={SPACING}
          height={SPACING}
          patternUnits="userSpaceOnUse"
        >
          {/* Grid line fragments — cross shape at each intersection */}
          <line
            x1={SPACING / 2}
            y1={0}
            x2={SPACING / 2}
            y2={SPACING}
            stroke="rgba(202, 111, 78, 0.04)"
            strokeWidth={0.5}
          />
          <line
            x1={0}
            y1={SPACING / 2}
            x2={SPACING}
            y2={SPACING / 2}
            stroke="rgba(202, 111, 78, 0.04)"
            strokeWidth={0.5}
          />
          {/* Dot at intersection */}
          <circle
            cx={SPACING / 2}
            cy={SPACING / 2}
            r={1.2}
            fill="rgba(202, 111, 78, 0.12)"
          />
        </pattern>
      </defs>

      {/* Full grid background */}
      <rect x={0} y={0} width={W} height={H} fill="url(#grid-dots)" />

      {/* Ambient glow */}
      <circle cx={W / 2} cy={H / 2} r={W * 0.55} fill="url(#hero-glow)" />

      {/* Animated clusters */}
      {clusters.map((cluster, ci) => (
        <g
          key={`cluster-${ci}`}
          ref={(el) => { clusterGroupRefs.current[ci] = el; }}
        >
          {/* Cluster edges */}
          {cluster.edges.map((edge, ei) => (
            <line
              key={`ce-${ci}-${ei}`}
              className="cluster-edge"
              x1={edge.x1}
              y1={edge.y1}
              x2={edge.x2}
              y2={edge.y2}
              stroke="rgba(212, 168, 75, 0.3)"
              strokeWidth={1}
              strokeLinecap="round"
            />
          ))}
          {/* Cluster dots */}
          {cluster.dots.map((dot, di) => (
            <g key={`cd-${ci}-${di}`}>
              {/* Glow halo */}
              <circle
                className="cluster-dot"
                cx={dot.x}
                cy={dot.y}
                r={6}
                fill="rgba(202, 111, 78, 0.15)"
              />
              {/* Core dot */}
              <circle
                className="cluster-dot"
                cx={dot.x}
                cy={dot.y}
                r={2.5}
                fill="rgba(212, 168, 75, 0.8)"
              />
            </g>
          ))}
        </g>
      ))}
    </svg>
  );
}
