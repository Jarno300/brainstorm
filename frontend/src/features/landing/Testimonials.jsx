import { useRef } from 'react';
import { useGSAP } from '@gsap/react';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';

gsap.registerPlugin(ScrollTrigger);

const TESTIMONIALS = [
  {
    quote: 'Brainstorm completely changed how I prepare for research papers. The knowledge maps help me see the entire field at a glance and find gaps I would have missed.',
    name: 'Sarah Chen',
    role: 'PhD Candidate, Stanford',
    initials: 'SC',
  },
  {
    quote: 'I use Brainstorm to map out product strategies. It takes complex competitive landscapes and turns them into something my whole team can understand in minutes.',
    name: 'Marcus Rivera',
    role: 'Product Lead, Stripe',
    initials: 'MR',
  },
  {
    quote: 'As a teacher, I create knowledge maps for every unit. My students use them to study, and the flashcard feature is a game-changer for exam prep.',
    name: 'Dr. Aisha Patel',
    role: 'High School Science Teacher',
    initials: 'AP',
  },
];

export default function Testimonials() {
  const cardsRef = useRef([]);

  useGSAP(() => {
    cardsRef.current.forEach((card, i) => {
      if (!card) return;
      gsap.fromTo(
        card,
        {
          opacity: 0,
          x: i % 2 === 0 ? -60 : 60,
        },
        {
          opacity: 1,
          x: 0,
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
    <section className="landing-section testimonials-section">
      <div className="landing-section-label">Testimonials</div>
      <h2 className="landing-section-title">
        Loved by thinkers,
        <br />
        researchers &amp; creators
      </h2>
      <p className="landing-section-sub">
        See how people are using Brainstorm to organize their thinking and
        accelerate their work.
      </p>

      <div className="testimonials-grid">
        {TESTIMONIALS.map((t, i) => (
          <div
            key={t.name}
            ref={(el) => { cardsRef.current[i] = el; }}
            className="testimonial-card"
          >
            <p className="testimonial-quote">&ldquo;{t.quote}&rdquo;</p>
            <div className="testimonial-author">
              <div className="testimonial-avatar">{t.initials}</div>
              <div>
                <div className="testimonial-name">{t.name}</div>
                <div className="testimonial-role">{t.role}</div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
