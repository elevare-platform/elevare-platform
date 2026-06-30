import { Link } from 'react-router-dom'
import { Helmet } from 'react-helmet-async'
import Navbar from '@/components/layout/Navbar'
import Footer from '@/components/layout/Footer'
import { FloatingWhatsApp } from '@/components/ui/FloatingWhatsApp'
import { Button } from '@/components/ui/button'
import { CheckCircle2, Minus } from 'lucide-react'

const TIERS = [
  {
    name: 'Starter',
    price: 'Free',
    description: 'Get started with essential hiring tools at no cost.',
    highlight: false,
    cta: { label: 'Get Started', href: '/register?role=employer' },
    features: [
      { text: 'Up to 3 active job postings', included: true },
      { text: 'Basic candidate search', included: true },
      { text: 'Application management dashboard', included: true },
      { text: 'Email notifications', included: true },
      { text: 'Unlimited job postings', included: false },
      { text: 'Priority candidate matching', included: false },
      { text: 'Dedicated account manager', included: false },
      { text: 'SLA guarantee', included: false },
    ],
  },
  {
    name: 'Professional',
    price: 'TBD',
    priceNote: 'per month',
    description: 'For growing teams that need unlimited reach and priority support.',
    highlight: true,
    badge: 'Most Popular',
    cta: { label: 'Get Started', href: '/register?role=employer' },
    features: [
      { text: 'Unlimited active job postings', included: true },
      { text: 'Advanced candidate search & filters', included: true },
      { text: 'Application management dashboard', included: true },
      { text: 'Email notifications', included: true },
      { text: 'Priority candidate matching', included: true },
      { text: 'Priority support', included: true },
      { text: 'Dedicated account manager', included: false },
      { text: 'SLA guarantee', included: false },
    ],
  },
  {
    name: 'Enterprise',
    price: 'Custom',
    description: 'Tailored solutions for organisations with complex or high-volume hiring needs.',
    highlight: false,
    cta: { label: 'Contact Sales', href: '/contact?type=employer_inquiry' },
    features: [
      { text: 'Unlimited active job postings', included: true },
      { text: 'Advanced candidate search & filters', included: true },
      { text: 'Application management dashboard', included: true },
      { text: 'Email notifications', included: true },
      { text: 'Priority candidate matching', included: true },
      { text: 'Priority support', included: true },
      { text: 'Dedicated account manager', included: true },
      { text: 'SLA guarantee', included: true },
    ],
  },
]

export default function PricingPage() {
  return (
    <>
      <Helmet>
        <title>Pricing | Elevare Human Solutions</title>
        <meta name="description" content="Simple, transparent pricing for employers. Start free and scale as you grow — Starter, Professional, and Enterprise plans available." />
        <meta property="og:title" content="Pricing | Elevare Human Solutions" />
        <meta property="og:description" content="Simple, transparent pricing for employers. Start free and scale as you grow." />
        <meta property="og:url" content="https://elevare.com.ng/pricing" />
        <meta property="og:type" content="website" />
        <link rel="canonical" href="https://elevare.com.ng/pricing" />
      </Helmet>
      <Navbar />

      <main className="pt-16 bg-[#fafbfc]">

        {/* ── Hero ── */}
        <section className="relative overflow-hidden py-24 lg:py-32 text-white">
          <div 
            className="absolute inset-0 bg-cover bg-center bg-no-repeat transition-transform duration-1000 scale-105"
            style={{ backgroundImage: "url('/hero-images/img25.jpg')" }}
          />
          <div className="absolute inset-0 bg-gradient-to-r from-brand-blue-dark/95 via-brand-blue/85 to-transparent backdrop-blur-[2px]" />
          
          <div className="relative z-10 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="max-w-3xl space-y-6">
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded bg-brand-amber/20 text-brand-amber text-xs font-bold uppercase tracking-wider border border-brand-amber/35">
                Pricing
              </span>
              <h1 className="text-4xl sm:text-5xl lg:text-7xl font-extrabold tracking-tight leading-tight" style={{ fontFamily: "'Lobster Two', cursive" }}>
                Simple, Transparent Pricing
              </h1>
              <p className="text-lg lg:text-xl text-blue-100/90 leading-relaxed max-w-2xl">
                Start free and scale as you grow. No hidden fees, no surprises.
              </p>
            </div>
          </div>
          <div className="curve-divider-bottom" style={{ height: '3vw' }}>
            <svg viewBox="0 0 1440 120" fill="none" xmlns="http://www.w3.org/2000/svg" className="w-full h-full">
              <path d="M0,64L120,80C240,96,480,128,720,128C960,128,1200,96,1320,80L1440,64L1440,120L1320,120C1200,120,960,120,720,120C480,120,240,120,120,120L0,120Z" fill="#fafbfc" />
            </svg>
          </div>
        </section>

        {/* ── Tiers ── */}
        <section className="py-16 sm:py-24 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8 items-start">
            {TIERS.map((tier) => (
              <div
                key={tier.name}
                className={`premium-card relative rounded-2xl border p-8 flex flex-col gap-6 ${
                  tier.highlight
                    ? 'bg-brand-blue text-white border-brand-blue shadow-2xl scale-[1.03]'
                    : 'bg-white border-border premium-shadow'
                }`}
              >
                {tier.badge && (
                  <span className="absolute -top-3.5 left-1/2 -translate-x-1/2 bg-brand-amber text-white text-xs font-bold uppercase tracking-wider px-4 py-1 rounded-full shadow">
                    {tier.badge}
                  </span>
                )}

                <div>
                  <p className={`text-xs font-bold uppercase tracking-widest mb-1 ${tier.highlight ? 'text-blue-200' : 'text-brand-amber'}`}>
                    {tier.name}
                  </p>
                  <div className="flex items-end gap-1.5 mb-2">
                    <span className={`text-4xl font-extrabold ${tier.highlight ? 'text-white' : 'text-text'}`}>
                      {tier.price}
                    </span>
                    {tier.priceNote && (
                      <span className={`text-sm mb-1 ${tier.highlight ? 'text-blue-200' : 'text-text-muted'}`}>
                        {tier.priceNote}
                      </span>
                    )}
                  </div>
                  <p className={`text-sm leading-relaxed ${tier.highlight ? 'text-blue-100' : 'text-text-muted'}`}>
                    {tier.description}
                  </p>
                </div>

                <ul className="space-y-3 flex-1">
                  {tier.features.map((f) => (
                    <li key={f.text} className="flex items-start gap-3">
                      {f.included ? (
                        <CheckCircle2
                          size={16}
                          className={`flex-shrink-0 mt-0.5 ${tier.highlight ? 'text-brand-amber' : 'text-brand-blue'}`}
                        />
                      ) : (
                        <Minus
                          size={16}
                          className={`flex-shrink-0 mt-0.5 ${tier.highlight ? 'text-blue-400' : 'text-border'}`}
                        />
                      )}
                      <span className={`text-sm ${
                        f.included
                          ? tier.highlight ? 'text-white' : 'text-text'
                          : tier.highlight ? 'text-blue-300' : 'text-text-muted'
                      }`}>
                        {f.text}
                      </span>
                    </li>
                  ))}
                </ul>

                <Link to={tier.cta.href}>
                  <Button
                    className={`w-full font-bold text-sm uppercase tracking-wider rounded-full border-0 ${
                      tier.highlight
                        ? 'bg-brand-amber hover:bg-brand-amber-dark text-white'
                        : 'bg-brand-blue hover:bg-brand-blue/90 text-white'
                    }`}
                  >
                    {tier.cta.label}
                  </Button>
                </Link>
              </div>
            ))}
          </div>

          <p className="text-center text-xs text-text-muted mt-10">
            Pricing subject to change. Contact us for current rates.
          </p>

          {/* Candidate callout */}
          <div className="mt-12 bg-white border border-border rounded-2xl p-8 text-center max-w-2xl mx-auto">
            <p className="text-xs font-bold text-brand-amber uppercase tracking-widest mb-2">For Candidates</p>
            <h3 className="text-xl font-extrabold text-text mb-2">Always Free</h3>
            <p className="text-sm text-text-muted mb-6">
              Creating a profile, uploading your CV, and applying to jobs is completely free — no plan required, no credit card needed.
            </p>
            <Link to="/register?role=candidate">
              <Button className="bg-brand-blue hover:bg-brand-blue/90 text-white border-0 px-8 rounded-full text-sm font-bold uppercase tracking-wider">
                Create Your Profile
              </Button>
            </Link>
          </div>
        </section>

      </main>

      <Footer />
      <FloatingWhatsApp />
    </>
  )
}
