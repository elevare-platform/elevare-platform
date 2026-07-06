import { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'

// ─── Profile card data ────────────────────────────────────────────────────────
// Each card has its own photo dimensions (w × h) to give a varied, organic feel.
// Positions are relative to the right-panel container so the three cards cluster
// in the centre of the column, close to each other.

const PROFILE_CARDS = [
  {
    id: 1,
    name: 'Jennifer O. Efe-Odiete',
    title: 'Founder & Lead Consultant, ACIPM, HRPL',
    available: true,
    availableLabel: 'Available now',
    imageUrl: '/hero-images/jennifer.png',
    imgW: 290,
    imgH: 230,
    delay: '0s',
    top: 80,
    left: 10,
    rotate: '-3deg',
    zIndex: 2,
  },
  {
    id: 2,
    name: 'Josephine Joseph Smith',
    title: 'Talent Acquisition & Business Development',
    available: false,
    availableLabel: 'Open to offers',
    imageUrl: '/hero-images/josephine.png',
    imgW: 290,
    imgH: 230,
    delay: '0.9s',
    top: 280,
    left: 270,
    rotate: '2deg',
    zIndex: 3,
  },
  {
    id: 3,
    name: 'Fatima Bello',
    title: 'Head of Finance',
    available: true,
    availableLabel: 'Available now',
    imageUrl: 'https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?w=290&h=230&fit=crop&crop=face',
    imgW: 290,
    imgH: 230,
    delay: '1.8s',
    top: 500,
    left: 20,
    rotate: '-2deg',
    zIndex: 2,
  },
]

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

const AVATAR_URLS = [
  'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=40&h=40&fit=crop&crop=face',
  'https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=40&h=40&fit=crop&crop=face',
  'https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=40&h=40&fit=crop&crop=face',
]

// ─── Cellotape X SVG ──────────────────────────────────────────────────────────
// Renders a semi-transparent tape strip crossing at the top-centre of the card,
// like a piece of sellotape pinning a photograph to a wall.

function TapeX() {
  return (
    <svg
      aria-hidden="true"
      style={{
        position: 'absolute',
        top: -14,
        left: '50%',
        transform: 'translateX(-50%)',
        zIndex: 10,
        pointerEvents: 'none',
      }}
      width="64"
      height="28"
      viewBox="0 0 64 28"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
    >
      {/* Tape body — semi-transparent warm white strip */}
      <rect x="0" y="6" width="64" height="16" rx="3" fill="rgba(255,252,230,0.82)" />
      {/* Tape sheen — subtle highlight across the middle */}
      <rect x="0" y="10" width="64" height="4" rx="1" fill="rgba(255,255,255,0.35)" />
      {/* X mark — two diagonal lines drawn in a slightly darker tape tone */}
      <line x1="22" y1="9" x2="42" y2="19" stroke="rgba(180,160,80,0.55)" strokeWidth="1.5" strokeLinecap="round" />
      <line x1="42" y1="9" x2="22" y2="19" stroke="rgba(180,160,80,0.55)" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  )
}

// ─── Floating photo card ──────────────────────────────────────────────────────

function ProfileCard({ card }) {
  return (
    <article
      className="hero-photo-card"
      style={{
        '--card-rotation': card.rotate,
        // White card with a slight warm tint — like photo paper
        background: '#fffef8',
        borderRadius: '6px',
        // Classic photo-print shadow
        boxShadow: '0 8px 32px rgba(0,0,0,0.18), 0 2px 8px rgba(0,0,0,0.10)',
        // Photo-print padding: more at the bottom (caption area)
        padding: '10px 10px 48px 10px',
        width: card.imgW + 20,
      }}
    >
      {/* Sellotape X pinning the card */}
      <TapeX />

      {/* Photo */}
      <img
        src={card.imageUrl}
        alt={`${card.name}, ${card.title}`}
        width={card.imgW}
        height={card.imgH}
        style={{
          width: card.imgW,
          height: card.imgH,
          display: 'block',
          objectFit: 'cover',
          // Slight desaturation for that printed-photo feel
          filter: 'saturate(0.92) contrast(1.04)',
        }}
      />

      {/* Caption area — below the photo, inside the white border */}
      <div style={{ marginTop: 10 }}>
        <p style={{ margin: 0, fontWeight: 700, fontSize: 13, color: '#1e293b', lineHeight: 1.3 }}>
          {card.name}
        </p>
        <p style={{ margin: '2px 0 6px', fontSize: 11, color: '#64748b' }}>
          {card.title}
        </p>
        <span
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 4,
            fontSize: 10,
            fontWeight: 600,
            padding: '2px 8px',
            borderRadius: 999,
            background: card.available ? '#f0fdf4' : '#fffbeb',
            color: card.available ? '#15803d' : '#b45309',
          }}
        >
          <span
            style={{
              width: 6,
              height: 6,
              borderRadius: '50%',
              background: card.available ? '#22c55e' : '#f59e0b',
              display: 'inline-block',
            }}
            aria-hidden="true"
          />
          {card.availableLabel}
        </span>
      </div>
    </article>
  )
}

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

      {/* Inner grid layout */}
      <div className="relative z-10 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 w-full py-20 sm:py-24 lg:py-0">
        <div className="grid grid-cols-1 lg:grid-cols-[53fr_47fr] gap-8 lg:gap-0 items-center min-h-screen">

          {/* ── Left: text content ── */}
          <div className="flex flex-col justify-center lg:pr-24">

            {/* Eyebrow */}
            <div className="hero-text-mask" style={{ marginBottom: '0.9rem' }}>
              <p
                className="font-bold text-sm tracking-widest uppercase hero-reveal-line"
                style={{ color: '#FCD34D', animationDelay: '150ms' }}
              >
                HR Strategy &amp; Workforce Solutions
              </p>
            </div>

            {/* Headline — merged into a single block to flow naturally and wrap, reducing vertical height */}
            <div style={{ marginBottom: '1.5rem' }}>
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

            {/* CTA buttons */}
            <div
              className="flex flex-col sm:flex-row lg:flex-row gap-3 sm:gap-4 mb-6 sm:mb-10 hero-entrance-ctas"
              style={{ animationDelay: '1550ms' }}
            >
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

            {/* Social proof avatar row */}
            <div className="flex items-center gap-3 hero-entrance-social" style={{ animationDelay: '1800ms' }}>
              <div className="flex -space-x-2">
                {AVATAR_URLS.map((url, i) => (
                  <img
                    key={i}
                    src={url}
                    alt={`Professional ${i + 1} on Elevare`}
                    width={36}
                    height={36}
                    className="rounded-full border-2 border-white object-cover hero-social-avatar"
                    style={{ width: 36, height: 36, animationDelay: `${1900 + i * 100}ms` }}
                  />
                ))}
              </div>
              <p className="text-sm font-medium" style={{ color: 'rgba(255,255,255,0.72)' }}>
                Join <span style={{ color: '#ffffff', fontWeight: 700 }}>2,400+</span> professionals already on Elevare
              </p>
            </div>
          </div>

          {/* ── Right: photo cards pinned to a corkboard ── */}
          <div
            className="relative hidden lg:flex items-center justify-start"
            style={{ height: '100vh', paddingLeft: '8%' }}
            aria-hidden="true"
          >
            {/* Subtle corkboard texture hint */}
            <div
              className="hero-corkboard-glow"
              style={{
                position: 'absolute',
                inset: 0,
                background: 'radial-gradient(ellipse at 60% 50%, rgba(180,140,80,0.07) 0%, transparent 70%)',
                pointerEvents: 'none',
              }}
            />

            {/* Cards container — fixed px sizing so gaps are guaranteed */}
            <div style={{ position: 'relative', width: 610, height: 860 }}>

              {/* Waterfall connector — Jennifer top-centre → Josephine centre only */}
              <svg
                aria-hidden="true"
                className="hero-entrance-connector"
                style={{
                  position: 'absolute',
                  inset: 0,
                  width: '100%',
                  height: '100%',
                  pointerEvents: 'none',
                  zIndex: 1,
                  overflow: 'visible',
                }}
                viewBox="0 0 610 860"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
              >
                <defs>
                  <marker id="wf-arrow" markerWidth="7" markerHeight="7" refX="3.5" refY="3.5" orient="auto">
                    <circle cx="3.5" cy="3.5" r="2.5" fill="#E87722" opacity="0.75" />
                  </marker>
                </defs>

                {/*
                  Jennifer top-centre: left=10, imgW=290 → centre x = 10+145 = 155, top y = 80
                  Josephine centre: left=270, imgW=290 → centre x = 270+145 = 415, top=280, imgH=230 → centre y = 280+115 = 395
                */}
                <path
                  d="M 165 80 C 80 200, 500 180, 425 395"
                  stroke="#E87722"
                  strokeWidth="1.8"
                  strokeDasharray="7 6"
                  strokeLinecap="round"
                  strokeDashoffset="900"
                  markerEnd="url(#wf-arrow)"
                  style={{
                    animation: 'draw-waterfall 5s ease-in-out infinite',
                  }}
                />
              </svg>

              {PROFILE_CARDS.map((card, i) => (
                <div
                  key={card.id}
                  className="hero-card-wrapper hero-card-drop"
                  style={{
                    position: 'absolute',
                    top: card.top,
                    left: card.left,
                    zIndex: card.zIndex,
                    width: card.imgW + 20,
                    '--drop-delay': `${1400 + i * 380}ms`,
                  }}
                >
                  <div
                    className="hero-card-float"
                    style={{ animationDelay: card.delay }}
                  >
                    <ProfileCard card={card} />
                  </div>
                </div>
              ))}
            </div>
          </div>

        </div>
      </div>
    </section>
  )
}
