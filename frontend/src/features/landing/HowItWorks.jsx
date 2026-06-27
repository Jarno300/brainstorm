import { useRef } from 'react';
import { useGSAP } from '@gsap/react';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';

gsap.registerPlugin(ScrollTrigger);

const STEPS = [
  {
    step: '01',
    title: 'Enter a topic',
    desc: 'Start with any question, concept, or subject you want to explore. Brainstorm begins researching instantly.',
    icon: '🔍',
  },
  {
    step: '02',
    title: 'AI builds your map',
    desc: 'Wikipedia-powered research generates a structured knowledge map with key concepts, subtopics, and connections.',
    icon: '🧠',
  },
  {
    step: '03',
    title: 'Explore & discover',
    desc: 'Click any node to dive deeper. Discover unexpected connections, generate flashcards, and export your insights.',
    icon: '✨',
  },
];

export default function HowItWorks({ sectionRef }) {
  const cardsRef = useRef([]);

  useGSAP(() => {
    cardsRef.current.forEach((card, i) => {
      if (!card) return;
      gsap.fromTo(
        card,
        { opacity: 0, y: 60 },
        {
          opacity: 1,
          y: 0,
          duration: 0.8,
          ease: 'power3.out',
          scrollTrigger: {
            trigger: card,
            start: 'top 85%',
            toggleActions: 'play none none reverse',
          },
          delay: i * 0.15,
        }
      );
    });
  }, []);

  return (
    <section ref={sectionRef} className="landing-section how-section">
      <div className="landing-section-label">How It Works</div>
      <h2 className="landing-section-title">
        From idea to insight
        <br />
        in three steps
      </h2>
      <p className="landing-section-sub">
        No complex setup. No manual structuring. Just enter a topic and watch
        your knowledge map unfold.
      </p>

      <div className="how-grid">
        {STEPS.map((step, i) => (
          <div
            key={step.step}
            ref={(el) => { cardsRef.current[i] = el; }}
            className="how-card"
          >
            <div className="how-card-step">{step.step}</div>
            <h3 className="how-card-title">
              {step.icon} {step.title}
            </h3>
            <p className="how-card-desc">{step.desc}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
