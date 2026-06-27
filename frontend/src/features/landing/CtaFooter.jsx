import { useRef } from 'react';
import { useGSAP } from '@gsap/react';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';

gsap.registerPlugin(ScrollTrigger);

export default function CtaFooter({ onGetStarted, onSignIn }) {
  const sectionRef = useRef(null);
  const contentRef = useRef(null);

  useGSAP(() => {
    gsap.fromTo(
      contentRef.current,
      { opacity: 0, y: 40 },
      {
        opacity: 1,
        y: 0,
        duration: 0.9,
        ease: 'power3.out',
        scrollTrigger: {
          trigger: sectionRef.current,
          start: 'top 75%',
          toggleActions: 'play none none reverse',
        },
      }
    );
  }, []);

  return (
    <section ref={sectionRef} className="cta-section">
      <div ref={contentRef}>
        <h2 className="cta-title">
          Start mapping
          <br />
          your knowledge
        </h2>
        <p className="cta-sub">
          Free to start. No credit card required.
          <br />
          Build your first knowledge map in under a minute.
        </p>
        <button className="cta-btn" onClick={onGetStarted}>
          Get Started Free
        </button>

        <div className="cta-login">
          Already have an account?{' '}
          <a href="#signin" onClick={(e) => { e.preventDefault(); onSignIn(); }}>
            Sign in
          </a>
        </div>
      </div>

      <footer className="landing-footer">
        <p className="landing-footer-text">
          &copy; {new Date().getFullYear()} Brainstorm. All rights reserved.
        </p>
      </footer>
    </section>
  );
}
