import { useRef, useMemo } from 'react';
import { useGSAP } from '@gsap/react';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';

gsap.registerPlugin(ScrollTrigger);

const NODES = [
  { id: 0, label: 'AI', x: 400, y: 100, r: 28, color: '#CA6F4E' },
  { id: 1, label: 'Neural Networks', x: 200, y: 220, r: 22, color: '#D4A84B' },
  { id: 2, label: 'Deep Learning', x: 600, y: 220, r: 22, color: '#D4A84B' },
  { id: 3, label: 'Transformers', x: 100, y: 360, r: 18, color: '#7B9E74' },
  { id: 4, label: 'GPT Models', x: 300, y: 380, r: 18, color: '#7B9E74' },
  { id: 5, label: 'Computer Vision', x: 500, y: 360, r: 18, color: '#7B9E74' },
  { id: 6, label: 'Reinforcement Learning', x: 700, y: 380, r: 18, color: '#7B9E74' },
];

const EDGES = [
  { from: 0, to: 1 },
  { from: 0, to: 2 },
  { from: 1, to: 3 },
  { from: 1, to: 4 },
  { from: 2, to: 5 },
  { from: 2, to: 6 },
  { from: 3, to: 4 },
  { from: 5, to: 6 },
];

export default function DemoPreview() {
  const svgRef = useRef(null);
  const nodeRefs = useRef([]);
  const edgeRefs = useRef([]);
  const labelRefs = useRef([]);

  useGSAP(() => {
    if (!svgRef.current) return;

    const tl = gsap.timeline({
      repeat: -1,
      repeatDelay: 1.5,
    });

    // Initial state: all hidden
    gsap.set(nodeRefs.current, { scale: 0, opacity: 0, transformOrigin: '50% 50%' });
    gsap.set(edgeRefs.current, { opacity: 0 });
    gsap.set(labelRefs.current, { opacity: 0 });

    // Phase 1: Central node appears
    tl.to(nodeRefs.current[0], {
      scale: 1,
      opacity: 1,
      duration: 0.6,
      ease: 'back.out(1.7)',
    })
      .to(labelRefs.current[0], { opacity: 1, duration: 0.3 }, '-=0.2');

    // Phase 2: Level 2 nodes + edges
    [1, 2].forEach((i) => {
      const edgeIdx = i - 1;
      tl.to(nodeRefs.current[i], {
        scale: 1,
        opacity: 1,
        duration: 0.5,
        ease: 'back.out(1.7)',
      }, '-=0.15')
        .to(edgeRefs.current[edgeIdx], {
          opacity: 0.5,
          duration: 0.4,
        }, '-=0.3')
        .to(labelRefs.current[i], { opacity: 1, duration: 0.3 }, '-=0.2');
    });

    // Phase 3: Level 3 nodes + edges (staggered)
    for (let i = 3; i <= 6; i++) {
      const edgeIdx = i - 1; // edges 2-7
      tl.to(nodeRefs.current[i], {
        scale: 1,
        opacity: 1,
        duration: 0.4,
        ease: 'back.out(1.5)',
      }, '-=0.1')
        .to(edgeRefs.current[edgeIdx], {
          opacity: 0.4,
          duration: 0.3,
        }, '-=0.25')
        .to(labelRefs.current[i], { opacity: 1, duration: 0.25 }, '-=0.15');
    }

    // Cross edges (7, 8) — connect siblings
    tl.to(edgeRefs.current[7], { opacity: 0.3, duration: 0.4 }, '-=0.1');
    tl.to(edgeRefs.current[8], { opacity: 0.3, duration: 0.4 }, '-=0.1');

    // Hold
    tl.to({}, { duration: 1.5 });

    // Collapse
    tl.to([...nodeRefs.current, ...labelRefs.current, ...edgeRefs.current], {
      opacity: 0,
      scale: 0,
      duration: 0.5,
      ease: 'power2.in',
      stagger: 0.03,
    });
  }, []);

  // Draw edges as paths with slight curves
  const edgePaths = useMemo(() => {
    return EDGES.map(({ from, to }) => {
      const a = NODES[from];
      const b = NODES[to];
      const mx = (a.x + b.x) / 2;
      const my = (a.y + b.y) / 2 - 15;
      return `M ${a.x} ${a.y} Q ${mx} ${my} ${b.x} ${b.y}`;
    });
  }, []);

  return (
    <section className="landing-section demo-section">
      <div className="landing-section-label">See It In Action</div>
      <h2 className="landing-section-title">
        Watch your knowledge
        <br />
        come to life
      </h2>
      <p className="landing-section-sub">
        Every topic expands into a rich, connected network. Here&apos;s what
        mapping &quot;Artificial Intelligence&quot; looks like.
      </p>

      <div className="demo-container">
        <svg
          ref={svgRef}
          viewBox="0 0 800 500"
          className="demo-canvas-svg"
          preserveAspectRatio="xMidYMid meet"
        >
          {/* Edges */}
          {edgePaths.map((d, i) => (
            <path
              key={`edge-${i}`}
              ref={(el) => { edgeRefs.current[i] = el; }}
              d={d}
              fill="none"
              stroke="rgba(202, 111, 78, 0.4)"
              strokeWidth={1.5}
              strokeDasharray="6 4"
            />
          ))}

          {/* Node labels */}
          {NODES.map((node, i) => (
            <text
              key={`label-${i}`}
              ref={(el) => { labelRefs.current[i] = el; }}
              x={node.x}
              y={node.y + node.r + 22}
              textAnchor="middle"
              fill="rgba(208, 191, 176, 0.6)"
              fontSize="12"
              fontFamily="Inter, sans-serif"
              fontWeight="500"
            >
              {node.label}
            </text>
          ))}

          {/* Nodes */}
          {NODES.map((node, i) => (
            <g key={`node-${i}`} ref={(el) => { nodeRefs.current[i] = el; }}>
              <circle
                cx={node.x}
                cy={node.y}
                r={node.r + 6}
                fill="none"
                stroke={node.color}
                strokeWidth={1}
                opacity={0.3}
              />
              <circle
                cx={node.x}
                cy={node.y}
                r={node.r}
                fill={node.color}
                opacity={0.85}
              />
              <circle
                cx={node.x}
                cy={node.y}
                r={node.r * 0.4}
                fill="rgba(253, 250, 247, 0.6)"
              />
            </g>
          ))}
        </svg>
      </div>
    </section>
  );
}
