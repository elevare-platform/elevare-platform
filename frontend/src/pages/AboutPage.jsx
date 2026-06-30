import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Helmet } from 'react-helmet-async'
import Navbar from '@/components/layout/Navbar'
import Footer from '@/components/layout/Footer'
import { ConsultationModal } from '@/components/ui/ConsultationModal'
import { FloatingWhatsApp } from '@/components/ui/FloatingWhatsApp'
import { Button } from '@/components/ui/button'
import founderImg from '@/assets/IMG_9606.PNG'

import {
  Users,
  Search,
  CheckCircle2,
  TrendingUp,
  Award,
  Layers,
  ArrowRight,
  ShieldCheck,
  MessageSquare,
  Sparkles,
  Building2,
  Briefcase,
  Hotel,
  Fuel,
  ShoppingBag,
  Laptop,
  Rocket,
  Factory,
  Home,
  Activity,
} from 'lucide-react'

// ─── Branded Social Media Custom SVGs (Perfect branding representation) ───────
function WhatsAppIcon({ size = 20 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor">
      <path d="M.057 24l1.687-6.163c-1.041-1.804-1.588-3.849-1.587-5.946C.06 5.348 5.397.01 12.008.01c3.202.001 6.212 1.246 8.477 3.514 2.266 2.268 3.507 5.28 3.505 8.484-.004 6.657-5.34 11.997-11.953 11.997-2.005-.001-3.973-.502-5.724-1.457L0 24zm6.59-4.846c1.6.95 3.188 1.449 4.825 1.451 5.436 0 9.859-4.42 9.863-9.864.002-2.637-1.023-5.116-2.887-6.98C16.484 1.897 14.016.865 11.39.865c-5.44 0-9.866 4.42-9.87 9.865-.001 1.639.497 3.237 1.445 4.825l-.999 3.648 3.74-.981zm12.355-6.666c-.302-.151-1.787-.882-2.05-.978-.264-.096-.456-.145-.648.145-.192.29-.744.978-.912 1.17-.168.193-.336.217-.638.066-1.554-.78-2.68-1.34-3.743-3.167-.282-.486.282-.451.808-1.503.088-.175.044-.329-.022-.48-.066-.15-.648-1.562-.888-2.141-.234-.564-.473-.488-.648-.497-.168-.008-.36-.01-.552-.01-.192 0-.504.072-.768.36-.264.29-1.008.986-1.008 2.404 0 1.417 1.032 2.79 1.176 2.985.144.195 2.032 3.102 4.922 4.35.688.297 1.224.474 1.644.607.69.22 1.32.19 1.815.115.552-.083 1.787-.73 2.039-1.436.252-.706.252-1.314.176-1.436-.076-.12-.276-.192-.578-.342z"/>
    </svg>
  )
}

function InstagramIcon({ size = 20 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor">
      <path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zM12 0C8.741 0 8.333.014 7.053.072 2.695.272.273 2.69.073 7.051.014 8.333 0 8.741 0 12c0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98 1.281.058 1.689.072 4.948.072 3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98C15.668.014 15.259 0 12 0zm0 5.838a6.162 6.162 0 100 12.324 6.162 6.162 0 000-12.324zM12 16a4 4 0 110-8 4 4 0 010 8zm6.406-11.845a1.44 1.44 0 100 2.881 1.44 1.44 0 000-2.881z"/>
    </svg>
  )
}

function LinkedInIcon({ size = 20 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor">
      <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.3 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/>
    </svg>
  )
}

function TikTokIcon({ size = 20 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor">
      <path d="M12.525.02c1.31-.02 2.61-.01 3.91-.02.08 1.53.63 3.09 1.75 4.17 1.12 1.11 2.7 1.62 4.24 1.79v4.03c-1.44-.06-2.89-.52-4.06-1.39-.77-.57-1.39-1.33-1.89-2.17v7.41c.08 2.08-.62 4.21-2.16 5.65-1.57 1.53-3.88 2.23-6.03 1.84-2.14-.37-4.1-1.8-5.02-3.79-.98-2.08-.85-4.66.39-6.61 1.17-1.9 3.25-3.05 5.5-3.09v4.03c-1.34.02-2.73.68-3.4 1.82-.69 1.1-.6 2.62.24 3.59.81.99 2.18 1.34 3.42.92 1.16-.36 1.95-1.43 1.97-2.65V.02z"/>
    </svg>
  )
}

// ─── Industries We Serve Data ────────────────────────────────────────────────
const INDUSTRIES = [
  { name: 'Corporate Organizations', icon: Building2 },
  { name: 'Professional Services', icon: Briefcase },
  { name: 'Hospitality & Lifestyle Brands', icon: Hotel },
  { name: 'Oil & Gas Companies', icon: Fuel },
  { name: 'Retail & Consumer Businesses', icon: ShoppingBag },
  { name: 'Technology-Driven Companies', icon: Laptop },
  { name: 'Startups & SMEs', icon: Rocket },
  { name: 'Manufacturing & Industrial Businesses', icon: Factory },
  { name: 'Real Estate & Construction Firms', icon: Home },
  { name: 'Healthcare & Service-Based', icon: Activity },
]

// ─── Why Choose Elevare Data ──────────────────────────────────────────────────
const WHY_CHOOSE_US_DATA = [
  {
    title: 'Professional Recruitment Process',
    desc: 'Structured, methodological searches from rigorous competency mapping to executive salary benchmarking.',
    icon: Search,
  },
  {
    title: 'Access to Qualified Talent',
    desc: 'Exclusive, pre-vetted local and international professional networks, lowering the friction of sourcing.',
    icon: Users,
  },
  {
    title: 'Efficient Candidate Screening',
    desc: 'Thorough background checks, psychological frameworks, and technical assessments to filter precisely.',
    icon: ShieldCheck,
  },
  {
    title: 'Strong Client Communication',
    desc: 'Transparent, proactive consulting reporting models keeping you updated during every stage of the lifecycle.',
    icon: MessageSquare,
  },
  {
    title: 'Tailored Hiring Solutions',
    desc: 'Strategies designed around your specific scale, budget parameters, operating market, and unique company culture.',
    icon: Sparkles,
  },
  {
    title: 'Reliable Workforce Support',
    desc: 'End-to-end expatriate compliance guidance, prompt payroll operations, and responsive HR advisory assistance.',
    icon: Layers,
  },
]

export default function AboutPage() {
  const [isModalOpen, setIsModalOpen] = useState(false)

  const openModal = () => setIsModalOpen(true)
  const closeModal = () => setIsModalOpen(false)

  return (
    <>
      <Helmet>
        <title>About Us | Elevare Human Solutions</title>
        <meta name="description" content="Learn about Elevare Human Solutions — our mission, values, and the team behind Africa's leading recruitment platform." />
        <meta property="og:title" content="About Us | Elevare Human Solutions" />
        <meta property="og:description" content="Learn about Elevare Human Solutions — our mission, values, and the team behind Africa's leading recruitment platform." />
        <meta property="og:url" content="https://elevare.com.ng/about" />
        <meta property="og:type" content="website" />
        <link rel="canonical" href="https://elevare.com.ng/about" />
      </Helmet>
      <Navbar onBookConsultation={openModal} />

      <main className="pt-16 bg-[#fafbfc]">
        {/* ── 1. Executive Hero Header ── */}
        <section className="relative overflow-hidden py-24 lg:py-32 text-white">
          {/* Background image from new_images_hero */}
          <div 
            className="absolute inset-0 bg-cover bg-center bg-no-repeat transition-transform duration-1000 scale-105"
            style={{ 
              backgroundImage: "url('/hero-images/img12.jpg')",
            }}
          />
          {/* Rich Overlay */}
          <div className="absolute inset-0 bg-gradient-to-r from-brand-blue-dark/95 via-brand-blue/85 to-transparent backdrop-blur-[2px]" />
          
          <div className="relative z-10 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="max-w-3xl space-y-6">
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded bg-brand-amber/20 text-brand-amber text-xs font-bold uppercase tracking-wider border border-brand-amber/35">
                About Elevare Human Solutions
              </span>
              <h1 className="text-4xl sm:text-5xl lg:text-7xl font-extrabold tracking-tight leading-tight" style={{ fontFamily: "'Lobster Two', cursive" }}>
                Pioneering Workforce Transformation &amp; HR Excellence
              </h1>
              <p className="text-lg lg:text-xl text-blue-100/90 leading-relaxed max-w-2xl">
                We deliver integrated people operations, recruitment expertise, and strategic workforce advisory to help ambitious organizations scale sustainably.
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

        {/* ── 2. Company Story & Mission ── */}
        <section className="py-16 sm:py-24 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 lg:gap-20 items-center">
            <div>
              <p className="text-brand-amber font-bold text-xs tracking-widest uppercase mb-2">Our Story</p>
              <h2 className="text-3xl sm:text-4xl font-extrabold text-text tracking-tight mb-6">
                Who We Are
              </h2>
              <p className="text-text-muted text-base leading-relaxed mb-6">
                Elevare Human Solutions Ltd is a professional human capital consulting and workforce solutions firm committed to helping organizations build high-performing, sustainable, and productive workforces.
              </p>
              <p className="text-text-muted text-base leading-relaxed">
                We provide integrated HR solutions that support businesses across recruitment, workforce management, organization development, employee engagement, payroll operations, leadership development, and performance management.
              </p>
            </div>
            <div className="bg-brand-blue rounded-2xl p-8 sm:p-10 text-white">
              <p className="text-brand-amber font-bold text-xs tracking-widest uppercase mb-4">Our Mission</p>
              <p className="text-lg sm:text-xl font-medium leading-relaxed text-blue-50">
                "To support organizations in building strong, productive, and sustainable workforces through practical HR solutions, strategic workforce advisory, and professional service delivery."
              </p>
            </div>
          </div>
        </section>

        {/* ── 3. Core Values ── */}
        <section className="bg-white py-16 sm:py-24 border-y border-border">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="text-center mb-16">
              <p className="text-brand-amber font-bold text-xs tracking-widest uppercase mb-2">What Drives Us</p>
              <h2 className="text-3xl sm:text-4xl font-extrabold text-text tracking-tight">Our Core Values</h2>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
              {[
                { label: 'Professional Integrity', icon: ShieldCheck },
                { label: 'Service Excellence', icon: Award },
                { label: 'Client Partnership', icon: Users },
                { label: 'Accountability', icon: CheckCircle2 },
                { label: 'Innovation', icon: Sparkles },
                { label: 'Talent Quality', icon: TrendingUp },
                { label: 'Workforce Transformation', icon: Layers },
                { label: 'Long-Term Business Impact', icon: Rocket },
              ].map(({ label, icon: Icon }) => (
                <div key={label} className="group bg-surface-muted hover:bg-brand-blue rounded-xl p-6 text-center flex flex-col items-center gap-3 transition-all duration-300 hover:shadow-md">
                  <div className="w-11 h-11 rounded-full bg-brand-blue-light text-brand-blue group-hover:bg-white/20 group-hover:text-white flex items-center justify-center transition-colors duration-300">
                    <Icon size={20} strokeWidth={2} />
                  </div>
                  <p className="font-bold text-sm text-text group-hover:text-white transition-colors">{label}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ── 4. Founder & Leadership Spotlight Section ── */}
        <section className="py-16 sm:py-24 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <p className="text-brand-amber font-bold text-xs tracking-widest uppercase mb-2">
              Leadership Spotlight
            </p>
            <h2 className="text-3xl sm:text-4xl font-extrabold text-text tracking-tight">
              Meet Our Founder &amp; Lead Consultant
            </h2>
            <div className="w-16 h-1 bg-brand-amber mx-auto mt-4 rounded"></div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 lg:gap-16 items-center">
            {/* Left Column: Image wrapper with highly executive glassmorphism style */}
            <div className="lg:col-span-5 flex justify-center">
              <div className="relative group max-w-sm sm:max-w-md w-full">
                {/* Floating design elements */}
                <div className="absolute -inset-1.5 bg-gradient-to-tr from-brand-blue to-brand-amber rounded-2xl blur opacity-25 group-hover:opacity-40 transition duration-300"></div>
                <div className="relative bg-white p-3 rounded-2xl shadow-2xl border border-border">
                  <div className="aspect-[3/4] overflow-hidden rounded-xl bg-slate-100">
                    <img
                      src={founderImg}
                      alt="Jennifer .O. Efe-Odiete, ACIPM, HRPL"
                      width={400}
                      height={533}
                      loading="lazy"
                      decoding="async"
                      className="w-full h-full object-cover grayscale-[15%] group-hover:grayscale-0 transition-all duration-500"
                    />
                  </div>
                  {/* Subtle Badge Overlay */}
                  <div className="absolute bottom-6 left-6 right-6 bg-white/95 backdrop-blur-md p-4 rounded-xl shadow-lg border border-border/50 text-center">
                    <p className="font-extrabold text-brand-blue text-sm uppercase tracking-wide">
                      Jennifer .O. Efe-Odiete
                    </p>
                    <p className="text-xs text-text-muted font-bold mt-1">ACIPM, HRPL</p>
                  </div>
                </div>
              </div>
            </div>

            {/* Right Column: Bio Content */}
            <div className="lg:col-span-7 space-y-6">
              <div>
                <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded bg-brand-blue-light text-brand-blue text-xs font-bold uppercase tracking-wider mb-3">
                  <Award size={14} /> Founder Spotlight
                </span>
                <h3 className="text-2xl sm:text-3xl font-extrabold text-text">
                  JENNIFER .O. EFE-ODIETE, ACIPM, HRPL
                </h3>
                <p className="text-brand-amber font-semibold text-sm mt-1.5">
                  Founder and Lead Consultant, Elevare Human Solutions Ltd
                </p>
              </div>

              <p className="text-text-muted text-base leading-relaxed">
                Jennifer is a Senior Human Resources Leader and Strategic Workforce Consultant with extensive experience delivering end-to-end HR solutions across multiple industries including oil and gas, hospitality, real estate, donor-funded organizations, and corporate services.
              </p>

              <div className="border-t border-border pt-6">
                <h4 className="text-sm uppercase tracking-wider font-extrabold text-text mb-4">
                  Strategic Specializations
                </h4>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
                  {[
                    'Recruitment Strategy',
                    'Performance Management',
                    'Organization Development',
                    'Workforce Governance',
                    'Expatriate Workforce Management',
                    'Employee Engagement',
                    'HR Operations',
                    'Payroll Administration',
                    'Leadership Development',
                  ].map((spec) => (
                    <div key={spec} className="flex items-center gap-2.5">
                      <div className="flex-shrink-0 w-5 h-5 rounded-full bg-brand-blue-light flex items-center justify-center text-brand-blue">
                        <CheckCircle2 size={14} className="stroke-[2.5]" />
                      </div>
                      <span className="text-sm font-semibold text-text">{spec}</span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="bg-surface-muted border-l-4 border-brand-amber p-5 rounded-r-lg mt-6">
                <p className="text-sm text-text-muted italic leading-relaxed">
                  "Through Elevare Human Solutions Ltd, she leads the delivery of integrated HR solutions that support organizations in building, managing, and optimizing their workforce for operational excellence and sustainable growth."
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* ── 3. Why Choose Elevare? Section ── */}
        <section className="bg-white py-16 sm:py-24 border-y border-border">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="text-center mb-16">
              <p className="text-brand-amber font-bold text-xs tracking-widest uppercase mb-2">
                Why Partners Work With Us
              </p>
              <h2 className="text-3xl sm:text-4xl font-extrabold text-text tracking-tight">
                WHY CHOOSE ELEVARE?
              </h2>
              <p className="text-text-muted text-sm max-w-xl mx-auto mt-2">
                Delivering high-caliber talent pipelines and optimized operations designed to grow alongside your organization.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
              {WHY_CHOOSE_US_DATA.map((item, idx) => {
                const IconComponent = item.icon
                return (
                  <article
                    key={idx}
                    className="group bg-white rounded-xl border border-border p-6 shadow-sm hover:shadow-lg hover:border-brand-blue/20 transition-all duration-300 flex flex-col gap-4"
                  >
                    <div className="w-12 h-12 rounded-lg bg-brand-blue-light text-brand-blue flex items-center justify-center transition-all duration-300 group-hover:bg-brand-blue group-hover:text-white group-hover:scale-105">
                      <IconComponent size={22} strokeWidth={2} />
                    </div>
                    <div>
                      <h3 className="font-bold text-text mb-2 text-base transition-colors group-hover:text-brand-blue">
                        {item.title}
                      </h3>
                      <p className="text-text-muted text-xs sm:text-sm leading-relaxed">
                        {item.desc}
                      </p>
                    </div>
                  </article>
                )
              })}
            </div>
          </div>
        </section>

        {/* ── 4. Industries We Serve Section ── */}
        <section className="py-16 sm:py-24 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <p className="text-brand-amber font-bold text-xs tracking-widest uppercase mb-2">
              Cross-Industry Versatility
            </p>
            <h2 className="text-3xl sm:text-4xl font-extrabold text-text tracking-tight">
              INDUSTRIES WE SERVE
            </h2>
            <p className="text-text-muted text-sm max-w-xl mx-auto mt-2">
              Supporting standard organizations and niche industrial brands with premium talent consulting strategies.
            </p>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-6">
            {INDUSTRIES.map((ind, idx) => {
              const Icon = ind.icon
              return (
                <div
                  key={idx}
                  className="group bg-white p-6 rounded-xl border border-border shadow-sm text-center flex flex-col items-center justify-center gap-4 transition-all duration-300 hover:shadow-md hover:-translate-y-1 hover:border-brand-amber/20"
                >
                  <div className="w-12 h-12 rounded-full bg-brand-blue-light text-brand-blue flex items-center justify-center group-hover:bg-brand-amber group-hover:text-white transition-colors duration-300">
                    <Icon size={22} strokeWidth={2} />
                  </div>
                  <h3 className="font-bold text-text text-xs sm:text-sm leading-snug">
                    {ind.name}
                  </h3>
                </div>
              )
            })}
          </div>
        </section>

        {/* ── Register CTA ── */}
        <section className="py-16 sm:py-20 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <h2 className="text-3xl sm:text-4xl font-extrabold text-text mb-4">Ready to get started?</h2>
          <p className="text-text-muted text-base max-w-xl mx-auto mb-8">
            Join hundreds of employers and candidates already using Elevare to build better careers and stronger teams.
          </p>
          <Link to="/register">
            <Button className="bg-brand-blue hover:bg-brand-blue/90 text-white border-0 px-8 py-3 text-sm font-bold uppercase tracking-wider rounded-full shadow-sm hover:scale-[1.02] transition-transform inline-flex items-center gap-2">
              Join Us <ArrowRight size={16} />
            </Button>
          </Link>
        </section>

        {/* ── 5. stay connected CTA/Social media connections Section ── */}
        <section className="relative overflow-hidden bg-brand-blue py-16 sm:py-24 text-white border-t border-border">
          <div className="absolute inset-0 bg-gradient-to-r from-brand-blue to-brand-blue-dark opacity-95" />
          <div className="relative z-10 max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="text-center mb-12">
              <p className="text-brand-amber font-bold text-xs tracking-widest uppercase mb-3">
                Stay Updated
              </p>
              <h2 className="text-3xl sm:text-4xl font-extrabold mb-4">
                Stay Connected With Elevare
              </h2>
              <p className="text-base text-blue-100 max-w-2xl mx-auto leading-relaxed">
                If you're not already following us on our social media platforms, please do so. It helps us stay connected and makes it easier for you to stay updated with what we're sharing.
              </p>
            </div>

            {/* Social Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 max-w-4xl mx-auto">
              {/* WhatsApp Card */}
              <a
                href="https://chat.whatsapp.com/F4ixcZxlxO38N79oPr0I7b?mode=gi_c"
                target="_blank"
                rel="noopener noreferrer"
                className="group flex items-center gap-4 bg-white/10 hover:bg-[#25D366]/20 p-5 rounded-xl border border-white/10 hover:border-[#25D366]/40 transition-all duration-300 shadow"
              >
                <div className="w-10 h-10 rounded-lg bg-white/10 text-white flex items-center justify-center group-hover:bg-[#25D366] transition-colors duration-300">
                  <WhatsAppIcon size={20} />
                </div>
                <div>
                  <p className="font-extrabold text-xs uppercase tracking-wide text-blue-200">WhatsApp</p>
                  <p className="font-bold text-sm text-white mt-0.5 group-hover:text-[#25D366] transition-colors">Follow Group</p>
                </div>
              </a>

              {/* Instagram Card 1 (Personal) */}
              <a
                href="https://www.instagram.com/hrgirloflagos?igsh=a3J4Mmp6bWE1cDdj&utm_source=qr"
                target="_blank"
                rel="noopener noreferrer"
                className="group flex items-center gap-4 bg-white/10 hover:bg-[#E1306C]/20 p-5 rounded-xl border border-white/10 hover:border-[#E1306C]/40 transition-all duration-300 shadow"
              >
                <div className="w-10 h-10 rounded-lg bg-white/10 text-white flex items-center justify-center group-hover:bg-gradient-to-tr group-hover:from-[#f9ce34] group-hover:via-[#ee2a7b] group-hover:to-[#6228d7] transition-all duration-300">
                  <InstagramIcon size={20} />
                </div>
                <div>
                  <p className="font-extrabold text-xs uppercase tracking-wide text-blue-200">Instagram</p>
                  <p className="font-bold text-sm text-white mt-0.5 group-hover:text-[#ee2a7b] transition-colors">@hrgirloflagos</p>
                </div>
              </a>

              {/* Instagram Card 2 (Business) */}
              <a
                href="https://www.instagram.com/elevare_recruits_ehls?igsh=MTVidmozZ2VzOXN6aQ%3D%3D&utm_source=qr"
                target="_blank"
                rel="noopener noreferrer"
                className="group flex items-center gap-4 bg-white/10 hover:bg-[#E1306C]/20 p-5 rounded-xl border border-white/10 hover:border-[#E1306C]/40 transition-all duration-300 shadow"
              >
                <div className="w-10 h-10 rounded-lg bg-white/10 text-white flex items-center justify-center group-hover:bg-gradient-to-tr group-hover:from-[#f9ce34] group-hover:via-[#ee2a7b] group-hover:to-[#6228d7] transition-all duration-300">
                  <InstagramIcon size={20} />
                </div>
                <div>
                  <p className="font-extrabold text-xs uppercase tracking-wide text-blue-200">Instagram Business</p>
                  <p className="font-bold text-sm text-white mt-0.5 group-hover:text-[#ee2a7b] transition-colors">@elevare_recruits_ehls</p>
                </div>
              </a>

              {/* LinkedIn Card */}
              <a
                href="https://www.linkedin.com/company/elevare-human-solutions-ltd/?viewAsMember=true"
                target="_blank"
                rel="noopener noreferrer"
                className="group flex items-center gap-4 bg-white/10 hover:bg-[#0A66C2]/20 p-5 rounded-xl border border-white/10 hover:border-[#0A66C2]/40 transition-all duration-300 shadow"
              >
                <div className="w-10 h-10 rounded-lg bg-white/10 text-white flex items-center justify-center group-hover:bg-[#0A66C2] transition-colors duration-300">
                  <LinkedInIcon size={20} />
                </div>
                <div>
                  <p className="font-extrabold text-xs uppercase tracking-wide text-blue-200">LinkedIn</p>
                  <p className="font-bold text-sm text-white mt-0.5 group-hover:text-[#0A66C2] transition-colors">Elevare Solutions</p>
                </div>
              </a>

              {/* TikTok Card */}
              <a
                href="https://www.tiktok.com/@sexy_jenny13?_r=1&_t=ZS-93UCex6vqKo"
                target="_blank"
                rel="noopener noreferrer"
                className="group flex items-center gap-4 bg-white/10 hover:bg-black/40 p-5 rounded-xl border border-white/10 hover:border-black/50 transition-all duration-300 shadow sm:col-span-2 lg:col-span-1"
              >
                <div className="w-10 h-10 rounded-lg bg-white/10 text-white flex items-center justify-center group-hover:bg-black transition-colors duration-300">
                  <TikTokIcon size={20} />
                </div>
                <div>
                  <p className="font-extrabold text-xs uppercase tracking-wide text-blue-200">TikTok</p>
                  <p className="font-bold text-sm text-white mt-0.5 group-hover:text-red-400 transition-colors">@sexy_jenny13</p>
                </div>
              </a>
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
