import { useState } from 'react'
import Navbar from '@/components/layout/Navbar'
import Footer from '@/components/layout/Footer'
import { ConsultationModal } from '@/components/ui/ConsultationModal'
import { FloatingWhatsApp } from '@/components/ui/FloatingWhatsApp'
import { Button } from '@/components/ui/button'
import {
  Cpu,
  Sparkles,
  CheckCircle2,
  Users,
  DollarSign,
  Clock,
  Compass,
  Workflow,
  Lock,
} from 'lucide-react'

// ─── Future tools coming soon ────────────────────────────────────────────────
const TOOLS = [
  {
    title: 'HR Management Portal',
    icon: Users,
    desc: 'Centralized directory to store contracts, track performance reviews, design handbook sign-offs, and handle personnel files.',
    badge: 'Phase 3',
  },
  {
    title: 'Automated Payroll Engine',
    icon: DollarSign,
    desc: 'Instant calculations for statutory PAYE, NSITF, pension, and direct disbursal payouts with absolute compliance.',
    badge: 'Phase 3',
  },
  {
    title: 'Attendance & Clock-In Tools',
    icon: Clock,
    desc: 'Geo-fenced mobile checking, shift coordination logs, and leave tracking models for remote and on-site staff.',
    badge: 'Phase 3',
  },
  {
    title: 'Employee Tracking & KPIs',
    icon: Compass,
    desc: 'Goal alignment modules to track team objectives (OKRs), generate productivity statistics, and reward top-performers.',
    badge: 'Phase 4',
  },
  {
    title: 'Recruitment Workflow System',
    icon: Workflow,
    desc: 'Fully configured Applicant Tracking System (ATS) to manage interview pipelines, invite recruiters, and draft offers.',
    badge: 'Phase 4',
  },
]

export default function WorkforceToolsPage() {
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [emailValue, setEmailValue] = useState('')
  const [joined, setJoined] = useState(false)

  const openModal = () => setIsModalOpen(true)
  const closeModal = () => setIsModalOpen(false)

  const handleWaitlistSubmit = (e) => {
    e.preventDefault()
    if (emailValue.trim()) {
      setJoined(true)
      setEmailValue('')
    }
  }

  return (
    <>
      <Navbar onBookConsultation={openModal} />

      <main className="pt-16 bg-[#fafbfc] min-h-screen">
        
        {/* 1. Header Section */}
        <section className="relative overflow-hidden bg-brand-blue py-16 lg:py-20 text-white">
          <div
            className="absolute inset-0 opacity-10 pointer-events-none"
            style={{
              backgroundImage: `
                linear-gradient(rgba(255,255,255,0.08) 1px, transparent 1px),
                linear-gradient(90deg, rgba(255,255,255,0.08) 1px, transparent 1px)
              `,
              backgroundSize: '40px 40px',
            }}
          />
          <div className="absolute inset-0 bg-gradient-to-tr from-brand-blue via-brand-blue-dark to-brand-blue-light opacity-80" />

          <div className="relative z-10 max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 text-center space-y-6">
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded bg-brand-amber/20 text-brand-amber text-xs font-bold uppercase tracking-wider">
              <Sparkles size={14} className="animate-spin" /> SaaS Tools Platform Coming Soon
            </span>
            <h1 className="text-4xl sm:text-5xl font-extrabold tracking-tight leading-tight">
              Workforce Management Tools
            </h1>
            <p className="text-base sm:text-lg text-blue-100 max-w-3xl mx-auto leading-relaxed">
              Workforce management tools coming soon. We are deploying a centralized suite of SaaS modules to manage your employee lifecycle, compliance pipelines, and payroll disbursals.
            </p>

            {/* Inline Email Waitlist */}
            <div className="max-w-md mx-auto pt-4">
              {joined ? (
                <div className="p-4 bg-white/10 backdrop-blur rounded-lg flex items-center justify-center gap-2 border border-white/15">
                  <CheckCircle2 size={18} className="text-brand-amber" />
                  <p className="text-sm font-semibold">You have joined the SaaS tools waitlist!</p>
                </div>
              ) : (
                <form onSubmit={handleWaitlistSubmit} className="flex gap-2">
                  <input
                    type="email"
                    required
                    placeholder="Enter business email for early beta"
                    value={emailValue}
                    onChange={(e) => setEmailValue(e.target.value)}
                    className="flex-grow px-4 py-3 rounded bg-white text-text text-sm focus:outline-none focus:ring-2 focus:ring-brand-amber"
                  />
                  <Button type="submit" className="bg-brand-amber hover:bg-brand-amber-dark text-white font-bold text-sm px-6">
                    Request Access
                  </Button>
                </form>
              )}
            </div>
          </div>
        </section>

        {/* 2. Future Tools / Cards Section */}
        <section className="py-16 sm:py-24 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <h2 className="text-3xl font-extrabold text-text tracking-tight">Interactive Workforce Suite</h2>
            <p className="text-text-muted text-sm max-w-xl mx-auto mt-2">
              SaaS dashboard modules designed to streamline operations and ensure complete statutory regulatory compliance.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8 max-w-6xl mx-auto">
            {TOOLS.map((tool, idx) => {
              const Icon = tool.icon
              return (
                <article
                  key={idx}
                  className="group relative bg-white border border-border p-6 rounded-xl shadow-sm hover:shadow-md transition-all duration-300 flex flex-col justify-between overflow-hidden"
                >
                  {/* Coming Soon absolute badge */}
                  <span className="absolute top-4 right-4 inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-brand-amber-dark/10 text-brand-amber-dark text-[10px] font-bold uppercase tracking-wider">
                    {tool.badge} — Coming Soon
                  </span>

                  <div>
                    {/* Icon */}
                    <div className="w-12 h-12 rounded-lg bg-brand-blue-light text-brand-blue flex items-center justify-center mb-6 group-hover:bg-brand-blue group-hover:text-white transition-colors duration-300">
                      <Icon size={24} strokeWidth={2} />
                    </div>

                    {/* Title */}
                    <h3 className="text-lg font-bold text-text mb-3 leading-snug group-hover:text-brand-blue transition-colors">
                      {tool.title}
                    </h3>

                    {/* Description */}
                    <p className="text-text-muted text-xs sm:text-sm leading-relaxed mb-6">
                      {tool.desc}
                    </p>
                  </div>

                  {/* Non-functional mock action */}
                  <div className="border-t border-border pt-4 mt-4 flex items-center justify-between text-xs text-text-muted">
                    <span className="flex items-center gap-1 font-bold text-brand-amber uppercase tracking-wider text-[10px]">
                      <Lock size={12} /> Closed Beta
                    </span>
                    <button disabled className="text-slate-400 font-semibold cursor-not-allowed">
                      Unlock Module →
                    </button>
                  </div>
                </article>
              )
            })}
          </div>
        </section>

      </main>

      <Footer onBookConsultation={openModal} />
      <ConsultationModal isOpen={isModalOpen} onClose={closeModal} />
      <FloatingWhatsApp />
    </>
  )
}
