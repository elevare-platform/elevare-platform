import { useEffect, useRef, useState } from 'react'
import { useIntersectionObserver } from '@/hooks/useIntersectionObserver'

// ─── Stats data (Requirements 5.3) ───────────────────────────────────────────

const STATS = [
  { value: 7,   suffix: 'days', label: 'Average time to fill a role' },
  { value: 69,  suffix: '%',    label: 'of clients return to hire again' },
  { value: 500, suffix: '+',    label: 'companies found their perfect hire' },
]

// ─── useCounterAnimation ─────────────────────────────────────────────────────
// Counts from 0 to `target` over `duration` ms using requestAnimationFrame.
// Only starts when `isActive` becomes true (Requirements 5.2, 5.4).
// Returns the current integer display value.

function useCounterAnimation(target, duration, isActive) {
  const [count, setCount] = useState(0)
  const rafRef = useRef(null)
  const startTimeRef = useRef(null)

  useEffect(() => {
    if (!isActive) return

    // Reset in case it's re-triggered (though triggerOnce prevents this)
    startTimeRef.current = null

    function step(timestamp) {
      if (startTimeRef.current === null) {
        startTimeRef.current = timestamp
      }

      const elapsed = timestamp - startTimeRef.current
      const progress = Math.min(elapsed / duration, 1)
      const current = Math.floor(progress * target)

      setCount(current)

      if (progress < 1) {
        rafRef.current = requestAnimationFrame(step)
      } else {
        // Ensure we land exactly on target
        setCount(target)
      }
    }

    rafRef.current = requestAnimationFrame(step)

    return () => {
      if (rafRef.current) {
        cancelAnimationFrame(rafRef.current)
      }
    }
  }, [isActive, target, duration])

  return count
}

// ─── StatCard ─────────────────────────────────────────────────────────────────

function StatCard({ stat, isActive }) {
  const count = useCounterAnimation(stat.value, 1500, isActive)

  return (
    <div
      className="glass-panel-dark premium-card"
      style={{
        borderRadius: '0.75rem',
        padding: 'clamp(1.5rem, 4vw, 2.5rem) clamp(1rem, 3vw, 2rem)',
        textAlign: 'center',
        minWidth: 0,
      }}
    >
      {/* Animated number + suffix */}
      <p
        style={{
          margin: 0,
          fontSize: 'clamp(2rem, 5vw, 3rem)',
          fontWeight: 800,
          color: '#ffffff',
          lineHeight: 1,
          letterSpacing: '-0.02em',
        }}
      >
        {count}
        <span
          style={{
            fontSize: 'clamp(1rem, 2.5vw, 1.5rem)',
            fontWeight: 700,
            color: '#E87722',
            marginLeft: '0.25rem',
          }}
        >
          {stat.suffix}
        </span>
      </p>

      {/* Label */}
      <p
        style={{
          margin: '0.75rem 0 0',
          fontSize: 'clamp(0.8125rem, 1.5vw, 0.9375rem)',
          color: 'rgba(255,255,255,0.7)',
          lineHeight: 1.5,
        }}
      >
        {stat.label}
      </p>
    </div>
  )
}

// ─── StatsSection ─────────────────────────────────────────────────────────────

export default function StatsSection() {
  // Requirements 5.4 — single observer on the section wrapper, triggerOnce: true
  const [sectionRef, isVisible] = useIntersectionObserver({ threshold: 0.2, triggerOnce: true })

  return (
    <section
      ref={sectionRef}
      aria-label="Platform statistics"
      className="relative overflow-hidden"
      style={{
        background: 'linear-gradient(135deg, #0e1f3a 0%, #153d72 50%, #1A4D8F 100%)',
        padding: '5rem 1rem',
      }}
    >
      {/* Subtle grid pattern */}
      <div
        className="absolute inset-0 opacity-10 pointer-events-none"
        style={{
          backgroundImage: `
            linear-gradient(rgba(255,255,255,0.06) 1px, transparent 1px),
            linear-gradient(90deg, rgba(255,255,255,0.06) 1px, transparent 1px)
          `,
          backgroundSize: '40px 40px',
        }}
        aria-hidden="true"
      />
      <div
        style={{
          maxWidth: '56rem',
          margin: '0 auto',
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: '1.25rem',
        }}
      >
        {STATS.map((stat) => (
          <StatCard key={stat.label} stat={stat} isActive={isVisible} />
        ))}
      </div>
    </section>
  )
}
