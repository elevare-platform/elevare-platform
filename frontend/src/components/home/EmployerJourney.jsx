import { useState, useEffect, useRef } from 'react'
import { FileText, Search, Brain, UserCheck, Award, ChevronRight } from 'lucide-react'
import { useIntersectionObserver } from '@/hooks/useIntersectionObserver'

const STEPS = [
  {
    icon: FileText,
    title: 'Employer Need',
    tagline: 'Step 01 — Define Requirements',
    description: 'Post your requirements, salary range, and company culture expectations in under 10 minutes.',
    color: '#E87722',
  },
  {
    icon: Search,
    title: 'Talent Search',
    tagline: 'Step 02 — Active Sourcing',
    description: 'Our system scans our network of over 50,000+ pre-vetted professionals across Africa.',
    color: '#1A4D8F',
  },
  {
    icon: Brain,
    title: 'AI Screening',
    tagline: 'Step 03 — Deterministic Scoring',
    description: 'Candidates are evaluated and ranked based on tech stack fit, past experience, and soft skills.',
    color: '#8b5cf6',
  },
  {
    icon: UserCheck,
    title: 'Shortlisting',
    tagline: 'Step 04 — Premium Curated Matches',
    description: 'Receive a structured, scored report of the top 3 matches. No resume pile to sift through.',
    color: '#06b6d4',
  },
  {
    icon: Award,
    title: 'Hiring Success',
    tagline: 'Step 05 — Onboarding & Scaling',
    description: 'Conduct interviews and make a confident offer. 94% of our placed talent stay beyond 12 months.',
    color: '#10b981',
  },
]

export default function EmployerJourney() {
  const [sectionRef, isVisible] = useIntersectionObserver({ threshold: 0.1, triggerOnce: false })
  const [activeStep, setActiveStep] = useState(0)
  const [scrollProgress, setScrollProgress] = useState(0)
  const containerRef = useRef(null)

  useEffect(() => {
    const handleScroll = () => {
      if (!containerRef.current) return
      const rect = containerRef.current.getBoundingClientRect()
      const viewportHeight = window.innerHeight
      
      // Calculate how far through the section the user has scrolled
      const totalHeight = rect.height
      const scrolledPast = -rect.top + (viewportHeight / 2)
      
      if (scrolledPast < 0) {
        setScrollProgress(0)
        setActiveStep(0)
      } else if (scrolledPast > totalHeight) {
        setScrollProgress(100)
        setActiveStep(STEPS.length - 1)
      } else {
        const percentage = (scrolledPast / totalHeight) * 100
        setScrollProgress(percentage)
        
        // Map percentage to step index
        const stepIndex = Math.min(
          Math.floor((percentage / 100) * STEPS.length),
          STEPS.length - 1
        )
        setActiveStep(stepIndex)
      }
    }

    window.addEventListener('scroll', handleScroll, { passive: true })
    return () => window.removeEventListener('scroll', handleScroll)
  }, [])

  return (
    <section
      ref={sectionRef}
      id="employer-journey-section"
      className="relative py-24 sm:py-32 overflow-hidden bg-slate-900 text-white"
    >
      {/* Abstract Design Accents */}
      <div className="absolute top-0 right-0 w-[500px] h-[500px] bg-brand-blue/10 rounded-full blur-[120px] pointer-events-none" />
      <div className="absolute bottom-0 left-0 w-[600px] h-[600px] bg-brand-amber/5 rounded-full blur-[140px] pointer-events-none" />

      {/* Grid Pattern overlay */}
      <div className="absolute inset-0 brand-panel-grid opacity-10 pointer-events-none" />

      <div className="max-w-7xl mx-auto px-6 sm:px-8 lg:px-12 relative z-10">
        
        {/* Header */}
        <div className="text-center max-w-3xl mx-auto mb-20">
          <span className="text-xs font-extrabold uppercase tracking-widest text-brand-amber bg-brand-amber/10 px-4 py-1.5 rounded-full border border-brand-amber/20">
            Employer Experience
          </span>
          <h2
            className="text-4xl sm:text-5xl font-extrabold mt-6 tracking-tight text-white leading-tight"
            style={{ fontFamily: "'Lobster Two', cursive" }}
          >
            The Journey to Hiring Excellence
          </h2>
          <p className="mt-4 text-slate-400 text-base sm:text-lg max-w-xl mx-auto">
            From discovering your need to securing top-tier talent, watch how we streamline your recruitment cycle step-by-step.
          </p>
        </div>

        {/* Scroll Interactive Showcase Container */}
        <div ref={containerRef} className="grid grid-cols-1 lg:grid-cols-12 gap-12 lg:gap-16 items-start">
          
          {/* Left Column: Sticky Title & Process Visualization */}
          <div className="lg:col-span-5 lg:sticky lg:top-32 flex flex-col justify-between">
            <div>
              <div className="text-slate-400 text-sm font-semibold tracking-wide uppercase mb-3">
                Live Roadmap
              </div>
              <h3 className="text-2xl sm:text-3xl font-bold mb-6 text-white leading-tight">
                Streamlined pipeline that guarantees results.
              </h3>
              <p className="text-slate-300 text-sm sm:text-base leading-relaxed mb-8">
                As you scroll, notice how each step connects seamlessly to the next, forming an integrated path that drives productivity and ensures recruitment success.
              </p>
            </div>

            {/* Visual Progress Meter (Left side representation) */}
            <div className="hidden lg:block bg-slate-800/40 border border-slate-700/50 rounded-2xl p-6 backdrop-blur-md">
              <div className="flex justify-between items-center mb-4">
                <span className="text-xs font-bold text-slate-400">PIPELINE MILESTONES</span>
                <span className="text-xs font-bold text-brand-amber">{Math.round(scrollProgress)}%</span>
              </div>
              {/* Process Bar */}
              <div className="w-full h-2.5 bg-slate-700 rounded-full overflow-hidden mb-6">
                <div
                  className="h-full bg-gradient-to-r from-brand-blue to-brand-amber rounded-full transition-all duration-300 ease-out"
                  style={{ width: `${scrollProgress}%` }}
                />
              </div>
              {/* Active Step Indicator */}
              <div className="flex items-center gap-4">
                <div
                  className="w-12 h-12 rounded-xl flex items-center justify-center transition-all duration-300"
                  style={{
                    backgroundColor: `${STEPS[activeStep].color}15`,
                    color: STEPS[activeStep].color,
                    border: `1px solid ${STEPS[activeStep].color}30`
                  }}
                >
                  {(() => {
                    const IconComp = STEPS[activeStep].icon
                    return <IconComp className="w-6 h-6 animate-pulse" />
                  })()}
                </div>
                <div>
                  <p className="text-[10px] font-bold text-brand-amber uppercase tracking-wider">
                    CURRENT STAGE
                  </p>
                  <p className="text-sm font-bold text-white">
                    {STEPS[activeStep].title}
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* Right Column: Steps with Scroll Timeline */}
          <div className="lg:col-span-7 relative pl-8 sm:pl-12">
            
            {/* Vertical timeline line */}
            <div className="absolute left-[23px] sm:left-[31px] top-4 bottom-4 w-1 bg-slate-800 rounded-full">
              {/* Glowing scroll progress filling line */}
              <div
                className="absolute top-0 w-full bg-gradient-to-b from-brand-blue via-brand-amber to-emerald-500 rounded-full transition-all duration-300 ease-out"
                style={{ height: `${scrollProgress}%` }}
              />
            </div>

            {/* List of Journey Cards */}
            <div className="flex flex-col gap-10">
              {STEPS.map((step, idx) => {
                const Icon = step.icon
                const isActive = activeStep === idx
                return (
                  <div
                    key={idx}
                    onClick={() => setActiveStep(idx)}
                    className={`relative flex gap-6 items-start cursor-pointer group transition-all duration-500 rounded-2xl p-4 sm:p-6 ${
                      isActive
                        ? 'bg-slate-800/60 border border-slate-700/50 shadow-xl scale-[1.01] backdrop-blur-md'
                        : 'border border-transparent hover:bg-slate-800/20'
                    }`}
                  >
                    {/* Node Circle */}
                    <div
                      className={`relative z-10 flex-shrink-0 w-12 h-12 sm:w-16 sm:h-16 rounded-full flex items-center justify-center transition-all duration-500 border-2 ${
                        isActive
                          ? 'bg-slate-900 border-white text-white shadow-lg'
                          : 'bg-slate-800 border-slate-700 text-slate-500 group-hover:border-slate-500 group-hover:text-slate-300'
                      }`}
                      style={{
                        boxShadow: isActive ? `0 0 20px ${step.color}25` : 'none',
                        borderColor: isActive ? step.color : undefined
                      }}
                    >
                      <Icon className={`w-5 h-5 sm:w-6 sm:h-6 transition-transform duration-500 ${isActive ? 'scale-110' : ''}`} />
                    </div>

                    {/* Step Content */}
                    <div>
                      <span
                        className="text-[10px] font-bold tracking-widest uppercase transition-colors duration-500"
                        style={{ color: isActive ? step.color : '#94a3b8' }}
                      >
                        {step.tagline}
                      </span>
                      <h4 className="text-lg sm:text-xl font-bold text-white mt-1 group-hover:text-brand-amber transition-colors">
                        {step.title}
                      </h4>
                      <p className={`mt-2 text-xs sm:text-sm leading-relaxed transition-colors duration-500 ${
                        isActive ? 'text-slate-200' : 'text-slate-400'
                      }`}>
                        {step.description}
                      </p>
                      
                      {isActive && (
                        <div className="mt-4 flex items-center gap-1.5 text-xs font-bold text-brand-amber animate-fade-in-up">
                          <span>Explore details</span>
                          <ChevronRight className="w-3.5 h-3.5" />
                        </div>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>

          </div>

        </div>

      </div>
    </section>
  )
}
