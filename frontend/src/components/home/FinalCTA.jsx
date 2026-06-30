import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'

// ─── FinalCTA ─────────────────────────────────────────────────────────────────
// Premium CTA with background image, gradient overlay, Lobster Two heading,
// and conversion-focused dual CTAs.

export default function FinalCTA() {
  return (
    <section
      className="relative overflow-hidden py-28 px-4"
      aria-label="Final call to action"
    >
      {/* Background image */}
      <div
        className="absolute inset-0 bg-cover bg-center bg-no-repeat scale-105"
        style={{ backgroundImage: "url('/hero-images/img6.jpg')" }}
        aria-hidden="true"
      />
      {/* Dark gradient overlay */}
      <div
        aria-hidden="true"
        className="absolute inset-0"
        style={{
          background:
            'linear-gradient(135deg, rgba(14,31,58,0.92) 0%, rgba(26,77,143,0.88) 50%, rgba(14,31,58,0.92) 100%)',
        }}
      />
      {/* Radial glow */}
      <div
        aria-hidden="true"
        className="absolute inset-0"
        style={{
          background:
            'radial-gradient(ellipse at 50% 0%, rgba(232,119,34,0.12) 0%, transparent 60%)',
          pointerEvents: 'none',
        }}
      />

      {/* Content */}
      <div className="relative z-10 max-w-3xl mx-auto text-center">
        <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded bg-brand-amber/20 text-brand-amber text-xs font-bold uppercase tracking-wider border border-brand-amber/35 mb-6">
          Get Started Today
        </span>

        <h2
          className="text-3xl sm:text-4xl lg:text-6xl font-bold text-white mb-5"
          style={{ fontFamily: "'Lobster Two', cursive" }}
        >
          Ready to Make Hiring Simple?
        </h2>

        <p
          className="text-lg sm:text-xl mb-10 leading-relaxed"
          style={{ color: 'rgba(255,255,255,0.82)' }}
        >
          Join 100+ companies that trust Elevare to find exceptional talent.
        </p>

        {/* CTA buttons */}
        <div className="flex flex-wrap justify-center gap-4">
          <Link to="/register">
            <Button
              size="lg"
              className="bg-brand-amber hover:bg-brand-amber-dark text-white border-0 transition-all duration-300 hover:scale-[1.03] shadow-lg hover:shadow-xl px-8 py-4 text-base font-bold"
            >
              Start Hiring →
            </Button>
          </Link>

          <Link to="/jobs">
            <Button
              size="lg"
              className="bg-white/10 backdrop-blur border border-white/30 text-white hover:bg-white/20 transition-all duration-300 hover:scale-[1.03] px-8 py-4 text-base font-bold"
            >
              Find a Job
            </Button>
          </Link>
        </div>
      </div>
    </section>
  )
}
