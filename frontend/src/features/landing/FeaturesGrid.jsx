import { useRef } from 'react';
import { useGSAP } from '@gsap/react';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';

gsap.registerPlugin(ScrollTrigger);

const FEATURES = [
  {
    id: 'maps',
    icon: '🗺️',
    title: 'Knowledge Maps',
    desc: 'Interactive visual maps that organize topics, subtopics, and their relationships into an intuitive spatial layout.',
  },
  {
    id: 'research',
    icon: '📚',
    title: 'Wikipedia Research',
    desc: 'Auto-researches any topic using Wikipedia. Every node comes packed with summaries, key facts, and structured content.',
  },
  {
    id: 'connections',
    icon: '🔗',
    title: 'Connection Exploration',
    desc: 'AI analyzes relationships between any two topics, revealing hidden links and synthesizing new insights.',
  },
  {
    id: 'flashcards',
    icon: '🃏',
    title: 'Flashcard Generation',
    desc: 'Turn any topic into study-ready flashcards. AI generates Q&A pairs from your knowledge map content.',
  },
  {
    id: 'collab',
    icon: '👥',
    title: 'Share & Collaborate',
    desc: 'Share your maps via link. Anyone can view your knowledge structures — no account required.',
  },
  {
    id: 'export',
    icon: '📤',
    title: 'Export & Integrate',
    desc: 'Export maps as Markdown, JSON, or images. Bring your knowledge anywhere you work.',
  },
];

export default function FeaturesGrid() {
  const cardsRef = useRef([]);

  useGSAP(() => {
    cardsRef.current.forEach((card, i) => {
      if (!card) return;
      gsap.fromTo(
        card,
        { opacity: 0, y: 40, scale: 0.95 },
        {
          opacity: 1,
          y: 0,
          scale: 1,
          duration: 0.7,
          ease: 'power3.out',
          scrollTrigger: {
            trigger: card,
            start: 'top 88%',
            toggleActions: 'play none none reverse',
          },
          delay: i * 0.08,
        }
      );

      // Hover lift effect
      card.addEventListener('mouseenter', () => {
        gsap.to(card, {
          y: -6,
          boxShadow: '0 8px 32px rgba(202, 111, 78, 0.12)',
          duration: 0.3,
          ease: 'power2.out',
        });
      });
      card.addEventListener('mouseleave', () => {
        gsap.to(card, {
          y: 0,
          boxShadow: '0 0 0 rgba(202, 111, 78, 0)',
          duration: 0.3,
          ease: 'power2.out',
        });
      });
    });
  }, []);

  return (
    <section className="landing-section features-section">
      <div className="landing-section-label">Features</div>
      <h2 className="landing-section-title">
        Everything you need
        <br />
        to think deeper
      </h2>
      <p className="landing-section-sub">
        Brainstorm combines research, visualization, and AI to give you a
        complete knowledge workspace.
      </p>

      <div className="features-grid">
        {FEATURES.map((feat, i) => (
          <div
            key={feat.id}
            ref={(el) => { cardsRef.current[i] = el; }}
            className="feature-card"
          >
            <div className={`feature-icon ${feat.id}`}>{feat.icon}</div>
            <h3 className="feature-title">{feat.title}</h3>
            <p className="feature-desc">{feat.desc}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
