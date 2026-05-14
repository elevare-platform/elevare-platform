import { ShieldCheck, Zap, MapPin, Headphones } from 'lucide-react'
import { motion } from 'framer-motion'
import { useIntersectionObserver } from '@/hooks/useIntersectionObserver'

// ─── Feature cards data (Requirements 6.3) ───────────────────────────────────

const FEATURES = [
  {
    icon: ShieldCheck,
    title: 'Vetted Talent Pool',
    description: 'Every candidate is pre-screened. You only meet professionals worth your time.',
  },
  {
    icon: Zap,
    title: 'Speed Without Compromise',
    description: "Our average time-to-fill is 7 days. Quality doesn't have to mean slow.",
  },
  {
    icon: MapPin,
    title: 'Nigerian Market Expertise',
    description: 'Deep understanding of local talent markets, salary benchmarks, and hiring culture.',
  },
  {
    icon: Headphones,
    title: 'End-to-End Support',
    description: 'From job brief to signed offer, our team is with you at every step.',
  },
]

// ─── WhyChooseUs ─────────────────────────────────────────────────────────────

export default function WhyChooseUs() {
  // Requirements 6.4 — observe section to trigger staggered card animations
  const [sectionRef, isVisible] = useIntersectionObserver({ threshold: 0.15, triggerOnce: true })

  return (
    <section
      ref={sectionRef}
      aria-label="Why choose Elevare"
      style={{ background: '#F8F9FA', padding: '5rem 1rem' }}
    >
      <div
        style={{
          maxWidth: '72rem',
          margin: '0 auto',
          display: 'flex',
          flexDirection: 'row',
          alignItems: 'center',
          gap: '6rem',
          flexWrap: 'wrap',
        }}
      >

        {/* ── Left: heading + 2×2 card grid ── */}
        <div style={{ flex: '1 1 480px', minWidth: 0 }}>
          {/* Eyebrow */}
          <p
            style={{
              margin: '0 0 0.5rem',
              fontSize: '0.8125rem',
              fontWeight: 600,
              color: '#E87722',
              letterSpacing: '0.08em',
              textTransform: 'uppercase',
            }}
          >
            Why Elevare
          </p>

          {/* Heading — Requirements 6.1 */}
          <h2
            style={{
              margin: '0 0 2.5rem',
              fontSize: 'clamp(1.625rem, 3vw, 2.125rem)',
              fontWeight: 800,
              color: '#1e293b',
              lineHeight: 1.2,
            }}
          >
            Why Leading Companies Choose Elevare
          </h2>

          {/* 2×2 grid — Requirements 6.2 */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(2, 1fr)',
              gap: '1rem',
            }}
          >
            {FEATURES.map((feature, index) => {
              const Icon = feature.icon

              return (
                // Requirements 6.4 — fade-up entrance, staggered 100ms between cards
                <motion.article
                  key={feature.title}
                  initial={{ opacity: 0, y: 24 }}
                  animate={isVisible ? { opacity: 1, y: 0 } : {}}
                  transition={{ duration: 0.5, delay: index * 0.1 }}
                  style={{
                    background: '#ffffff',
                    borderRadius: '0.75rem',
                    border: '1px solid #e2e8f0',
                    boxShadow: '0 1px 8px rgba(0,0,0,0.05)',
                    padding: '1.5rem',
                  }}
                >
                  {/* Icon */}
                  <div
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      width: 44,
                      height: 44,
                      borderRadius: '0.625rem',
                      background: '#e8f0fb',
                      marginBottom: '1rem',
                    }}
                    aria-hidden="true"
                  >
                    <Icon size={22} color="#1A4D8F" strokeWidth={1.75} />
                  </div>

                  {/* Title */}
                  <h3
                    style={{
                      margin: '0 0 0.375rem',
                      fontSize: '0.9375rem',
                      fontWeight: 700,
                      color: '#1e293b',
                    }}
                  >
                    {feature.title}
                  </h3>

                  {/* Description */}
                  <p
                    style={{
                      margin: 0,
                      fontSize: '0.875rem',
                      color: '#64748b',
                      lineHeight: 1.6,
                    }}
                  >
                    {feature.description}
                  </p>
                </motion.article>
              )
            })}
          </div>
        </div>

        {/* ── Right: image — stretches to match left column height ── */}
        <div
          style={{
            flex: '1 1 400px',
            minWidth: 0,
            alignSelf: 'stretch',
            borderRadius: '1.25rem',
            overflow: 'hidden',
            boxShadow: '0 20px 60px rgba(26,77,143,0.12)',
          }}
        >
          <img
            src="https://images.unsplash.com/photo-1522071820081-009f0129c71c?w=1200&h=900&fit=crop&crop=center"
            alt="A diverse group of professionals collaborating in a modern office"
            style={{
              width: '100%',
              height: '100%',
              objectFit: 'cover',
              display: 'block',
            }}
          />
        </div>

      </div>
    </section>
  )
}
