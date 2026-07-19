import { Award, Users, Filter, MessageSquare, Settings, LifeBuoy } from 'lucide-react'
import { motion } from 'framer-motion'
import { useIntersectionObserver } from '@/hooks/useIntersectionObserver'

// ─── Feature cards data (Requirements 6.3) ───────────────────────────────────

const FEATURES = [
  {
    icon: Award,
    title: 'Professional Recruitment Process',
    description: 'A structured, expert-led process that ensures every hire meets your standards.',
  },
  {
    icon: Users,
    title: 'Access to Qualified Talent',
    description: 'Tap into a curated network of verified professionals ready for your roles.',
  },
  {
    icon: Filter,
    title: 'Efficient Candidate Screening',
    description: 'We handle the heavy lifting — only the best-fit candidates reach your desk.',
  },
  {
    icon: MessageSquare,
    title: 'Strong Client Communication',
    description: 'Transparent updates and clear communication at every stage of the process.',
  },
  {
    icon: Settings,
    title: 'Tailored Hiring Solutions',
    description: 'Recruitment strategies built around your unique business needs and culture.',
  },
  {
    icon: LifeBuoy,
    title: 'Reliable Workforce Support',
    description: 'Ongoing support to help you retain and grow your workforce long-term.',
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

// ─── WhyChooseUs ─────────────────────────────────────────────────────────────

export default function WhyChooseUs() {
  // Requirements 6.4 — observe section to trigger staggered card animations
  const [sectionRef, isVisible] = useIntersectionObserver({ threshold: 0.15, triggerOnce: true })

  return (
    <section
      ref={sectionRef}
      aria-label="Why choose Elevare"
      style={{ background: '#F8F9FA', padding: '5rem 1.5rem', overflow: 'hidden' }}
    >
      <div style={{ maxWidth: '80rem', margin: '0 auto' }}>

        {/* ── Centered heading block ── */}
        <div style={{ textAlign: 'center', marginBottom: '3rem' }}>
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

          <motion.h2
            custom={1}
            variants={headingVariants}
            initial="hidden"
            animate={isVisible ? 'visible' : 'hidden'}
            style={{
              margin: '0 auto',
              maxWidth: '38rem',
              fontSize: 'clamp(1.625rem, 3vw, 2.125rem)',
              fontWeight: 800,
              color: '#1e293b',
              lineHeight: 1.2,
              fontFamily: "'Inter', system-ui, sans-serif",
            }}
          >
            Why Leading Companies Choose Elevare
          </motion.h2>
        </div>

        {/* ── 3-col card grid, full width ── */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
          {FEATURES.map((feature, index) => {
            const Icon = feature.icon
            return (
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
                  padding: '1.75rem',
                  position: 'relative',
                  overflow: 'hidden',
                }}
              >
                <span className="why-card-accent" aria-hidden="true" />

                <div
                  className="why-icon-wrap"
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    width: 48,
                    height: 48,
                    borderRadius: '0.625rem',
                    background: '#e8f0fb',
                    marginBottom: '1rem',
                  }}
                  aria-hidden="true"
                >
                  <Icon size={24} className="why-icon" strokeWidth={1.75} style={{ color: '#1A4D8F' }} />
                </div>

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

                <p style={{ margin: 0, fontSize: '0.875rem', color: '#64748b', lineHeight: 1.6 }}>
                  {feature.description}
                </p>
              </motion.article>
            )
          })}
        </div>

      </div>
    </section>
  )
}
