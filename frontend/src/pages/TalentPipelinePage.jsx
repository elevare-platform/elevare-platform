import { useState } from 'react'
import Navbar from '@/components/layout/Navbar'
import Footer from '@/components/layout/Footer'
import { ConsultationModal } from '@/components/ui/ConsultationModal'
import { FloatingWhatsApp } from '@/components/ui/FloatingWhatsApp'
import { Button } from '@/components/ui/button'
import {
  Sparkles,
  Zap,
  Users,
  Search,
  Lock,
  ChevronRight,
  TrendingUp,
  Sliders,
  CheckCircle2,
} from 'lucide-react'

export default function TalentPipelinePage() {
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [waitlistEmail, setWaitlistEmail] = useState('')
  const [joined, setJoined] = useState(false)

  const openModal = () => setIsModalOpen(true)
  const closeModal = () => setIsModalOpen(false)

  const handleJoinWaitlist = (e) => {
    e.preventDefault()
    if (waitlistEmail.trim()) {
      setJoined(true)
      setWaitlistEmail('')
    }
  }

  return (
    <>
      <Navbar onBookConsultation={openModal} />

      <main className="pt-16 min-h-screen bg-gradient-to-b from-slate-900 via-brand-blue to-slate-950 text-white flex flex-col justify-between">
        
        {/* Main Content */}
        <div className="flex-grow flex items-center py-16 sm:py-24">
          <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 grid grid-cols-1 lg:grid-cols-12 gap-12 lg:gap-16 items-center">
            
            {/* Left Column: Heading, Waitlist, Tagline */}
            <div className="lg:col-span-6 space-y-6 text-center lg:text-left">
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded bg-brand-amber/20 text-brand-amber text-xs font-bold uppercase tracking-wider">
                <Sparkles size={14} className="animate-spin" /> Coming Soon to Phase 3
              </span>
              <h1 className="text-4xl sm:text-5xl font-extrabold tracking-tight leading-tight">
                AI-Powered <span className="text-brand-amber">Talent Pipeline</span>
              </h1>
              <p className="text-lg text-blue-100 max-w-xl mx-auto lg:mx-0 leading-relaxed">
                Unlock automated candidate discovery, real-time employer matching, and predictive workforce analytics built to cut time-to-hire by 60%.
              </p>

              {/* Waitlist submission form */}
              <div className="max-w-md mx-auto lg:mx-0">
                {joined ? (
                  <div className="p-4 bg-green-500/20 border border-green-500/40 rounded-lg flex items-center gap-3">
                    <CheckCircle2 size={20} className="text-green-400 flex-shrink-0" />
                    <p className="text-sm font-semibold text-white">
                      You are on the list! We will contact you soon.
                    </p>
                  </div>
                ) : (
                  <form onSubmit={handleJoinWaitlist} className="flex flex-col sm:flex-row gap-2.5">
                    <input
                      type="email"
                      required
                      placeholder="Enter work email address"
                      value={waitlistEmail}
                      onChange={(e) => setWaitlistEmail(e.target.value)}
                      className="flex-grow px-4 py-3 bg-white/10 backdrop-blur border border-white/10 rounded focus:border-brand-amber text-sm text-white placeholder-slate-400 focus:outline-none"
                    />
                    <Button
                      type="submit"
                      className="px-6 py-3 font-bold text-sm bg-brand-amber hover:bg-brand-amber-dark text-white rounded shadow-md transition-all hover:scale-[1.02]"
                    >
                      Join Waitlist
                    </Button>
                  </form>
                )}
                <p className="text-xs text-blue-200 mt-2">
                  Be the first to access early matching pools and pipeline slots.
                </p>
              </div>

              {/* Scope/Features grid */}
              <div className="grid grid-cols-2 gap-4 border-t border-white/10 pt-6">
                <div>
                  <p className="text-xl font-extrabold text-brand-amber">Coming Soon</p>
                  <p className="text-xs text-blue-200 uppercase mt-0.5 font-semibold">AI Sourcing Pipeline</p>
                </div>
                <div>
                  <p className="text-xl font-extrabold text-brand-amber">Phase 3</p>
                  <p className="text-xs text-blue-200 uppercase mt-0.5 font-semibold">Automated Vetting</p>
                </div>
              </div>
            </div>

            {/* Right Column: Beautiful SaaS / Dashboard Simulation card */}
            <div className="lg:col-span-6 flex justify-center">
              <div className="relative w-full max-w-lg">
                
                {/* Visual Glassmorphism Dashboard Simulation */}
                <div className="absolute -inset-2 bg-gradient-to-tr from-brand-amber to-brand-blue rounded-3xl blur opacity-30 animate-pulse"></div>
                <div className="relative bg-slate-950/80 backdrop-blur-xl border border-white/15 p-6 rounded-2xl shadow-2xl">
                  
                  {/* Dashboard Mock Header */}
                  <div className="flex items-center justify-between border-b border-white/10 pb-4 mb-5">
                    <div className="flex items-center gap-2">
                      <div className="w-3 h-3 rounded-full bg-red-500"></div>
                      <div className="w-3 h-3 rounded-full bg-yellow-500"></div>
                      <div className="w-3 h-3 rounded-full bg-green-500"></div>
                    </div>
                    <span className="text-xs text-slate-400 font-mono tracking-wider">elevare_ai_pipeline_v1.0</span>
                  </div>

                  {/* Vetted Candidate List Mockups (Blurred out style) */}
                  <div className="space-y-4 relative">
                    
                    {/* Mock candidate card 1 */}
                    <div className="flex items-center gap-4 p-3 bg-white/5 rounded-lg border border-white/5 opacity-80 filter blur-[0.7px]">
                      <div className="w-10 h-10 rounded-full bg-brand-blue-light text-brand-blue flex items-center justify-center font-bold">
                        JD
                      </div>
                      <div className="flex-grow">
                        <div className="h-3 w-28 bg-slate-700 rounded mb-1.5"></div>
                        <div className="h-2.5 w-16 bg-slate-800 rounded"></div>
                      </div>
                      <div className="h-5 w-14 bg-green-500/10 text-green-400 rounded-full flex items-center justify-center text-[10px] font-bold">
                        97% Match
                      </div>
                    </div>

                    {/* Mock candidate card 2 */}
                    <div className="flex items-center gap-4 p-3 bg-white/5 rounded-lg border border-white/5 opacity-40 filter blur-[1.2px]">
                      <div className="w-10 h-10 rounded-full bg-brand-blue-light text-brand-blue flex items-center justify-center font-bold">
                        AM
                      </div>
                      <div className="flex-grow">
                        <div className="h-3 w-36 bg-slate-700 rounded mb-1.5"></div>
                        <div className="h-2.5 w-20 bg-slate-800 rounded"></div>
                      </div>
                      <div className="h-5 w-14 bg-green-500/10 text-green-400 rounded-full flex items-center justify-center text-[10px] font-bold">
                        92% Match
                      </div>
                    </div>

                    {/* Screen lock Overlay (Req 1) */}
                    <div className="absolute inset-0 bg-slate-950/40 backdrop-blur-sm flex flex-col items-center justify-center text-center p-6 rounded-lg">
                      <div className="w-12 h-12 rounded-full bg-brand-amber/20 text-brand-amber flex items-center justify-center shadow-lg border border-brand-amber/30 mb-3 animate-bounce">
                        <Lock size={20} />
                      </div>
                      <h3 className="font-extrabold text-sm text-white">AI-Powered Matching Engine</h3>
                      <p className="text-slate-300 text-xs mt-1 max-w-xs leading-relaxed">
                        AI-powered candidate discovery and smart employer matching coming soon. Join waitlist above to unlock early access.
                      </p>
                    </div>

                  </div>
                </div>

              </div>
            </div>

          </div>
        </div>

      </main>

      <Footer onBookConsultation={openModal} />
      <ConsultationModal isOpen={isModalOpen} onClose={closeModal} />
      <FloatingWhatsApp />
    </>
  )
}
