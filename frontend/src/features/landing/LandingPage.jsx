import { useRef, useState, useEffect, useCallback } from 'react';
import HeroSection from './HeroSection';
import HowItWorks from './HowItWorks';
import FeaturesGrid from './FeaturesGrid';
import DemoPreview from './DemoPreview';
import Testimonials from './Testimonials';
import CtaFooter from './CtaFooter';
import './landing.css';

export default function LandingPage({ onGetStarted, onSignIn }) {
  const navRef = useRef(null);
  const howRef = useRef(null);
  const [scrolled, setScrolled] = useState(false);

  // Override global overflow:hidden so landing page can scroll
  useEffect(() => {
    const html = document.documentElement;
    const body = document.body;
    const root = document.getElementById('root');
    const prevHtml = html.style.overflow;
    const prevBody = body.style.overflow;
    const prevRoot = root?.style.overflow;

    html.style.overflow = 'auto';
    html.style.height = 'auto';
    body.style.overflow = 'auto';
    body.style.height = 'auto';
    if (root) {
      root.style.overflow = 'auto';
      root.style.height = 'auto';
    }

    return () => {
      html.style.overflow = prevHtml;
      html.style.height = '';
      body.style.overflow = prevBody;
      body.style.height = '';
      if (root) {
        root.style.overflow = prevRoot;
        root.style.height = '';
      }
    };
  }, []);

  // Nav scroll effect
  useEffect(() => {
    const onScroll = () => {
      setScrolled(window.scrollY > 20);
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  const scrollToHow = useCallback(() => {
    howRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  return (
    <div className="landing-page">
      {/* ── Sticky Nav ────────────────────────────────── */}
      <nav ref={navRef} className={`landing-nav${scrolled ? ' scrolled' : ''}`}>
        <a href="/" className="landing-nav-brand">
          <div className="landing-nav-logo">B</div>
          <span className="landing-nav-title">Brainstorm</span>
        </a>
        <div className="landing-nav-actions">
          <button className="landing-nav-btn landing-nav-btn-outline" onClick={onSignIn}>
            Sign In
          </button>
          <button className="landing-nav-btn landing-nav-btn-primary" onClick={onGetStarted}>
            Get Started
          </button>
        </div>
      </nav>

      {/* ── Sections ──────────────────────────────────── */}
      <HeroSection onGetStarted={onGetStarted} onHowItWorks={scrollToHow} />
      <HowItWorks sectionRef={howRef} />
      <FeaturesGrid />
      <DemoPreview />
      <Testimonials />
      <CtaFooter onGetStarted={onGetStarted} onSignIn={onSignIn} />
    </div>
  );
}
