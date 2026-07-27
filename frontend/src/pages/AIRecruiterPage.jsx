import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Helmet } from 'react-helmet-async'
import Navbar from '@/components/layout/Navbar'
import Footer from '@/components/layout/Footer'
import { ConsultationModal } from '@/components/ui/ConsultationModal'
import { FloatingWhatsApp } from '@/components/ui/FloatingWhatsApp'
import { Button } from '@/components/ui/button'
import { ArrowRight, Zap, Layers, BarChart3, Brain, Sparkles } from 'lucide-react'

import TalentGraphCanvas from '@/components/ai-recruiter/TalentGraphCanvas'
import AnimatedCounter from '@/components/ai-recruiter/AnimatedCounter'
import TalentGraphFlow from '@/components/ai-recruiter/TalentGraphFlow'
import PipelineShowcase from '@/components/ai-recruiter/PipelineShowcase'

const REGISTER_EMPLOYER_PATH = '/register?role=employer'

export default function AIRecruiterPage() {
  const [isModalOpen, setIsModalOpen] = useState(false)
  const openModal = () => setIsModalOpen(true)
  const closeModal = () => setIsModalOpen(false)

  return (
    <>
      <Helmet>
        <title>AI Recruiter & Talent Graph | Elevare Human Solutions</title>
        <meta
          name="description"
          content="Automated talent search, candidate discovery, and explainable match scoring for modern recruitment teams."
        />
      </Helmet>

      <Navbar onBookConsultation={openModal} />

      <main className="relative pt-16 min-h-screen bg-slate-950 text-white overflow-hidden font-sans">
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-full max-w-7xl h-[450px] bg-gradient-to-b from-brand-blue/20 to-transparent blur-[100px] pointer-events-none" />

        {/* Hero Section */}
        <section className="relative z-10 min-h-[80vh] flex flex-col justify-center py-16 px-4 sm:px-6 lg:px-8 border-b border-white/10">
          <TalentGraphCanvas />

          <div className="relative z-10 max-w-4xl mx-auto text-center space-y-6">
            <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-slate-900 border border-brand-amber/40 shadow-sm backdrop-blur-md">
              <span className="w-2 h-2 rounded-full bg-brand-amber animate-pulse" />
              <span className="text-xs font-semibold text-amber-300">
                <AnimatedCounter target={12847} prefix="" suffix=" candidates in graph" liveTick={true} />
              </span>
            </div>

            <h1 className="text-4xl sm:text-6xl font-extrabold tracking-tight leading-[1.1]">
              Automated Sourcing & <br className="hidden sm:inline" />
              <span className="text-brand-amber">
                Candidate Matching Engine
              </span>
            </h1>

            <p className="text-base sm:text-lg text-slate-300 max-w-2xl mx-auto leading-relaxed font-normal">
              Search your talent pool in plain English and get ranked, explainable matches —
              available inside your employer dashboard once you register.
            </p>

            <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-2">
              <Link to={REGISTER_EMPLOYER_PATH} className="w-full sm:w-auto">
                <Button className="w-full sm:w-auto px-7 py-3.5 bg-brand-amber hover:bg-brand-amber-dark text-white font-bold text-sm rounded-xl shadow-lg transition-all flex items-center justify-center gap-2">
                  <span>Register as Employer</span>
                  <ArrowRight size={16} />
                </Button>
              </Link>

              <Button
                onClick={openModal}
                variant="outline"
                className="w-full sm:w-auto px-7 py-3.5 bg-slate-900 hover:bg-white/10 text-white font-semibold text-sm rounded-xl border border-white/20 transition-all"
              >
                Book a Demo
              </Button>
            </div>

            <div className="pt-6 grid grid-cols-1 sm:grid-cols-3 gap-3 max-w-2xl mx-auto border-t border-white/10 text-xs text-slate-400 font-medium">
              <div className="flex items-center justify-center gap-1.5">
                <Zap size={15} className="text-brand-amber" />
                <span>Explainable Fit Scoring</span>
              </div>
              <div className="flex items-center justify-center gap-1.5">
                <Layers size={15} className="text-blue-400" />
                <span>Multi-Source Ingestion</span>
              </div>
              <div className="flex items-center justify-center gap-1.5">
                <BarChart3 size={15} className="text-violet-400" />
                <span>Pre-Vetted Role Pools</span>
              </div>
            </div>
          </div>
        </section>

        {/* What it does — informational, no interactive search here */}
        <section className="relative z-10 py-16 px-4 sm:px-6 lg:px-8 max-w-5xl mx-auto">
          <div className="text-center max-w-xl mx-auto space-y-1.5 mb-10">
            <span className="text-xs font-bold uppercase tracking-wider text-brand-amber">
              How Search Works
            </span>
            <h2 className="text-2xl sm:text-3xl font-extrabold text-white">
              Natural Language Talent Search
            </h2>
            <p className="text-sm text-slate-300 leading-relaxed">
              Describe who you're hiring for — "Senior backend engineer in Lagos with fintech
              experience" — and get ranked candidates with a plain-language explanation of why
              each one matched. It's part of your employer dashboard, not a public tool, since it
              searches real candidate profiles.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-5">
            <div className="rounded-xl bg-slate-900/90 border border-white/10 p-5">
              <div className="w-10 h-10 rounded-lg bg-brand-blue/20 flex items-center justify-center mb-3">
                <Brain size={18} className="text-brand-blue" />
              </div>
              <h3 className="font-bold text-white text-sm">Understands your query</h3>
              <p className="text-xs text-slate-400 mt-1.5 leading-relaxed">
                Type it the way you'd say it — skills, seniority, location, and industry context
                are parsed automatically, and you can always review and edit before searching.
              </p>
            </div>
            <div className="rounded-xl bg-slate-900/90 border border-white/10 p-5">
              <div className="w-10 h-10 rounded-lg bg-brand-amber/20 flex items-center justify-center mb-3">
                <Sparkles size={18} className="text-brand-amber" />
              </div>
              <h3 className="font-bold text-white text-sm">Explains every match</h3>
              <p className="text-xs text-slate-400 mt-1.5 leading-relaxed">
                Every result shows why it ranked where it did — matched skills, experience fit,
                and semantic relevance — never a black-box score.
              </p>
            </div>
            <div className="rounded-xl bg-slate-900/90 border border-white/10 p-5">
              <div className="w-10 h-10 rounded-lg bg-emerald-500/20 flex items-center justify-center mb-3">
                <Layers size={18} className="text-emerald-400" />
              </div>
              <h3 className="font-bold text-white text-sm">Spans your whole pipeline</h3>
              <p className="text-xs text-slate-400 mt-1.5 leading-relaxed">
                Searches both candidates who registered directly and CVs your team sourced
                yourself — one search, your whole talent pool.
              </p>
            </div>
          </div>
        </section>

        {/* How It Works */}
        <div className="border-t border-white/10 bg-slate-900/50">
          <TalentGraphFlow />
        </div>

        {/* Pipeline Showcase */}
        <section className="relative z-10 py-16 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto border-t border-white/10">
          <PipelineShowcase registerHref={REGISTER_EMPLOYER_PATH} />
        </section>

        {/* Stats Band */}
        <section className="relative z-10 py-16 bg-slate-900 border-y border-white/10">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-6 text-center">
              <div className="space-y-1 p-5 rounded-xl bg-white/5 border border-white/10">
                <p className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight">
                  <AnimatedCounter target={12847} suffix="+" />
                </p>
                <p className="text-xs font-bold text-brand-amber uppercase tracking-wider">
                  Candidates in Graph
                </p>
                <p className="text-[11px] text-slate-400">Continuously updated</p>
              </div>

              <div className="space-y-1 p-5 rounded-xl bg-white/5 border border-white/10">
                <p className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight">
                  <AnimatedCounter target={45} prefix="< " suffix="s" />
                </p>
                <p className="text-xs font-bold text-emerald-400 uppercase tracking-wider">
                  Avg Sourcing Time
                </p>
                <p className="text-[11px] text-slate-400">Real-time candidate search</p>
              </div>

              <div className="space-y-1 p-5 rounded-xl bg-white/5 border border-white/10">
                <p className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight">
                  <AnimatedCounter target={99.4} decimals={1} suffix="%" />
                </p>
                <p className="text-xs font-bold text-cyan-400 uppercase tracking-wider">
                  Fit Analysis Clarity
                </p>
                <p className="text-[11px] text-slate-400">Transparent match reasoning</p>
              </div>

              <div className="space-y-1 p-5 rounded-xl bg-white/5 border border-white/10">
                <p className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight">
                  <AnimatedCounter target={94.8} decimals={1} suffix="%" />
                </p>
                <p className="text-xs font-bold text-violet-400 uppercase tracking-wider">
                  Skill Overlap Match
                </p>
                <p className="text-[11px] text-slate-400">Verified taxonomy overlap</p>
              </div>
            </div>
          </div>
        </section>
      </main>

      <Footer onBookConsultation={openModal} />
      <ConsultationModal isOpen={isModalOpen} onClose={closeModal} />
      <FloatingWhatsApp />
    </>
  )
}
