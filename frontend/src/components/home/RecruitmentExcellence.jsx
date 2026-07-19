import { ArrowRight } from 'lucide-react'
import { Button } from '@/components/ui/button'

export default function RecruitmentExcellence({ onBookConsultation }) {
  return (
    <section
      aria-label="Recruitment Excellence Banner"
      className="relative min-h-[500px] flex items-center justify-center overflow-hidden bg-slate-900 py-20 px-6 sm:px-8"
    >
      {/* Parallax Background Image */}
      <div
        className="absolute inset-0 bg-cover bg-center bg-no-repeat opacity-40 scale-105"
        style={{
          backgroundImage: "url('/hero-images/img32.jpg')",
          backgroundAttachment: 'fixed',
          transform: 'translate3d(0, 0, 0)', // Force GPU acceleration
        }}
      />

      {/* Dark Ambient Overlay */}
      <div className="absolute inset-0 bg-gradient-to-b from-slate-950/80 via-slate-950/65 to-slate-950/80" />

      {/* Content Box */}
      <div className="relative max-w-4xl mx-auto text-center z-10 text-white">
        
        {/* Amber Tagline */}
        <span className="text-xs font-extrabold uppercase tracking-widest text-brand-amber bg-brand-amber/15 border border-brand-amber/35 px-4 py-1.5 rounded-full inline-block mb-8 animate-pulse">
          RECRUITMENT EXCELLENCE
        </span>

        {/* Large Statement */}
        <h2
          className="font-sans text-4xl sm:text-5xl md:text-7xl font-extrabold tracking-tight mb-6 leading-[1.1] text-white"
        >
          Elevating African Talent to a Global Standard
        </h2>

        {/* Minimal Supporting Text */}
        <p className="text-base sm:text-lg md:text-xl text-slate-200 mb-10 max-w-2xl mx-auto font-medium leading-relaxed">
          We curate the top 5% of professional talent in Africa, connecting them with organizations that demand absolute execution.
        </p>

        {/* Strong CTA */}
        <div className="flex justify-center items-center">
          <Button
            size="lg"
            onClick={onBookConsultation}
            className="bg-brand-amber hover:bg-brand-amber-dark text-white border-none font-bold rounded-lg shadow-lg hover:shadow-brand-amber/20 hover:scale-[1.03] transition-all duration-300 px-8 py-6 text-base"
          >
            Partner With Us Now <ArrowRight className="w-5 h-5 ml-2.5" />
          </Button>
        </div>

      </div>

      {/* Edge Curved Transitions/Separators */}
      <div className="absolute bottom-0 left-0 right-0 h-12 bg-gradient-to-t from-slate-950 to-transparent pointer-events-none" />
      <div className="absolute top-0 left-0 right-0 h-12 bg-gradient-to-b from-slate-900 to-transparent pointer-events-none" />
    </section>
  )
}
