import { CheckCircle2 } from 'lucide-react'
import { Button } from '@/components/ui/button'

// ─── Pain-point / solution data (Requirements 4.1) ────────────────────────────
// Min 3 pairs required

const PAIN_POINTS = [
  {
    id: 'retention',
    problem: 'Struggling to retain top talent?',
    solution:
      'Our retention-focused placement process reduces churn by matching culture, not just skills.',
  },
  {
    id: 'time-to-hire',
    problem: 'Spending weeks on a single hire?',
    solution:
      'Our pre-vetted talent pool cuts average time-to-hire to under 14 days — without sacrificing quality.',
  },
  {
    id: 'compliance',
    problem: 'Worried about HR compliance and payroll errors?',
    solution:
      'We handle payroll processing and labour-law compliance so your team can focus on growth.',
  },
  {
    id: 'scaling',
    problem: 'Need to scale your team fast but lack the bandwidth?',
    solution:
      'Our dedicated account managers act as an extension of your HR team, ready to mobilise at short notice.',
  },
]

// ─── EmployerStrip ────────────────────────────────────────────────────────────

export default function EmployerStrip({ onBookConsultation }) {
  return (
    <section
      aria-label="For employers"
      className="relative overflow-hidden"
      style={{
        padding: '5rem 1rem',
      }}
    >
      {/* Background image */}
      <div
        className="absolute inset-0 bg-cover bg-center bg-no-repeat scale-105"
        style={{ backgroundImage: "url('/hero-images/img15.jpg')" }}
        aria-hidden="true"
      />
      {/* Dark gradient overlay */}
      <div
        className="absolute inset-0"
        style={{ background: 'linear-gradient(135deg, rgba(14,31,58,0.94) 0%, rgba(26,77,143,0.92) 100%)' }}
        aria-hidden="true"
      />
      <div
        style={{
          maxWidth: '72rem',
          margin: '0 auto',
          // Requirements 4.4 — stack vertically on mobile, side-by-side on desktop
          display: 'grid',
          gridTemplateColumns: '1fr',
          gap: '3rem',
          position: 'relative',
          zIndex: 10,
        }}
        className="employer-strip-grid"
      >
        {/* ── Left column: heading + pain-point/solution pairs ── */}
        <div>
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
            For Employers
          </p>

          {/* Heading */}
          <h2
            style={{
              margin: '0 0 2.5rem',
              fontSize: 'clamp(1.625rem, 3vw, 2.125rem)',
              fontWeight: 800,
              color: '#ffffff',
              lineHeight: 1.2,
              fontFamily: "'Lobster Two', cursive",
            }}
          >
            We Solve Your Toughest
            <br />
            Hiring Challenges
          </h2>

          {/* Pain-point / solution pairs */}
          <ul
            style={{
              listStyle: 'none',
              margin: 0,
              padding: 0,
              display: 'flex',
              flexDirection: 'column',
              gap: '1.75rem',
            }}
          >
            {PAIN_POINTS.map((item) => (
              <li key={item.id} style={{ display: 'flex', gap: '1rem', alignItems: 'flex-start' }}>
                {/* Check icon */}
                <CheckCircle2
                  size={22}
                  color="#E87722"
                  strokeWidth={2}
                  style={{ flexShrink: 0, marginTop: 2 }}
                  aria-hidden="true"
                />
                <div>
                  <p
                    style={{
                      margin: '0 0 0.25rem',
                      fontWeight: 700,
                      fontSize: '1rem',
                      color: '#ffffff',
                      lineHeight: 1.4,
                    }}
                  >
                    {item.problem}
                  </p>
                  <p
                    style={{
                      margin: 0,
                      fontSize: '0.9375rem',
                      color: 'rgba(255,255,255,0.75)',
                      lineHeight: 1.6,
                    }}
                  >
                    {item.solution}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        </div>

        {/* ── Right column: CTA (Requirements 4.2) ── */}
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'flex-start',
            justifyContent: 'center',
            gap: '1.5rem',
          }}
          className="employer-strip-cta"
        >
          {/* Supporting stat */}
          <div
            style={{
              background: 'rgba(255,255,255,0.08)',
              border: '1px solid rgba(255,255,255,0.15)',
              borderRadius: '0.75rem',
              padding: '1.5rem 2rem',
              width: '100%',
            }}
          >
            <p
              style={{
                margin: '0 0 0.25rem',
                fontSize: 'clamp(2rem, 4vw, 2.75rem)',
                fontWeight: 800,
                color: '#E87722',
                lineHeight: 1,
              }}
            >
              94%
            </p>
            <p
              style={{
                margin: 0,
                fontSize: '0.9375rem',
                color: 'rgba(255,255,255,0.8)',
                lineHeight: 1.5,
              }}
            >
              of our placements are still in role after 12 months — well above the industry average.
            </p>
          </div>

          {/* Book a Consultation CTA — Requirements 4.2 */}
          <Button
            size="lg"
            onClick={onBookConsultation}
            style={{
              background: '#E87722',
              color: '#ffffff',
              border: 'none',
              fontWeight: 700,
              fontSize: '1rem',
              padding: '0.875rem 2rem',
              borderRadius: '0.5rem',
              cursor: 'pointer',
              transition: 'background 0.2s, transform 0.15s',
              minHeight: 44,
              width: '100%',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = '#c9661a'
              e.currentTarget.style.transform = 'translateY(-1px)'
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = '#E87722'
              e.currentTarget.style.transform = 'translateY(0)'
            }}
          >
            Book a Consultation
          </Button>

          <p
            style={{
              margin: 0,
              fontSize: '0.8125rem',
              color: 'rgba(255,255,255,0.55)',
              lineHeight: 1.5,
            }}
          >
            Free 30-minute strategy call. No commitment required.
          </p>
        </div>
      </div>
    </section>
  )
}
