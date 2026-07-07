import { useState, useEffect } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import api from '@/lib/api'

export default function Testimonials() {
  const [testimonials, setTestimonials] = useState([])
  const [activeIndex, setActiveIndex] = useState(0)
  const [isPaused, setIsPaused] = useState(false)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function load() {
      try {
        const { data } = await api.get('/api/v1/testimonials')
        setTestimonials(data)
      } catch {
        // silent fail
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  useEffect(() => {
    if (isPaused || testimonials.length === 0) return
    const timer = setInterval(() => {
      setActiveIndex((prev) => (prev + 1) % testimonials.length)
    }, 6000)
    return () => clearInterval(timer)
  }, [isPaused, testimonials.length])

  function handlePrev() {
    setActiveIndex((prev) => (prev - 1 + testimonials.length) % testimonials.length)
  }

  function handleNext() {
    setActiveIndex((prev) => (prev + 1) % testimonials.length)
  }

  if (loading || testimonials.length === 0) return null

  const testimonial = testimonials[activeIndex]

  return (
    <section
      aria-label="Client testimonials"
      onMouseEnter={() => setIsPaused(true)}
      onMouseLeave={() => setIsPaused(false)}
      style={{ background: '#F8F9FA', padding: '5rem 1rem' }}
    >
      <div style={{ maxWidth: '48rem', margin: '0 auto' }}>
        <h2
          style={{
            textAlign: 'center',
            fontSize: '2rem',
            fontWeight: 800,
            color: '#1e293b',
            marginBottom: '3rem',
            lineHeight: 1.2,
            fontFamily: "'Lobster Two', cursive",
          }}
        >
          What Our Clients Say
        </h2>

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

              <blockquote
                style={{
                  margin: '0 0 2rem',
                  fontSize: '1.125rem',
                  fontStyle: 'italic',
                  color: '#334155',
                  lineHeight: 1.7,
                }}
              >
                {testimonial.testimony}
              </blockquote>

              {testimonial.image_url && (
                <img
                  src={testimonial.image_url}
                  alt={`Portrait of ${testimonial.full_name}`}
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
              )}

              <p
                style={{
                  margin: '0 0 0.25rem',
                  fontWeight: 700,
                  fontSize: '1rem',
                  color: '#1e293b',
                }}
              >
                {testimonial.full_name}
              </p>

              {(testimonial.position || testimonial.company) && (
                <p style={{ margin: 0, fontSize: '0.875rem', color: '#64748b' }}>
                  {[testimonial.position, testimonial.company].filter(Boolean).join(', ')}
                </p>
              )}
            </motion.div>
          </AnimatePresence>

          <button
            onClick={handlePrev}
            aria-label="Previous testimonial"
            className="absolute top-1/2 -translate-y-1/2 -left-3 md:-left-12 flex items-center justify-center w-10 h-10 rounded-full cursor-pointer"
            style={{ background: '#ffffff', border: '1px solid #e2e8f0', boxShadow: '0 1px 4px rgba(0,0,0,0.08)', transition: 'box-shadow 0.2s' }}
            onMouseEnter={(e) => (e.currentTarget.style.boxShadow = '0 2px 8px rgba(0,0,0,0.15)')}
            onMouseLeave={(e) => (e.currentTarget.style.boxShadow = '0 1px 4px rgba(0,0,0,0.08)')}
          >
            <ChevronLeft size={18} color="#1A4D8F" />
          </button>

          <button
            onClick={handleNext}
            aria-label="Next testimonial"
            className="absolute top-1/2 -translate-y-1/2 -right-3 md:-right-12 flex items-center justify-center w-10 h-10 rounded-full cursor-pointer"
            style={{ background: '#ffffff', border: '1px solid #e2e8f0', boxShadow: '0 1px 4px rgba(0,0,0,0.08)', transition: 'box-shadow 0.2s' }}
            onMouseEnter={(e) => (e.currentTarget.style.boxShadow = '0 2px 8px rgba(0,0,0,0.15)')}
            onMouseLeave={(e) => (e.currentTarget.style.boxShadow = '0 1px 4px rgba(0,0,0,0.08)')}
          >
            <ChevronRight size={18} color="#1A4D8F" />
          </button>
        </div>

        <div
          role="tablist"
          aria-label="Testimonial navigation"
          style={{ display: 'flex', justifyContent: 'center', gap: '0.5rem', marginTop: '1.75rem' }}
        >
          {testimonials.map((t, i) => (
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
