import { useState, useEffect } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { Helmet } from 'react-helmet-async'
import Navbar from '@/components/layout/Navbar'
import Footer from '@/components/layout/Footer'
import { FloatingWhatsApp } from '@/components/ui/FloatingWhatsApp'
import { Button } from '@/components/ui/button'
import {
  Briefcase,
  Users,
  FileText,
  CheckCircle2,
  ChevronDown,
  UserPlus,
  Upload,
  Search,
  BarChart2,
  ClipboardList,
  Star,
  Handshake,
} from 'lucide-react'

// ─── Data ─────────────────────────────────────────────────────────────────────

const EMPLOYER_STEPS = [
  {
    number: '01',
    icon: Briefcase,
    title: 'Post a Role',
    desc: 'Create a job listing with your requirements, salary range, and ideal candidate profile. Takes less than 5 minutes.',
  },
  {
    number: '02',
    icon: Users,
    title: 'We Source & Vet',
    desc: 'Our team and AI-powered pipeline surfaces qualified candidates from our network. Every applicant is screened before you see them.',
  },
  {
    number: '03',
    icon: ClipboardList,
    title: 'You Interview Shortlisted Candidates',
    desc: 'Receive a curated shortlist of the best-fit candidates. Review profiles, CVs, and match scores — then schedule interviews.',
  },
  {
    number: '04',
    icon: Handshake,
    title: 'Hire',
    desc: 'Select your hire and let us handle the offer coordination. We stay engaged post-placement to ensure a smooth transition.',
  },
]

const CANDIDATE_STEPS = [
  {
    number: '01',
    icon: UserPlus,
    title: 'Create Your Profile',
    desc: 'Sign up and build your professional profile. Add your skills, experience, and career goals — it only takes a few minutes.',
  },
  {
    number: '02',
    icon: Upload,
    title: 'Upload Your CV',
    desc: 'Upload your CV and let our system parse your experience. You can also be discovered by employers actively searching our talent pool.',
  },
  {
    number: '03',
    icon: Search,
    title: 'Apply to Roles',
    desc: 'Browse active job listings and apply with one click. Your profile and CV are sent directly to the hiring employer.',
  },
  {
    number: '04',
    icon: BarChart2,
    title: 'Track Your Applications',
    desc: 'Monitor every application from your dashboard. Get notified when your status changes — from reviewing to shortlisted to hired.',
  },
]

const EMPLOYER_FAQS = [
  {
    q: 'How quickly will I see candidates after posting a job?',
    a: 'Most roles receive an initial shortlist within 3–5 business days, depending on the seniority and availability of candidates in the market.',
  },
  {
    q: 'Do I need to pay to post a job?',
    a: 'The Starter plan allows a limited number of free postings. Professional and Enterprise plans unlock unlimited postings and priority support. See our Pricing page for details.',
  },
  {
    q: 'Can I search for candidates directly without posting a job?',
    a: 'Yes. Professional and Enterprise plan employers have access to our candidate database and can run searches by skills, experience, and location.',
  },
  {
    q: 'What if the hired candidate leaves within the first few months?',
    a: 'Enterprise plans include a placement guarantee. Contact our team to discuss the terms that apply to your account.',
  },
  {
    q: 'Is the platform suitable for high-volume hiring?',
    a: 'Yes. Our Enterprise plan is designed for organisations running multiple concurrent searches with a dedicated account manager.',
  },
]

const CANDIDATE_FAQS = [
  {
    q: 'Is it free to create a candidate profile?',
    a: 'Completely free. Candidates always have full access to job listings, applications, and their dashboard at no cost.',
  },
  {
    q: 'How do employers find me?',
    a: 'Employers on Professional and Enterprise plans can search the candidate database. Setting your profile to visible and keeping it complete significantly increases your chances of being found.',
  },
  {
    q: 'What file formats are accepted for CV uploads?',
    a: 'We accept PDF and Word documents (.docx). PDF is recommended for consistent formatting.',
  },
  {
    q: 'Will I be notified when my application status changes?',
    a: 'Yes. You will receive an email notification every time an employer updates your application status.',
  },
  {
    q: 'Can I apply to multiple jobs at once?',
    a: 'Yes, there is no limit on the number of active applications you can have at any time.',
  },
  {
    q: 'How do I know if a job is still accepting applications?',
    a: 'All listings on the job board are active and accepting applications. Closed or expired roles are removed automatically.',
  },
]

// ─── Sub-components ────────────────────────────────────────────────────────────

function StepCard({ step, index, total }) {
  const Icon = step.icon
  const isLast = index === total - 1
  return (
    <div className="relative flex gap-5">
      {/* Connector line */}
      {!isLast && (
        <div className="absolute left-6 top-14 bottom-0 w-px bg-border" aria-hidden="true" />
      )}
      {/* Icon circle */}
      <div className="relative flex-shrink-0 w-12 h-12 rounded-full bg-brand-blue text-white flex items-center justify-center shadow-md z-10">
        <Icon size={20} strokeWidth={2} />
      </div>
      {/* Content */}
      <div className="pb-10">
        <span className="text-xs font-bold text-brand-amber uppercase tracking-widest">{step.number}</span>
        <h3 className="text-base font-extrabold text-text mt-0.5 mb-1">{step.title}</h3>
        <p className="text-sm text-text-muted leading-relaxed">{step.desc}</p>
      </div>
    </div>
  )
}

function FaqItem({ q, a }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="border-b border-border">
      <button
        className="flex items-center justify-between w-full py-4 text-left text-sm font-semibold text-text hover:text-brand-blue transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-blue rounded"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
      >
        {q}
        <ChevronDown
          size={16}
          className={`flex-shrink-0 ml-4 transition-transform duration-200 ${open ? 'rotate-180' : ''}`}
        />
      </button>
      {open && (
        <p className="pb-4 text-sm text-text-muted leading-relaxed">{a}</p>
      )}
    </div>
  )
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function HowItWorksPage() {
  const [audience, setAudience] = useState('employers')
  const location = useLocation()

  // Drive tab from URL hash — /how-it-works#candidates or #employers
  useEffect(() => {
    if (location.hash === '#candidates') setAudience('candidates')
    else if (location.hash === '#employers') setAudience('employers')
  }, [location.hash])

  return (
    <>
      <Helmet>
        <title>How It Works | Elevare Human Solutions</title>
        <meta name="description" content="See how Elevare works for employers and candidates — from posting a role to getting hired, step by step." />
        <meta property="og:title" content="How It Works | Elevare Human Solutions" />
        <meta property="og:description" content="See how Elevare works for employers and candidates — from posting a role to getting hired, step by step." />
        <meta property="og:url" content="https://elevare.com.ng/how-it-works" />
        <meta property="og:type" content="website" />
        <link rel="canonical" href="https://elevare.com.ng/how-it-works" />
      </Helmet>
      <Navbar />

      <main className="pt-16 bg-[#fafbfc]">

        {/* ── Hero ── */}
        <section className="relative overflow-hidden py-24 lg:py-32 text-white">
          {/* Background image from new_images_hero */}
          <div 
            className="absolute inset-0 bg-cover bg-center bg-no-repeat transition-transform duration-1000 scale-105"
            style={{ 
              backgroundImage: "url('/hero-images/img9.jpg')",
            }}
          />
          {/* Rich Overlay */}
          <div className="absolute inset-0 bg-gradient-to-r from-brand-blue-dark/95 via-brand-blue/85 to-transparent backdrop-blur-[2px]" />
          
          <div className="relative z-10 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="max-w-3xl space-y-6">
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded bg-brand-amber/20 text-brand-amber text-xs font-bold uppercase tracking-wider border border-brand-amber/35">
                How It Works
              </span>
              <h1 className="text-4xl sm:text-5xl lg:text-7xl font-extrabold tracking-tight leading-tight" style={{ fontFamily: "'Lobster Two', cursive" }}>
                Simple. Structured. Effective.
              </h1>
              <p className="text-lg lg:text-xl text-blue-100/90 leading-relaxed max-w-2xl">
                Whether you're hiring or job hunting, Elevare makes the process straightforward from start to finish.
              </p>
            </div>
          </div>
          {/* Curved section divider at bottom */}
          <div className="curve-divider-bottom" style={{ height: '3vw' }}>
            <svg viewBox="0 0 1440 120" fill="none" xmlns="http://www.w3.org/2000/svg" className="w-full h-full">
              <path d="M0,64L120,80C240,96,480,128,720,128C960,128,1200,96,1320,80L1440,64L1440,120L1320,120C1200,120,960,120,720,120C480,120,240,120,120,120L0,120Z" fill="#fafbfc" />
            </svg>
          </div>
        </section>

        {/* ── Tab switcher ── */}
        <section className="py-16 sm:py-24 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          {/* Tabs */}
          <div className="flex justify-center mb-14">
            <div className="inline-flex bg-surface-muted rounded-full p-1 gap-1" role="tablist">
              {[
                { id: 'employers', label: 'For Employers' },
                { id: 'candidates', label: 'For Candidates' },
              ].map((tab) => (
                <button
                  key={tab.id}
                  role="tab"
                  aria-selected={audience === tab.id}
                  id={`tab-${tab.id}`}
                  aria-controls={`panel-${tab.id}`}
                  onClick={() => setAudience(tab.id)}
                  className={`px-6 py-2.5 rounded-full text-sm font-bold transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-blue ${
                    audience === tab.id
                      ? 'bg-brand-blue text-white shadow-sm'
                      : 'text-text-muted hover:text-text'
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>
          </div>

          {/* Step panels */}
          <div id={`panel-employers`} role="tabpanel" aria-labelledby="tab-employers" hidden={audience !== 'employers'}>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-x-20 gap-y-0 max-w-4xl mx-auto">
              {EMPLOYER_STEPS.map((step, i) => (
                <StepCard key={step.number} step={step} index={i} total={EMPLOYER_STEPS.length} />
              ))}
            </div>
            <div className="text-center mt-4">
              <Link to="/register?role=employer">
                <Button className="bg-brand-amber hover:bg-brand-amber-dark text-white border-0 px-8 py-3 text-sm font-bold uppercase tracking-wider rounded-full">
                  Post a Job
                </Button>
              </Link>
            </div>
          </div>

          <div id={`panel-candidates`} role="tabpanel" aria-labelledby="tab-candidates" hidden={audience !== 'candidates'}>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-x-20 gap-y-0 max-w-4xl mx-auto">
              {CANDIDATE_STEPS.map((step, i) => (
                <StepCard key={step.number} step={step} index={i} total={CANDIDATE_STEPS.length} />
              ))}
            </div>
            <div className="text-center mt-4">
              <Link to="/register?role=candidate">
                <Button className="bg-brand-blue hover:bg-brand-blue/90 text-white border-0 px-8 py-3 text-sm font-bold uppercase tracking-wider rounded-full">
                  Create Your Profile
                </Button>
              </Link>
            </div>
          </div>
        </section>

        {/* ── FAQ ── */}
        <section className="bg-white border-t border-border py-16 sm:py-24">
          <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="text-center mb-12">
              <p className="text-brand-amber font-bold text-xs tracking-widest uppercase mb-2">FAQ</p>
              <h2 className="text-3xl sm:text-4xl font-extrabold text-text tracking-tight">
                {audience === 'employers' ? 'Employer Questions' : 'Candidate Questions'}
              </h2>
            </div>
            <div>
              {(audience === 'employers' ? EMPLOYER_FAQS : CANDIDATE_FAQS).map((item) => (
                <FaqItem key={item.q} q={item.q} a={item.a} />
              ))}
            </div>
          </div>
        </section>

      </main>

      <Footer />
      <FloatingWhatsApp />
    </>
  )
}
