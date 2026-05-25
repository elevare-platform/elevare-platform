import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'

// ─── Profile card data ────────────────────────────────────────────────────────
// Each card has its own photo dimensions (w × h) to give a varied, organic feel.
// Positions are relative to the right-panel container so the three cards cluster
// in the centre of the column, close to each other.

const PROFILE_CARDS = [
  {
    id: 1,
    name: 'Amara Okafor',
    title: 'Senior Product Designer',
    available: true,
    availableLabel: 'Available now',
    imageUrl: 'https://images.unsplash.com/photo-1531123897727-8f129e1688ce?w=200&h=200&fit=crop&crop=face',
    imgW: 200,
    imgH: 200,
    delay: '0s',
    top: 80,
    left: 20,
    rotate: '-3deg',
    zIndex: 2,
  },
  {
    id: 2,
    name: 'Chidi Nwosu',
    title: 'Engineering Manager',
    available: false,
    availableLabel: 'Open to offers',
    imageUrl: 'https://images.unsplash.com/photo-1506794778202-cad84cf45f1d?w=200&h=200&fit=crop&crop=face',
    imgW: 200,
    imgH: 200,
    delay: '0.9s',
    top: 280,
    left: 320,
    rotate: '2deg',
    zIndex: 3,
  },
  {
    id: 3,
    name: 'Fatima Bello',
    title: 'Head of Finance',
    available: true,
    availableLabel: 'Available now',
    imageUrl: 'https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?w=200&h=200&fit=crop&crop=face',
    imgW: 200,
    imgH: 200,
    delay: '1.8s',
    top: 460,
    left: 30,
    rotate: '-2deg',
    zIndex: 2,
  },
]

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
      style={{
        position: 'absolute',
        top: card.top,
        left: card.left,
        zIndex: card.zIndex,
        transform: `rotate(${card.rotate})`,
        animation: `float 5s ease-in-out infinite`,
        animationDelay: card.delay,
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
      style={{
        // #1A4D8F fallback for when the background image fails to load (Req 1.5)
        backgroundColor: '#1A4D8F',
        // Left side stays the light blue-tinted grid; right side fades to a warm
        // off-white so the photo cards feel like they're pinned to a corkboard.
        background: `
          linear-gradient(
            to right,
            #EEF3FA 0%,
            #EEF3FA 45%,
            #f5f0e8 72%,
            #ede8dc 100%
          )
        `,
      }}
    >
      {/* Grid pattern overlay — only covers the left portion */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          backgroundImage: `
            linear-gradient(rgba(26,77,143,0.04) 1px, transparent 1px),
            linear-gradient(90deg, rgba(26,77,143,0.04) 1px, transparent 1px)
          `,
          backgroundSize: '40px 40px',
          // Fade the grid out before the right half
          WebkitMaskImage: 'linear-gradient(to right, black 0%, black 40%, transparent 65%)',
          maskImage: 'linear-gradient(to right, black 0%, black 40%, transparent 65%)',
        }}
        aria-hidden="true"
      />

      {/* Inner grid layout */}
      <div className="relative z-10 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 w-full py-20 sm:py-24 lg:py-0">
        <div className="grid grid-cols-1 lg:grid-cols-[60fr_40fr] gap-8 lg:gap-0 items-center min-h-screen">

          {/* ── Left: text content ── */}
          <div className="flex flex-col justify-center lg:pr-24">
            {/* Eyebrow */}
            <p className="text-brand-amber font-semibold text-xs tracking-widest uppercase mb-3 sm:mb-4">
              Nigeria's Premier Recruitment Platform
            </p>

            {/* Headline */}
            <h1 className="text-3xl sm:text-4xl lg:text-5xl xl:text-6xl font-bold text-text leading-tight mb-4 sm:mb-6">
              Connecting{' '}
              <em className="not-italic text-brand-amber">Exceptional</em>{' '}
              Talent
              <br />
              With Ambitious Companies
            </h1>

            {/* Subheadline */}
            <p className="text-base sm:text-lg text-text-muted leading-relaxed mb-6 sm:mb-8 max-w-lg">
              From Lagos to London, we match the right people with the right roles.
              Fast, precise, and built for African ambition.
            </p>

            {/* CTA buttons — stacked on mobile, side-by-side on desktop (Req 1.2, 1.3, 1.4) */}
            <div className="flex flex-col sm:flex-row lg:flex-row gap-3 sm:gap-4 mb-6 sm:mb-10">
              <Link to="/register">
                <Button
                  size="lg"
                  className="w-full sm:w-auto min-h-[44px] transition-transform duration-200 hover:scale-[1.02] bg-brand-blue hover:bg-brand-blue-dark text-white border-0"
                >
                  Hire Talent →
                </Button>
              </Link>
              <Link to="/jobs">
                <Button
                  size="lg"
                  variant="outline"
                  className="w-full sm:w-auto min-h-[44px] transition-transform duration-200 hover:scale-[1.02]"
                >
                  Find a Role →
                </Button>
              </Link>
            </div>

            {/* Social proof avatar row */}
            <div className="flex items-center gap-3">
              <div className="flex -space-x-2">
                {AVATAR_URLS.map((url, i) => (
                  <img
                    key={i}
                    src={url}
                    alt={`Professional ${i + 1} on Elevare`}
                    width={36}
                    height={36}
                    className="rounded-full border-2 border-white object-cover"
                    style={{ width: 36, height: 36 }}
                  />
                ))}
              </div>
              <p className="text-sm text-text-muted font-medium">
                Join <span className="text-text font-semibold">2,400+</span> professionals already on Elevare
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
              style={{
                position: 'absolute',
                inset: 0,
                background: 'radial-gradient(ellipse at 60% 50%, rgba(180,140,80,0.07) 0%, transparent 70%)',
                pointerEvents: 'none',
              }}
            />

            {/* Cards container — fixed px sizing so gaps are guaranteed */}
            <div style={{ position: 'relative', width: 540, height: 820 }}>

              {/* Waterfall connector — draws top-centre of Amara → Chidi centre → bottom-centre of Fatima */}
              <svg
                aria-hidden="true"
                style={{
                  position: 'absolute',
                  inset: 0,
                  width: '100%',
                  height: '100%',
                  pointerEvents: 'none',
                  zIndex: 1,
                  overflow: 'visible',
                }}
                viewBox="0 0 540 820"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
              >
                <defs>
                  <marker id="wf-arrow" markerWidth="7" markerHeight="7" refX="3.5" refY="3.5" orient="auto">
                    <circle cx="3.5" cy="3.5" r="2.5" fill="#E87722" opacity="0.75" />
                  </marker>
                </defs>

                {/*
                  Chidi centre is now at (320+110, 280+110) = (430, 390)
                  Amara top-centre: (20+110, 80) = (130, 90)
                  Fatima bottom-centre: (30+110, 460+260) = (140, 720)
                */}
                <path
                  d="
                    M 130 90
                    C 40 220, 500 200, 430 390
                    C 360 560, 220 580, 140 720
                  "
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

              {PROFILE_CARDS.map((card) => (
                <ProfileCard key={card.id} card={card} />
              ))}
            </div>
          </div>

        </div>
      </div>
    </section>
  )
}
