import { useRef } from 'react'
import { Link } from 'react-router-dom'
import { motion, useInView } from 'framer-motion'
import { Users, ArrowUpRight } from 'lucide-react'

// Illustrative only  -  spans multiple industries deliberately, so a visitor
// hiring for oil & gas or retail sees relevance, not just tech roles.
// TODO: once real talent-pool volume exists per industry, replace with a
// live aggregate query instead of this static list.
const PIPELINES = [
  {
    id: 'pipe-1',
    roleName: 'Senior Backend Engineers',
    count: 342,
    matchRate: '98% Avg Match',
    avatars: ['O.K.', 'F.A.', 'M.I.', 'E.N.'],
    tags: ['Python', 'FastAPI', 'Postgres', 'Docker'],
    location: 'Lagos & Remote',
  },
  {
    id: 'pipe-2',
    roleName: 'Oil & Gas Operations Managers',
    count: 127,
    matchRate: '93% Avg Match',
    avatars: ['I.U.', 'C.E.', 'M.A.'],
    tags: ['HSE Compliance', 'Field Operations', 'Logistics', 'Contract Mgmt'],
    location: 'Port Harcourt & Lagos',
  },
  {
    id: 'pipe-3',
    roleName: 'Retail & FMCG Regional Sales Leads',
    count: 204,
    matchRate: '95% Avg Match',
    avatars: ['T.A.', 'B.K.', 'S.O.', 'R.M.'],
    tags: ['Trade Marketing', 'Distribution', 'Team Leadership', 'Forecasting'],
    location: 'Accra & Remote',
  },
  {
    id: 'pipe-4',
    roleName: 'Healthcare Facility Administrators',
    count: 96,
    matchRate: '94% Avg Match',
    avatars: ['N.O.', 'D.A.', 'F.K.'],
    tags: ['Clinical Ops', 'Regulatory Compliance', 'Staffing', 'Budgeting'],
    location: 'Nairobi & Remote',
  },
  {
    id: 'pipe-5',
    roleName: 'Banking & Finance Operations Leads',
    count: 168,
    matchRate: '96% Avg Match',
    avatars: ['E.N.', 'C.I.', 'A.M.'],
    tags: ['Risk & Compliance', 'Reconciliation', 'Treasury', 'Process Automation'],
    location: 'Johannesburg & Remote',
  },
]

export default function PipelineShowcase({ registerHref = '/register?role=employer' }) {
  const ref = useRef(null)
  const isInView = useInView(ref, { once: true, amount: 0.2 })

  return (
    <section ref={ref} className="space-y-6 py-8">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-white/10 pb-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="px-2.5 py-0.5 rounded-full bg-brand-amber/20 text-brand-amber text-[10px] font-bold uppercase tracking-wider border border-brand-amber/40">
              Active Pipelines
            </span>
            <h3 className="text-xl font-bold text-white tracking-tight">
              Pre-Vetted Talent Pools
            </h3>
          </div>
          <p className="text-xs text-slate-300 mt-1">
            Pre-clustered candidate pools continuously maintained by Elevare matching engine
          </p>
        </div>
      </div>

      <div className="relative">
        <div className="flex items-stretch gap-5 overflow-x-auto pb-4 pt-1 snap-x scrollbar-thin scrollbar-thumb-white/10 scrollbar-track-transparent">
          {PIPELINES.map((pipe, idx) => (
            <motion.div
              key={pipe.id}
              initial={{ opacity: 0, x: 24 }}
              animate={{ opacity: isInView ? 1 : 0, x: isInView ? 0 : 24 }}
              transition={{ duration: 0.4, delay: idx * 0.1 }}
              whileHover={{ y: -3 }}
              className="flex-shrink-0 w-80 snap-start rounded-xl bg-slate-900/90 border border-white/10 p-5 flex flex-col justify-between shadow-lg hover:border-brand-amber/40 transition-all duration-200 group"
            >
              <div>
                <div className="flex items-start justify-between gap-2 mb-3">
                  <div>
                    <h4 className="font-bold text-white text-base group-hover:text-brand-amber transition-colors">
                      {pipe.roleName}
                    </h4>
                    <p className="text-xs text-slate-400 mt-0.5">{pipe.location}</p>
                  </div>
                  <span className="px-2 py-0.5 rounded-md bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 text-[10px] font-bold whitespace-nowrap">
                    {pipe.matchRate}
                  </span>
                </div>

                <div className="flex items-center justify-between py-3 my-2 border-y border-white/10">
                  <div className="flex items-center gap-1.5">
                    <Users size={16} className="text-brand-blue" />
                    <span className="text-sm font-bold text-white">
                      {pipe.count}{' '}
                      <span className="text-xs font-normal text-slate-400">candidates</span>
                    </span>
                  </div>

                  <div className="flex items-center -space-x-2">
                    {pipe.avatars.map((initials, i) => (
                      <div
                        key={i}
                        className="w-7 h-7 rounded-full bg-slate-800 border border-slate-700 text-slate-200 font-bold text-[10px] flex items-center justify-center shadow-sm"
                        title="Consent-protected profile"
                      >
                        {initials}
                      </div>
                    ))}
                    <div className="w-7 h-7 rounded-full bg-brand-amber/15 border border-brand-amber/30 text-brand-amber font-bold text-[9px] flex items-center justify-center">
                      +{pipe.count - pipe.avatars.length}
                    </div>
                  </div>
                </div>

                <div className="flex flex-wrap gap-1.5 mt-3">
                  {pipe.tags.map((tag) => (
                    <span
                      key={tag}
                      className="px-2 py-0.5 rounded bg-white/5 border border-white/10 text-slate-300 text-[11px]"
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              </div>

              <Link
                to={registerHref}
                className="mt-5 w-full py-2.5 px-4 rounded-lg bg-white/5 hover:bg-brand-amber hover:text-white text-slate-200 text-xs font-bold transition-all flex items-center justify-center gap-1.5 border border-white/10"
              >
                <span>Get Started</span>
                <ArrowUpRight size={14} />
              </Link>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  )
}
