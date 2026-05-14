import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'

// ─── FinalCTA ─────────────────────────────────────────────────────────────────
// Requirements: 10.1, 10.2, 10.3, 10.4
// Brand Blue background with radial gradient overlay, centred heading +
// subheading, Amber filled "Start Hiring →" and white outlined "Find a Job".

export default function FinalCTA() {
  return (
    <section
      className="relative overflow-hidden py-24 px-4"
      aria-label="Final call to action"
      style={{ background: '#1A4D8F' }}
    >
      {/* Radial gradient overlay — slightly lighter blue texture (Req 10.4) */}
      <div
        aria-hidden="true"
        style={{
          position: 'absolute',
          inset: 0,
          background:
            'radial-gradient(ellipse at 50% 0%, rgba(255,255,255,0.08) 0%, transparent 70%)',
          pointerEvents: 'none',
        }}
      />

      {/* Content — centred (Req 10.1) */}
      <div className="relative z-10 max-w-3xl mx-auto text-center">
        {/* Heading — white (Req 10.2) */}
        <h2 className="text-3xl sm:text-4xl lg:text-5xl font-bold text-white mb-4">
          Ready to Make Hiring Simple?
        </h2>

        {/* Subheading — white at 80% opacity (Req 10.2) */}
        <p
          className="text-lg sm:text-xl mb-10"
          style={{ color: 'rgba(255,255,255,0.8)' }}
        >
          Join 100+ companies that trust Elevare to find exceptional talent.
        </p>

        {/* CTA buttons (Req 10.3) */}
        <div className="flex flex-wrap justify-center gap-4">
          {/* Amber filled "Start Hiring →" */}
          <Link to="/register">
            <Button
              size="lg"
              className="bg-brand-amber hover:bg-brand-amber-dark text-white border-0 transition-transform duration-200 hover:scale-[1.02]"
            >
              Start Hiring →
            </Button>
          </Link>

          {/* White outlined "Find a Job" */}
          <Link to="/register">
            <Button
              size="lg"
              className="bg-transparent border border-white text-white hover:bg-white/10 transition-transform duration-200 hover:scale-[1.02]"
            >
              Find a Job
            </Button>
          </Link>
        </div>
      </div>
    </section>
  )
}
