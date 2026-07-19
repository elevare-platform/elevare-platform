// HowItWorks — three-step hiring process section (Requirements 7.1–7.5)

// ─── Steps data (Requirements 7.3) ───────────────────────────────────────────

const STEPS = [
  {
    number: '01',
    title: 'Tell Us What You Need',
    description:
      'Share your role requirements, team culture, and timeline. Takes less than 10 minutes.',
  },
  {
    number: '02',
    title: 'AI Talent Pipeline Matching',
    description:
      'Our smart recruitment pipelines instantly curate and map the best-fit professionals matching your technical criteria.',
  },
  {
    number: '03',
    title: 'Connect and Hire Fast',
    description:
      'Interview shortlisted candidates and make your hire. We handle the paperwork.',
  },
]

// ─── HowItWorks ───────────────────────────────────────────────────────────────

export default function HowItWorks() {
  return (
    // Requirements 7.1 — white background
    <section
      aria-label="How it works"
      style={{ background: '#ffffff', padding: '5rem 1rem' }}
    >
      <div style={{ maxWidth: '64rem', margin: '0 auto' }}>
        {/* Heading — Requirements 7.1 */}
        <h2
          style={{
            textAlign: 'center',
            fontSize: '2rem',
            fontWeight: 800,
            color: '#1e293b',
            marginBottom: '3.5rem',
            lineHeight: 1.2,
            fontFamily: "'Inter', system-ui, sans-serif",
          }}
        >
          Hiring Has Never Been This Simple
        </h2>

        {/* Steps row — Requirements 7.2: flex-col on mobile, flex-row on md+ */}
        {/* Using a wrapper div with CSS class for responsive flex direction */}
        <div className="how-it-works-steps">
          {STEPS.map((step, index) => (
            <div key={step.number} style={{ display: 'contents' }}>
              {/* Step item */}
              <div className="how-it-works-step">
                {/* Large Amber step number — Requirements 7.2 */}
                <p
                  style={{
                    margin: '0 0 1rem',
                    fontSize: '3.5rem',
                    fontWeight: 800,
                    color: '#E87722',
                    lineHeight: 1,
                    letterSpacing: '-0.02em',
                  }}
                  aria-hidden="true"
                >
                  {step.number}
                </p>

                {/* Bold title */}
                <h3
                  style={{
                    margin: '0 0 0.75rem',
                    fontSize: '1.125rem',
                    fontWeight: 700,
                    color: '#1e293b',
                  }}
                >
                  {step.title}
                </h3>

                {/* Description */}
                <p
                  style={{
                    margin: 0,
                    fontSize: '0.9375rem',
                    color: '#64748b',
                    lineHeight: 1.6,
                  }}
                >
                  {step.description}
                </p>
              </div>

              {/* Connector line between steps — Requirements 7.4: visible on md+ only */}
              {index < STEPS.length - 1 && (
                <div
                  aria-hidden="true"
                  className="how-it-works-connector"
                />
              )}
            </div>
          ))}
        </div>

        {/* CTA button — Requirements 7.5: centred Amber filled */}
        <div style={{ textAlign: 'center', marginTop: '3.5rem' }}>
          <a
            href="/register"
            style={{
              display: 'inline-block',
              background: '#E87722',
              color: '#ffffff',
              fontWeight: 700,
              fontSize: '1rem',
              padding: '0.875rem 2rem',
              borderRadius: '0.5rem',
              textDecoration: 'none',
              transition: 'opacity 0.2s',
            }}
            onMouseEnter={(e) => (e.currentTarget.style.opacity = '0.9')}
            onMouseLeave={(e) => (e.currentTarget.style.opacity = '1')}
          >
            Get Started Today →
          </a>
        </div>
      </div>
    </section>
  )
}
