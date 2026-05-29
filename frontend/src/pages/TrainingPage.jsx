import { useState } from 'react'
import Navbar from '@/components/layout/Navbar'
import Footer from '@/components/layout/Footer'
import { ConsultationModal } from '@/components/ui/ConsultationModal'
import { FloatingWhatsApp } from '@/components/ui/FloatingWhatsApp'
import { Button } from '@/components/ui/button'
import {
  GraduationCap,
  Sparkles,
  CheckCircle2,
  Terminal,
  MessagesSquare,
  Award,
  Compass,
  ArrowRight,
} from 'lucide-react'

// ─── Training tracks coming soon ─────────────────────────────────────────────
const TRACKS = [
  {
    title: 'Tech Training & Upskilling',
    icon: Terminal,
    desc: 'Deep-dive learning pathways in software engineering, product design, and digital project frameworks.',
    topics: ['Full-stack modules', 'UI/UX sprints', 'Data analytics fundamentals'],
  },
  {
    title: 'Interview Preparation',
    icon: MessagesSquare,
    desc: 'Interactive interview bootcamps, technical code review coaching, and soft skills training blocks.',
    topics: ['Live mock panels', 'Salary negotiations', 'Behavioral grading models'],
  },
  {
    title: 'Industry Certifications',
    icon: Award,
    desc: 'Preparation cohorts for globally recognized HR certifications (CIPM, PHRi, SHRM, PMP).',
    topics: ['Custom mock exams', 'Professional credit packs', 'Weekly mentor meetups'],
  },
  {
    title: 'Executive Career Coaching',
    icon: Compass,
    desc: '1-on-1 strategic consulting with Senior HR Directors to map out transition pipelines for leaders.',
    topics: ['C-suite roadmaps', 'Brand elevation audits', 'Board position networks'],
  },
]

export default function TrainingPage() {
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [emailInput, setEmailInput] = useState('')
  const [joined, setJoined] = useState(false)

  const openModal = () => setIsModalOpen(true)
  const closeModal = () => setIsModalOpen(false)

  const handleWaitlistSubmit = (e) => {
    e.preventDefault()
    if (emailInput.trim()) {
      setJoined(true)
      setEmailInput('')
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
              <Sparkles size={14} className="animate-spin" /> Learning Ecosystem Coming Soon
            </span>
            <h1 className="text-4xl sm:text-5xl font-extrabold tracking-tight leading-tight">
              Professional Training &amp; Career Development
            </h1>
            <p className="text-base sm:text-lg text-blue-100 max-w-3xl mx-auto leading-relaxed">
              Professional training and career development programs coming soon. We are building the next generation of workforce upskilling platforms to help professionals bridge industry skills gaps.
            </p>

            {/* Inline Email Waitlist */}
            <div className="max-w-md mx-auto pt-4">
              {joined ? (
                <div className="p-4 bg-white/10 backdrop-blur rounded-lg flex items-center justify-center gap-2 border border-white/15">
                  <CheckCircle2 size={18} className="text-brand-amber" />
                  <p className="text-sm font-semibold">You have joined the learning waitlist!</p>
                </div>
              ) : (
                <form onSubmit={handleWaitlistSubmit} className="flex gap-2">
                  <input
                    type="email"
                    required
                    placeholder="Enter email to get notified"
                    value={emailInput}
                    onChange={(e) => setEmailInput(e.target.value)}
                    className="flex-grow px-4 py-3 rounded bg-white text-text text-sm focus:outline-none focus:ring-2 focus:ring-brand-amber"
                  />
                  <Button type="submit" className="bg-brand-amber hover:bg-brand-amber-dark text-white font-bold text-sm px-6">
                    Notify Me
                  </Button>
                </form>
              )}
            </div>
          </div>
        </section>

        {/* 2. Future Tracks / Cards Section */}
        <section className="py-16 sm:py-24 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <h2 className="text-3xl font-extrabold text-text tracking-tight">Our Upcoming Training Tracks</h2>
            <p className="text-text-muted text-sm max-w-xl mx-auto mt-2">
              Browse through our modular training programs, engineered by top-tier HR strategists and tech leaders.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-8 max-w-5xl mx-auto">
            {TRACKS.map((track, idx) => {
              const Icon = track.icon
              return (
                <article
                  key={idx}
                  className="group relative bg-white border border-border p-8 rounded-xl shadow-sm hover:shadow-md transition-all duration-300 flex flex-col justify-between overflow-hidden"
                >
                  {/* Coming Soon absolute badge */}
                  <span className="absolute top-4 right-4 inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-brand-amber-dark/10 text-brand-amber-dark text-[10px] font-bold uppercase tracking-wider">
                    Coming Soon
                  </span>

                  <div>
                    {/* Icon */}
                    <div className="w-12 h-12 rounded-lg bg-brand-blue-light text-brand-blue flex items-center justify-center mb-6 group-hover:bg-brand-blue group-hover:text-white transition-colors duration-300">
                      <Icon size={24} strokeWidth={2} />
                    </div>

                    {/* Title */}
                    <h3 className="text-xl font-bold text-text mb-3 leading-snug group-hover:text-brand-blue transition-colors">
                      {track.title}
                    </h3>

                    {/* Description */}
                    <p className="text-text-muted text-sm leading-relaxed mb-6">
                      {track.desc}
                    </p>
                  </div>

                  {/* Highlights list */}
                  <div className="border-t border-border pt-4 mt-4">
                    <ul className="space-y-2">
                      {track.topics.map((t, i) => (
                        <li key={i} className="flex items-center gap-2 text-xs text-text font-semibold">
                          <CheckCircle2 size={13} className="text-brand-amber flex-shrink-0" />
                          <span>{t}</span>
                        </li>
                      ))}
                    </ul>
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
