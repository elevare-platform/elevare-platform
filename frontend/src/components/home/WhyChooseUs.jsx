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

// ─── Framer Motion variants ───────────────────────────────────────────────────

/** Eyebrow and heading — fade-up slightly ahead of cards */
const headingVariants = {
  hidden:  { opacity: 0, y: 20 },
  visible: (i = 0) => ({
    opacity: 1,
    y: 0,
    transition: { duration: 0.55, delay: i * 0.1, ease: [0.16, 1, 0.3, 1] },
  }),
}

/** Feature cards — spring entrance with subtle scale */
const cardVariants = {
  hidden:  { opacity: 0, y: 24, scale: 0.97 },
  visible: (i) => ({
    opacity: 1,
    y: 0,
    scale: 1,
    transition: { duration: 0.5, delay: 0.15 + i * 0.09, ease: [0.16, 1, 0.3, 1] },
  }),
}

/** Right image panel — slides in from the right */
const imageVariants = {
  hidden:  { opacity: 0, x: 40 },
  visible: {
    opacity: 1,
    x: 0,
    transition: { duration: 0.65, delay: 0.1, ease: [0.16, 1, 0.3, 1] },
  },
}

// ─── WhyChooseUs ─────────────────────────────────────────────────────────────

export default function WhyChooseUs() {
  // Requirements 6.4 — observe section to trigger staggered card animations
  const [sectionRef, isVisible] = useIntersectionObserver({ threshold: 0.15, triggerOnce: true })

  return (
    <section
      ref={sectionRef}
      aria-label="Why choose Elevare"
      style={{ background: '#F8F9FA', padding: '5rem 1rem', overflow: 'hidden' }}
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
          <motion.p
            custom={0}
            variants={headingVariants}
            initial="hidden"
            animate={isVisible ? 'visible' : 'hidden'}
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
          </motion.p>

          {/* Heading — Requirements 6.1 */}
          <motion.h2
            custom={1}
            variants={headingVariants}
            initial="hidden"
            animate={isVisible ? 'visible' : 'hidden'}
            style={{
              margin: '0 0 2.5rem',
              fontSize: 'clamp(1.625rem, 3vw, 2.125rem)',
              fontWeight: 800,
              color: '#1e293b',
              lineHeight: 1.2,
              fontFamily: "'Lobster Two', cursive",
            }}
          >
            Why Leading Companies Choose Elevare
          </motion.h2>

          {/* 2×2 grid — Requirements 6.2 — single column on small mobile, 2-col on sm+ */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {FEATURES.map((feature, index) => {
              const Icon = feature.icon

              return (
                // Requirements 6.4 — spring entrance, staggered
                <motion.article
                  key={feature.title}
                  custom={index}
                  variants={cardVariants}
                  initial="hidden"
                  animate={isVisible ? 'visible' : 'hidden'}
                  className="why-card group"
                  style={{
                    background: '#ffffff',
                    borderRadius: '0.875rem',
                    border: '1px solid #e2e8f0',
                    boxShadow: '0 2px 8px rgba(0,0,0,0.04), 0 1px 3px rgba(0,0,0,0.03)',
                    padding: '1.5rem',
                    position: 'relative',
                    overflow: 'hidden',
                  }}
                >
                  {/* Top-edge accent bar — same language as service cards */}
                  <span className="why-card-accent" aria-hidden="true" />

                  {/* Icon wrapper */}
                  <div
                    className="why-icon-wrap"
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
                    <Icon
                      size={22}
                      className="why-icon"
                      strokeWidth={1.75}
                      style={{ color: '#1A4D8F' }}
                    />
                  </div>

                  {/* Title */}
                  <h3
                    className="why-card-title"
                    style={{
                      margin: '0 0 0.375rem',
                      fontSize: '0.9375rem',
                      fontWeight: 700,
                      color: '#1e293b',
                      transition: 'color 0.25s ease',
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

        {/* ── Right: image panel — slides in from right ── */}
        <motion.div
          variants={imageVariants}
          initial="hidden"
          animate={isVisible ? 'visible' : 'hidden'}
          className="why-image-wrap"
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
            src="/hero-images/img7.jpg"
            alt="A diverse group of professionals collaborating in a modern office"
            className="why-image"
            style={{
              width: '100%',
              height: '100%',
              objectFit: 'cover',
              display: 'block',
            }}
          />
        </motion.div>

      </div>
    </section>
  )
}
