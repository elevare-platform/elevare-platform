import { useRef } from 'react'
import { motion, useInView } from 'framer-motion'
import { FileText, Cpu, RefreshCw, CheckCircle, Trophy, ArrowRight } from 'lucide-react'

const STEPS = [
  {
    step: '01',
    title: 'CV Ingestion & Inflow',
    subtitle: 'Multi-Source Parsing',
    description: 'Sourced CVs, direct applicant submissions, and mail ingestions enter the central talent repository.',
    icon: FileText,
  },
  {
    step: '02',
    title: 'Structured Skill Mapping',
    subtitle: 'Taxonomy Standardization',
    description: 'Profiles are mapped against verified taxonomies, technical competencies, and domain experience.',
    icon: Cpu,
  },
  {
    step: '03',
    title: 'Continuous Role Matching',
    subtitle: 'Real-Time Pipeline Scoring',
    description: 'Background workers rank talent against active employer requirements in real time.',
    icon: RefreshCw,
  },
  {
    step: '04',
    title: 'Transparent Match Analysis',
    subtitle: 'Explainable Fit Breakdown',
    description: 'Every match details skill overlap metrics, experience alignment, and notice period fit.',
    icon: CheckCircle,
  },
  {
    step: '05',
    title: 'Vetted Candidate Pools',
    subtitle: 'Direct Employer Introductions',
    description: 'Employers receive top-ranked candidate recommendations ready for direct introduction requests.',
    icon: Trophy,
  },
]

export default function TalentGraphFlow() {
  const ref = useRef(null)
  const isInView = useInView(ref, { once: true, amount: 0.25 })

  return (
    <section ref={ref} className="relative py-20 overflow-hidden">
      <div className="relative z-10 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center max-w-3xl mx-auto space-y-3 mb-16">
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-brand-amber/15 text-brand-amber text-xs font-bold uppercase tracking-wider border border-brand-amber/30">
            Sourcing Architecture
          </span>
          <h2 className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight leading-tight">
            How The Talent Graph Works
          </h2>
          <p className="text-base text-slate-300">
            From raw CV ingestion to candidate matching: continuous, automated, and unbiased.
          </p>
        </div>

        <div className="relative grid grid-cols-1 md:grid-cols-5 gap-4">
          <div className="hidden md:block absolute top-14 left-10 right-10 h-0.5 pointer-events-none z-0">
            <svg className="w-full h-full overflow-visible">
              <line
                x1="0%"
                y1="0"
                x2="100%"
                y2="0"
                stroke="rgba(255, 255, 255, 0.12)"
                strokeWidth="2"
                strokeDasharray="6 6"
              />
              <motion.line
                x1="0%"
                y1="0"
                x2="100%"
                y2="0"
                stroke="url(#line-gradient)"
                strokeWidth="2"
                initial={{ pathLength: 0 }}
                animate={{ pathLength: isInView ? 1 : 0 }}
                transition={{ duration: 1.8, ease: 'easeInOut' }}
              />
              <defs>
                <linearGradient id="line-gradient" x1="0%" y1="0%" x2="100%" y2="0%">
                  <stop offset="0%" stopColor="#1A4D8F" />
                  <stop offset="100%" stopColor="#E87722" />
                </linearGradient>
              </defs>
            </svg>
          </div>

          {STEPS.map((item, idx) => {
            const Icon = item.icon
            return (
              <motion.div
                key={item.step}
                initial={{ opacity: 0, y: 24 }}
                animate={{ opacity: isInView ? 1 : 0, y: isInView ? 0 : 24 }}
                transition={{ duration: 0.45, delay: idx * 0.12, ease: [0.16, 1, 0.3, 1] }}
                className="relative z-10 rounded-xl bg-slate-900/80 border border-white/10 p-5 flex flex-col justify-between shadow-lg hover:border-brand-amber/40 transition-all duration-200"
              >
                <div>
                  <div className="flex items-center justify-between mb-4">
                    <div className="w-10 h-10 rounded-lg bg-brand-blue/30 text-brand-blue border border-brand-blue/40 flex items-center justify-center">
                      <Icon size={20} />
                    </div>
                    <span className="text-xl font-bold text-slate-500 font-mono">
                      {item.step}
                    </span>
                  </div>

                  <h3 className="font-bold text-white text-sm leading-snug">
                    {item.title}
                  </h3>
                  <p className="text-xs font-semibold text-brand-amber mt-0.5">
                    {item.subtitle}
                  </p>
                  <p className="text-xs text-slate-300 mt-2 leading-relaxed">
                    {item.description}
                  </p>
                </div>

                {idx < STEPS.length - 1 && (
                  <div className="md:hidden flex justify-center py-2 text-slate-600">
                    <ArrowRight size={18} className="rotate-90" />
                  </div>
                )}
              </motion.div>
            )
          })}
        </div>
      </div>
    </section>
  )
}
