import { useRef } from 'react';
import { useGSAP } from '@gsap/react';
import gsap from 'gsap';
import NetworkGraph from './NetworkGraph';

export default function HeroSection({ onGetStarted, onHowItWorks }) {
  const containerRef = useRef(null);
  const titleRef = useRef(null);
  const subtitleRef = useRef(null);
  const eyebrowRef = useRef(null);
  const actionsRef = useRef(null);

  useGSAP(() => {
    const tl = gsap.timeline({ defaults: { ease: 'power3.out' } });

    tl.fromTo(
      eyebrowRef.current,
      { opacity: 0, y: 20 },
      { opacity: 1, y: 0, duration: 0.7 }
    )
      .fromTo(
        titleRef.current,
        { opacity: 0, y: 40 },
        { opacity: 1, y: 0, duration: 0.9 },
        '-=0.3'
      )
      .fromTo(
        subtitleRef.current,
        { opacity: 0, y: 24 },
        { opacity: 1, y: 0, duration: 0.8 },
        '-=0.4'
      )
      .fromTo(
        actionsRef.current,
        { opacity: 0, y: 20 },
        { opacity: 1, y: 0, duration: 0.7 },
        '-=0.3'
      );
  }, []);

  return (
    <section ref={containerRef} className="hero-section">
      <div className="hero-bg">
        <NetworkGraph />
      </div>

      <div className="hero-content">
        <div ref={eyebrowRef} className="hero-eyebrow">
          AI-Powered Knowledge Mapping
        </div>

        <h1 ref={titleRef} className="hero-title">
          Visualize ideas.
          <br />
          Discover connections.
        </h1>

        <p ref={subtitleRef} className="hero-subtitle">
          Turn any topic into an interactive knowledge map.
          Brainstorm uses AI to research, structure, and connect ideas
          — so you can think deeper and create faster.
        </p>

        <div ref={actionsRef} className="hero-actions">
          <button className="hero-btn-primary" onClick={onGetStarted}>
            Get Started Free
          </button>
          <button className="hero-btn-secondary" onClick={onHowItWorks}>
            See how it works ↓
          </button>
        </div>
      </div>
    </section>
  );
}
