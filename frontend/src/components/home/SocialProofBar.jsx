// ─── Company names (Requirements 4.4) ────────────────────────────────────────
// Rendered twice inside the scrolling strip to create a seamless infinite loop.
// The CSS `scroll-x` animation translates by -50%, so the second copy fills in
// exactly as the first copy scrolls out of view.

const COMPANIES = [
  'Access Bank',
  'GTBank',
  'Flutterwave',
  'Andela',
  'Interswitch',
  'Paystack',
  'Konga',
  'MTN Nigeria',
  'Dangote Group',
  'Sterling Bank',
]

// ─── SocialProofBar ───────────────────────────────────────────────────────────

export default function SocialProofBar() {
  return (
    <section
      aria-label="Trusted companies"
      style={{
        // Requirements 4.1 — white bg, top/bottom #E5E7EB borders
        background: '#ffffff',
        borderTop: '1px solid #E5E7EB',
        borderBottom: '1px solid #E5E7EB',
        padding: '16px 0',
        overflow: 'hidden',
      }}
    >
      <div
        style={{
          maxWidth: '80rem',
          margin: '0 auto',
          padding: '0 1rem',
          display: 'flex',
          alignItems: 'center',
          gap: '2rem',
        }}
      >
        {/* Requirements 4.2 — "Trusted by 100+ companies" label on the left */}
        <p
          style={{
            flexShrink: 0,
            fontSize: '0.8125rem',
            fontWeight: 600,
            color: '#64748b',
            whiteSpace: 'nowrap',
          }}
        >
          Trusted by 100+ companies
        </p>

        {/* Scrolling strip container — clips the overflowing strip */}
        <div
          style={{
            flex: 1,
            overflow: 'hidden',
            // Fade edges so the strip looks seamless
            WebkitMaskImage:
              'linear-gradient(to right, transparent 0%, black 8%, black 92%, transparent 100%)',
            maskImage:
              'linear-gradient(to right, transparent 0%, black 8%, black 92%, transparent 100%)',
          }}
        >
          {/*
           * Requirements 4.3, 4.5 — CSS-only auto-scroll, pause on hover.
           * The `animate-scroll-x` class (defined in index.css) applies the
           * `scroll-x` keyframe at 30s linear infinite, and the `:hover` rule
           * sets `animation-play-state: paused`.
           */}
          <div
            className="animate-scroll-x"
            style={{
              display: 'flex',
              gap: '3rem',
              width: 'max-content',
            }}
          >
            {/* Requirements 4.4 — all 10 names rendered twice for seamless loop */}
            {[...COMPANIES, ...COMPANIES].map((name, i) => (
              <span
                key={i}
                style={{
                  fontSize: '0.875rem',
                  fontWeight: 600,
                  color: '#94a3b8',
                  whiteSpace: 'nowrap',
                  letterSpacing: '0.02em',
                }}
              >
                {name}
              </span>
            ))}
          </div>
        </div>
      </div>
    </section>
  )
}
