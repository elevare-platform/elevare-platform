import { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'

// ─── Hero background slides ──────────────────────────────────────────────────
// Images are served from /public/hero-images/ via Vite static assets.
const HERO_SLIDES = [
  { src: '/hero-images/img1.jpg', alt: 'Aerial view of Victoria Island, Lagos — Civic Centre Towers and the waterfront' },
  { src: '/hero-images/img4.jpg', alt: 'Lagos skyline looking south along the marina corridor' },
  { src: '/hero-images/img3.jpg', alt: 'Lekki-Ikoyi Link Bridge at dusk — an engineering landmark' },
  { src: '/hero-images/img2.jpg', alt: 'Lagos cityscape at golden hour — the mainland and harbour' },
  { src: '/hero-images/img5.jpg', alt: 'Lagos panorama — lush greenery meets a modern skyline' },
]

// ─── HeroSlideshow ───────────────────────────────────────────────────────────
// Full-bleed layer that crossfades between slides. Each active slide plays a
// slow Ken Burns pan via CSS animation. Pauses the auto-advance while hovered.

function HeroSlideshow() {
  const [current, setCurrent] = useState(0)
  const [paused, setPaused] = useState(false)

  const advance = useCallback(() => {
    setCurrent((prev) => (prev + 1) % HERO_SLIDES.length)
  }, [])

  useEffect(() => {
    if (paused) return
    const id = setInterval(advance, 6000)
    return () => clearInterval(id)
  }, [advance, paused])

  return (
    <div
      className="absolute inset-0 hero-slideshow"
      aria-hidden="true"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
    >
      {HERO_SLIDES.map((slide, i) => (
        <div
          key={slide.src}
          className={`hero-slide ${ i === current ? 'hero-slide--active' : '' }`}
        >
          <img
            src={slide.src}
            alt={slide.alt}
            className="hero-slide-img"
            draggable={false}
          />
        </div>
      ))}

      {/* Multi-stop overlay: opaque dark on the left (text area) → semi-transparent right */}
      <div className="hero-slide-overlay" />
    </div>
  )
}

// ─── Social proof avatars ─────────────────────────────────────────────────────

const AVATAR_PROFILES = [
  { src: '/hero-images/jennifer.png', alt: 'Jennifer O. Efe-Odiete, Founder & Lead Consultant at Elevare' },
  { src: '/hero-images/josephine.png', alt: 'Josephine Joseph Smith, Talent Acquisition & Business Development at Elevare' },
  { src: '/hero-images/stephanie.png', alt: 'Stephanie, Talent Acquisition & Employer Branding Executive at Elevare' },
]

// ─── Right-panel feature list ────────────────────────────────────────────────
// Echoes the three colour-coded phrases in the headline as a small glass
// "what we deliver" panel, so the right side of the hero isn't empty once the
// photo cards are gone — without reaching for stock photography.

const FEATURE_ROWS = [
  {
    label: 'Human Capital Advisory',
    color: '#38bdf8',
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <rect x="3" y="7" width="18" height="12" rx="2" stroke="white" strokeWidth="1.6" />
        <path d="M8 7V5.5C8 4.67157 8.67157 4 9.5 4H14.5C15.3284 4 16 4.67157 16 5.5V7" stroke="white" strokeWidth="1.6" />
        <path d="M3 12H21" stroke="white" strokeWidth="1.6" />
      </svg>
    ),
  },
  {
    label: 'Workforce Transformation',
    color: '#1a4d8f',
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M4 8C4 8 6.5 4.5 12 4.5C16 4.5 18.5 6.5 19.5 8" stroke="white" strokeWidth="1.6" strokeLinecap="round" />
        <path d="M20 16C20 16 17.5 19.5 12 19.5C8 19.5 5.5 17.5 4.5 16" stroke="white" strokeWidth="1.6" strokeLinecap="round" />
        <path d="M17 5L19.5 8L16.5 9.5" stroke="white" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
        <path d="M7 19L4.5 16L7.5 14.5" stroke="white" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    ),
  },
  {
    label: 'Recruitment Consulting',
    color: '#e87722',
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <circle cx="12" cy="12" r="8" stroke="white" strokeWidth="1.6" />
        <circle cx="12" cy="12" r="4" stroke="white" strokeWidth="1.6" />
        <circle cx="12" cy="12" r="0.75" fill="white" />
      </svg>
    ),
  },
]

// ─── HeroSection ─────────────────────────────────────────────────────────────

export default function HeroSection({ onBookConsultation }) {
  return (
    <section
      className="relative min-h-screen flex items-center overflow-hidden"
      aria-label="Hero"
      style={{ backgroundColor: '#0e1f3a' }}
    >
      {/* ── Crossfade background slideshow ── */}
      <HeroSlideshow />

      {/* Grid pattern overlay — only covers the left portion */}
      <div
        className="absolute inset-0 pointer-events-none hero-grid-pattern"
        style={{
          backgroundImage: `
            linear-gradient(rgba(255,255,255,0.06) 1px, transparent 1px),
            linear-gradient(90deg, rgba(255,255,255,0.06) 1px, transparent 1px)
          `,
          backgroundSize: '40px 40px',
          WebkitMaskImage: 'linear-gradient(to right, black 0%, black 40%, transparent 65%)',
          maskImage: 'linear-gradient(to right, black 0%, black 40%, transparent 65%)',
        }}
        aria-hidden="true"
      />

      {/* Inner content — text on the left, a small glass feature panel on the
          right so the space the photo cards used to fill doesn't sit empty */}
      <div className="relative z-10 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 w-full py-20 sm:py-24 lg:py-0">
        <div className="grid grid-cols-1 lg:grid-cols-[1.15fr_0.85fr] gap-10 lg:gap-12 items-center min-h-screen">

          {/* ── Left: text content ── */}
          <div className="flex flex-col justify-center max-w-2xl">

            {/* Eyebrow */}
            <div className="hero-text-mask" style={{ marginBottom: '1.1rem' }}>
              <div
                className="hero-eyebrow-badge hero-reveal-line"
                style={{ animationDelay: '150ms' }}
              >
                <span className="hero-eyebrow-dot" aria-hidden="true" />
                <span className="font-bold text-sm tracking-widest uppercase" style={{ color: '#FCD34D' }}>
                  HR Strategy &amp; Workforce Solutions
                </span>
              </div>
            </div>

            {/* Headline — merged into a single block to flow naturally and wrap, reducing vertical height */}
            <div style={{ marginBottom: '1.1rem' }}>
              <div className="hero-text-mask">
                <h1
                  className="text-4xl sm:text-5xl lg:text-6xl font-bold leading-tight hero-reveal-line"
                  style={{ animationDelay: '400ms', fontFamily: "'Lobster Two', cursive", lineHeight: '1.2' }}
                >
                  <span style={{ color: '#ffffff' }}>Human Capital Advisory </span>
                  <span style={{ color: '#38bdf8' }}>&amp; Workforce Transformation </span>
                  <span style={{ color: '#E87722' }}>&amp; Recruitment Consulting</span>
                </h1>
              </div>
            </div>

            {/* Divider — a small brand-gradient accent that grounds the transition to body copy */}
            <div className="hero-divider-line" style={{ marginBottom: '1.25rem', animationDelay: '1100ms' }} aria-hidden="true" />

            {/* Subheadline — enters as one block after the headline finishes */}
            <div className="hero-text-mask" style={{ marginBottom: '1.75rem' }}>
              <p
                className="text-base sm:text-lg leading-relaxed max-w-xl hero-reveal-line"
                style={{ color: 'rgba(255,255,255,0.78)', animationDelay: '1250ms' }}
              >
                Where Talent Meets Opportunity. Elevating People, Empowering Businesses.
                We align state-of-the-art talent strategies with organizational goals to drive real business growth.
              </p>
            </div>

            {/* CTA panel — buttons sit on an elevated glass surface for more visual weight */}
            <div
              className="hero-cta-panel hero-entrance-ctas mb-6 sm:mb-8"
              style={{ animationDelay: '1550ms', width: 'fit-content' }}
            >
              <div className="flex flex-col sm:flex-row gap-3 sm:gap-4">
                <Link to="/register">
                  <Button
                    size="lg"
                    className="hero-btn-primary w-full sm:w-auto min-h-[44px] bg-brand-blue hover:bg-brand-blue-dark text-white border-0"
                  >
                    Hire Talent <span className="hero-btn-arrow">→</span>
                  </Button>
                </Link>
                <Link to="/jobs">
                  <Button
                    size="lg"
                    variant="outline"
                    className="hero-btn-secondary w-full sm:w-auto min-h-[44px]"
                    style={{ borderColor: 'rgba(255,255,255,0.35)', color: '#ffffff', background: 'rgba(255,255,255,0.08)' }}
                  >
                    Find a Role <span className="hero-btn-arrow">→</span>
                  </Button>
                </Link>
              </div>
            </div>

            {/* Social proof — an integrated glass chip rather than a bare row */}
            <div className="hero-social-proof-chip hero-entrance-social" style={{ animationDelay: '1800ms' }}>
              <div className="flex -space-x-2">
                {AVATAR_PROFILES.map((avatar, i) => (
                  <img
                    key={i}
                    src={avatar.src}
                    alt={avatar.alt}
                    width={36}
                    height={36}
                    className="rounded-full border-2 border-white object-cover hero-social-avatar"
                    style={{ width: 36, height: 36, animationDelay: `${1900 + i * 100}ms` }}
                  />
                ))}
              </div>
              <span className="hero-social-proof-divider" aria-hidden="true" />
              <p className="text-sm font-medium" style={{ color: 'rgba(255,255,255,0.72)' }}>
                Join <span style={{ color: '#ffffff', fontWeight: 700 }}>2,400+</span> professionals already on Elevare
              </p>
            </div>
          </div>

          {/* ── Right: glass feature panel ── */}
          <div className="relative hidden lg:flex items-center justify-center" aria-hidden="true">
            <div
              className="hero-panel-glow"
              style={{
                position: 'absolute',
                top: '8%',
                left: '10%',
                width: '65%',
                height: '45%',
                background: 'radial-gradient(circle, rgba(56,189,248,0.5) 0%, transparent 70%)',
              }}
            />
            <div
              className="hero-panel-glow"
              style={{
                position: 'absolute',
                bottom: '10%',
                right: '8%',
                width: '55%',
                height: '40%',
                background: 'radial-gradient(circle, rgba(232,119,34,0.45) 0%, transparent 70%)',
                animationDelay: '3s',
              }}
            />

            <div className="hero-feature-panel" style={{ animationDelay: '1200ms' }}>
              <div className="hero-feature-panel-float">
                <p
                  className="font-bold text-xs tracking-widest uppercase"
                  style={{ color: 'rgba(255,255,255,0.55)', marginBottom: 4 }}
                >
                  What We Deliver
                </p>

                {FEATURE_ROWS.map((row, i) => (
                  <div key={row.label}>
                    <div className="hero-feature-row">
                      <div className="hero-feature-icon" style={{ background: row.color }}>
                        {row.icon}
                      </div>
                      <p className="font-semibold text-base" style={{ color: '#ffffff' }}>
                        {row.label}
                      </p>
                    </div>
                    {i < FEATURE_ROWS.length - 1 && <div className="hero-feature-divider" />}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
