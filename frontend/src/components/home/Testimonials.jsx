import { useState, useEffect } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { ChevronLeft, ChevronRight } from 'lucide-react'

// ─── Testimonials data (Requirements 8.3) ────────────────────────────────────

const TESTIMONIALS = [
  {
    id: 1,
    quote:
      'Elevare filled our senior engineering role in 5 days. The quality of candidates was exceptional.',
    name: 'Tunde Bakare',
    title: 'CTO',
    company: 'FinEdge Lagos',
    imageUrl: 'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=80&h=80&fit=crop&crop=face',
  },
  {
    id: 2,
    quote:
      "We've hired 12 people through Elevare this year. It's now our default recruitment partner.",
    name: 'Amaka Eze',
    title: 'Head of People',
    company: 'Traction Apps',
    imageUrl: 'https://images.unsplash.com/photo-1531746020798-e6953c6e8e04?w=80&h=80&fit=crop&crop=face',
  },
  {
    id: 3,
    quote:
      'The team understood exactly what we needed. No wasted interviews, just great hires.',
    name: 'Seun Adebayo',
    title: 'MD',
    company: 'Sterling Capital',
    imageUrl: 'https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=80&h=80&fit=crop&crop=face',
  },
]

// ─── Testimonials ─────────────────────────────────────────────────────────────

export default function Testimonials() {
  // Requirements 8.5 — activeIndex (0–2) and isPaused state
  const [activeIndex, setActiveIndex] = useState(0)
  const [isPaused, setIsPaused] = useState(false)

  // Requirements 8.5 — auto-advance every 6s; pause when hovered or on unmount
  useEffect(() => {
    if (isPaused) return

    const timer = setInterval(() => {
      setActiveIndex((prev) => (prev + 1) % TESTIMONIALS.length)
    }, 6000)

    return () => clearInterval(timer)
  }, [isPaused])

  // Manual navigation helpers — Requirements 8.4
  function handlePrev() {
    setActiveIndex((prev) => (prev - 1 + TESTIMONIALS.length) % TESTIMONIALS.length)
  }

  function handleNext() {
    setActiveIndex((prev) => (prev + 1) % TESTIMONIALS.length)
  }

  const testimonial = TESTIMONIALS[activeIndex]

  return (
    // Requirements 8.1 — #F8F9FA background
    // Requirements 8.5 — pause auto-advance on hover
    <section
      aria-label="Client testimonials"
      onMouseEnter={() => setIsPaused(true)}
      onMouseLeave={() => setIsPaused(false)}
      style={{ background: '#F8F9FA', padding: '5rem 1rem' }}
    >
      <div style={{ maxWidth: '48rem', margin: '0 auto' }}>
        {/* Heading — Requirements 8.1 */}
        <h2
          style={{
            textAlign: 'center',
            fontSize: '2rem',
            fontWeight: 800,
            color: '#1e293b',
            marginBottom: '3rem',
            lineHeight: 1.2,
          }}
        >
          What Our Clients Say
        </h2>

        {/* Testimonial card with crossfade — Requirements 8.6 */}
        <div style={{ position: 'relative' }}>
          <AnimatePresence mode="wait">
            <motion.div
              key={activeIndex}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.4 }}
              style={{
                background: '#ffffff',
                borderRadius: '1rem',
                border: '1px solid #e2e8f0',
                boxShadow: '0 2px 16px rgba(0,0,0,0.06)',
                padding: '2.5rem',
                textAlign: 'center',
              }}
            >
              {/* Decorative Amber quote mark — Requirements 8.2 */}
              <p
                aria-hidden="true"
                style={{
                  margin: '0 0 1rem',
                  fontSize: '5rem',
                  lineHeight: 0.8,
                  color: '#E87722',
                  fontFamily: 'Georgia, serif',
                  fontWeight: 700,
                }}
              >
                &ldquo;
              </p>

              {/* Italic quote text at 18px — Requirements 8.2 */}
              <blockquote
                style={{
                  margin: '0 0 2rem',
                  fontSize: '1.125rem',
                  fontStyle: 'italic',
                  color: '#334155',
                  lineHeight: 1.7,
                }}
              >
                {testimonial.quote}
              </blockquote>

              {/* Circular headshot — Requirements 8.2 */}
              <img
                src={testimonial.imageUrl}
                alt={`Portrait of ${testimonial.name}`}
                width={64}
                height={64}
                style={{
                  borderRadius: '50%',
                  objectFit: 'cover',
                  margin: '0 auto 0.75rem',
                  display: 'block',
                  border: '3px solid #e8f0fb',
                }}
              />

              {/* Bold name — Requirements 8.2 */}
              <p
                style={{
                  margin: '0 0 0.25rem',
                  fontWeight: 700,
                  fontSize: '1rem',
                  color: '#1e293b',
                }}
              >
                {testimonial.name}
              </p>

              {/* Secondary company/title — Requirements 8.2 */}
              <p
                style={{
                  margin: 0,
                  fontSize: '0.875rem',
                  color: '#64748b',
                }}
              >
                {testimonial.title}, {testimonial.company}
              </p>
            </motion.div>
          </AnimatePresence>

          {/* Left arrow — Requirements 8.4 */}
          <button
            onClick={handlePrev}
            aria-label="Previous testimonial"
            style={{
              position: 'absolute',
              top: '50%',
              left: '-3rem',
              transform: 'translateY(-50%)',
              background: '#ffffff',
              border: '1px solid #e2e8f0',
              borderRadius: '50%',
              width: 40,
              height: 40,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              cursor: 'pointer',
              boxShadow: '0 1px 4px rgba(0,0,0,0.08)',
              transition: 'box-shadow 0.2s',
            }}
            onMouseEnter={(e) => (e.currentTarget.style.boxShadow = '0 2px 8px rgba(0,0,0,0.15)')}
            onMouseLeave={(e) => (e.currentTarget.style.boxShadow = '0 1px 4px rgba(0,0,0,0.08)')}
          >
            <ChevronLeft size={18} color="#1A4D8F" />
          </button>

          {/* Right arrow — Requirements 8.4 */}
          <button
            onClick={handleNext}
            aria-label="Next testimonial"
            style={{
              position: 'absolute',
              top: '50%',
              right: '-3rem',
              transform: 'translateY(-50%)',
              background: '#ffffff',
              border: '1px solid #e2e8f0',
              borderRadius: '50%',
              width: 40,
              height: 40,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              cursor: 'pointer',
              boxShadow: '0 1px 4px rgba(0,0,0,0.08)',
              transition: 'box-shadow 0.2s',
            }}
            onMouseEnter={(e) => (e.currentTarget.style.boxShadow = '0 2px 8px rgba(0,0,0,0.15)')}
            onMouseLeave={(e) => (e.currentTarget.style.boxShadow = '0 1px 4px rgba(0,0,0,0.08)')}
          >
            <ChevronRight size={18} color="#1A4D8F" />
          </button>
        </div>

        {/* Dot indicators */}
        <div
          role="tablist"
          aria-label="Testimonial navigation"
          style={{
            display: 'flex',
            justifyContent: 'center',
            gap: '0.5rem',
            marginTop: '1.75rem',
          }}
        >
          {TESTIMONIALS.map((t, i) => (
            <button
              key={t.id}
              role="tab"
              aria-selected={i === activeIndex}
              aria-label={`Go to testimonial ${i + 1}`}
              onClick={() => setActiveIndex(i)}
              style={{
                width: i === activeIndex ? 24 : 8,
                height: 8,
                borderRadius: 4,
                border: 'none',
                background: i === activeIndex ? '#E87722' : '#cbd5e1',
                cursor: 'pointer',
                padding: 0,
                transition: 'width 0.3s, background 0.3s',
              }}
            />
          ))}
        </div>
      </div>
    </section>
  )
}
