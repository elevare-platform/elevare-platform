import { useState, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Helmet } from 'react-helmet-async'
import Navbar from '@/components/layout/Navbar'
import Footer from '@/components/layout/Footer'
import { FloatingWhatsApp } from '@/components/ui/FloatingWhatsApp'
import { Button } from '@/components/ui/button'
import api from '@/lib/api'
import { trackEvent } from '@/lib/analytics'
import { Mail, Phone, MapPin, CheckCircle2, AlertCircle } from 'lucide-react'

function LinkedInIcon({ size = 18 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.3 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/>
    </svg>
  )
}

const INQUIRY_TYPES = [
  { value: 'general', label: 'General Enquiry' },
  { value: 'employer_inquiry', label: 'Employer / Sales Enquiry' },
]

const CONTACT_INFO = [
  {
    icon: Mail,
    label: 'Email',
    value: 'hr@elevare.com.ng',
    href: 'mailto:hr@elevare.com.ng',
  },
  {
    icon: Phone,
    label: 'Phone',
    value: '+234 812 522 0774',
    href: 'tel:+2348125220774',
  },
  {
    icon: MapPin,
    label: 'Office',
    value: 'Lekki Gardens, Eti-Osa, Lekki 106104, Lagos, Nigeria',
    href: 'https://maps.google.com/?q=Lekki+Gardens+Eti-Osa+Lagos+Nigeria',
  },
  {
    icon: LinkedInIcon,
    label: 'LinkedIn',
    value: 'Elevare Human Solutions',
    href: 'https://www.linkedin.com/company/elevare-human-solutions-ltd/?viewAsMember=true',
  },
]

export default function ContactPage() {
  const [searchParams] = useSearchParams()
  const [form, setForm] = useState({
    name: '',
    email: '',
    company: '',
    message: '',
    inquiry_type: 'general',
    honeypot: '',
  })
  const [status, setStatus] = useState('idle') // idle | loading | success | error
  const [errorMsg, setErrorMsg] = useState('')

  // Pre-select inquiry type from URL param ?type=employer_inquiry
  useEffect(() => {
    const type = searchParams.get('type')
    if (type === 'employer_inquiry') {
      setForm((f) => ({ ...f, inquiry_type: 'employer_inquiry' }))
    }
  }, [searchParams])

  const handleChange = (e) => {
    const { name, value } = e.target
    setForm((f) => ({ ...f, [name]: value }))
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setStatus('loading')
    setErrorMsg('')

    try {
      await api.post('/api/v1/contact', {
        name: form.name.trim(),
        email: form.email.trim(),
        company: form.company.trim() || undefined,
        message: form.message.trim(),
        inquiry_type: form.inquiry_type,
        honeypot: form.honeypot,
      })
      setStatus('success')
      if (form.inquiry_type === 'employer_inquiry') {
        trackEvent('Contact', 'employer_inquiry')
      }
    } catch (err) {
      const data = err.response?.data
      // Custom envelope: { details: [{ field, message }] }
      if (Array.isArray(data?.details) && data.details.length > 0) {
        setErrorMsg(data.details.map((d) => d.message).join(' '))
      } else if (typeof data?.message === 'string') {
        setErrorMsg(data.message)
      } else if (typeof data?.detail === 'string') {
        setErrorMsg(data.detail)
      } else {
        setErrorMsg('Something went wrong. Please try again.')
      }
      setStatus('error')
    }
  }

  return (
    <>
      <Helmet>
        <title>Contact Us | Elevare Human Solutions</title>
        <meta name="description" content="Get in touch with the Elevare team. Employer sales enquiries, general questions, or just say hello — we respond within 24 hours." />
        <meta property="og:title" content="Contact Us | Elevare Human Solutions" />
        <meta property="og:description" content="Get in touch with the Elevare team. We respond within 24 hours on business days." />
        <meta property="og:url" content="https://elevare.com.ng/contact" />
        <meta property="og:type" content="website" />
        <link rel="canonical" href="https://elevare.com.ng/contact" />
      </Helmet>
      <Navbar />

      <main className="pt-16 bg-[#fafbfc]">

        {/* ── Hero ── */}
        <section className="relative overflow-hidden py-24 lg:py-32 text-white">
          <div 
            className="absolute inset-0 bg-cover bg-center bg-no-repeat transition-transform duration-1000 scale-105"
            style={{ backgroundImage: "url('/hero-images/img20.jpg')" }}
          />
          <div className="absolute inset-0 bg-gradient-to-r from-brand-blue-dark/95 via-brand-blue/85 to-transparent backdrop-blur-[2px]" />
          
          <div className="relative z-10 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="max-w-3xl space-y-6">
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded bg-brand-amber/20 text-brand-amber text-xs font-bold uppercase tracking-wider border border-brand-amber/35">
                Contact Us
              </span>
              <h1 className="font-sans text-4xl sm:text-5xl lg:text-7xl font-extrabold tracking-tight leading-tight">
                Get in Touch
              </h1>
              <p className="text-lg lg:text-xl text-blue-100/90 leading-relaxed max-w-xl">
                We typically respond within 24 hours on business days.
              </p>
            </div>
          </div>
          <div className="curve-divider-bottom" style={{ height: '3vw' }}>
            <svg viewBox="0 0 1440 120" fill="none" xmlns="http://www.w3.org/2000/svg" className="w-full h-full">
              <path d="M0,64L120,80C240,96,480,128,720,128C960,128,1200,96,1320,80L1440,64L1440,120L1320,120C1200,120,960,120,720,120C480,120,240,120,120,120L0,120Z" fill="#fafbfc" />
            </svg>
          </div>
        </section>

        {/* ── Split layout ── */}
        <section className="py-16 sm:py-24 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-1 lg:grid-cols-5 gap-12 lg:gap-20">

            {/* ── Left: Form ── */}
            <div className="lg:col-span-3">
              {status === 'success' ? (
                <div className="flex flex-col items-center justify-center text-center py-16 gap-4">
                  <CheckCircle2 size={48} className="text-green-500" />
                  <h2 className="text-2xl font-extrabold text-text">Message Sent</h2>
                  <p className="text-text-muted text-sm max-w-sm">
                    Thank you — we'll be in touch within 24 hours.
                  </p>
                  <button
                    className="mt-4 text-sm text-brand-blue font-semibold hover:underline"
                    onClick={() => { setStatus('idle'); setForm({ name: '', email: '', company: '', message: '', inquiry_type: 'general', honeypot: '' }) }}
                  >
                    Send another message
                  </button>
                </div>
              ) : (
                <form onSubmit={handleSubmit} noValidate aria-label="Contact form" className="space-y-5">
                  <h2 className="text-2xl font-extrabold text-text mb-6">Send us a message</h2>

                  {/* Honeypot — hidden from real users, bots fill it */}
                  <div style={{ position: 'absolute', left: '-9999px' }} aria-hidden="true">
                    <label htmlFor="contact_website">Website</label>
                    <input
                      id="contact_website"
                      name="honeypot"
                      type="text"
                      tabIndex={-1}
                      autoComplete="off"
                      value={form.honeypot}
                      onChange={handleChange}
                    />
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
                    <div className="flex flex-col gap-1.5">
                      <label htmlFor="name" className="text-xs font-bold text-text uppercase tracking-wider">
                        Full Name <span className="text-red-500">*</span>
                      </label>
                      <input
                        id="name"
                        name="name"
                        type="text"
                        required
                        value={form.name}
                        onChange={handleChange}
                        placeholder="Jennifer Efe-Odiete"
                        className="w-full rounded-lg border border-border px-4 py-2.5 text-sm text-text placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-brand-blue"
                      />
                    </div>
                    <div className="flex flex-col gap-1.5">
                      <label htmlFor="email" className="text-xs font-bold text-text uppercase tracking-wider">
                        Email Address <span className="text-red-500">*</span>
                      </label>
                      <input
                        id="email"
                        name="email"
                        type="email"
                        required
                        value={form.email}
                        onChange={handleChange}
                        placeholder="you@company.com"
                        className="w-full rounded-lg border border-border px-4 py-2.5 text-sm text-text placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-brand-blue"
                      />
                    </div>
                  </div>

                  <div className="flex flex-col gap-1.5">
                    <label htmlFor="company" className="text-xs font-bold text-text uppercase tracking-wider">
                      Company <span className="text-text-muted font-normal normal-case">(optional)</span>
                    </label>
                    <input
                      id="company"
                      name="company"
                      type="text"
                      value={form.company}
                      onChange={handleChange}
                      placeholder="Your organisation"
                      className="w-full rounded-lg border border-border px-4 py-2.5 text-sm text-text placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-brand-blue"
                    />
                  </div>

                  <div className="flex flex-col gap-1.5">
                    <label htmlFor="inquiry_type" className="text-xs font-bold text-text uppercase tracking-wider">
                      Enquiry Type <span className="text-red-500">*</span>
                    </label>
                    <select
                      id="inquiry_type"
                      name="inquiry_type"
                      value={form.inquiry_type}
                      onChange={handleChange}
                      className="w-full rounded-lg border border-border px-4 py-2.5 text-sm text-text bg-white focus:outline-none focus:ring-2 focus:ring-brand-blue"
                    >
                      {INQUIRY_TYPES.map((t) => (
                        <option key={t.value} value={t.value}>{t.label}</option>
                      ))}
                    </select>
                  </div>

                  <div className="flex flex-col gap-1.5">
                    <label htmlFor="message" className="text-xs font-bold text-text uppercase tracking-wider">
                      Message <span className="text-red-500">*</span>
                    </label>
                    <textarea
                      id="message"
                      name="message"
                      required
                      rows={5}
                      value={form.message}
                      onChange={handleChange}
                      placeholder="How can we help you? (minimum 20 characters)"
                      className="w-full rounded-lg border border-border px-4 py-2.5 text-sm text-text placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-brand-blue resize-none"
                    />
                  </div>

                  {status === 'error' && (
                    <div className="flex items-start gap-2 bg-red-50 border border-red-200 rounded-lg px-4 py-3" role="alert">
                      <AlertCircle size={16} className="text-red-500 flex-shrink-0 mt-0.5" />
                      <p className="text-sm text-red-700">{errorMsg}</p>
                    </div>
                  )}

                  <Button
                    type="submit"
                    disabled={status === 'loading'}
                    className="w-full sm:w-auto bg-brand-blue hover:bg-brand-blue/90 text-white border-0 px-10 py-3 text-sm font-bold uppercase tracking-wider rounded-full"
                  >
                    {status === 'loading' ? 'Sending…' : 'Send Message'}
                  </Button>
                </form>
              )}
            </div>

            {/* ── Right: Contact info ── */}
            <div className="lg:col-span-2 space-y-8">
              <div>
                <h2 className="text-2xl font-extrabold text-text mb-2">Contact Information</h2>
                <p className="text-sm text-text-muted leading-relaxed">
                  Reach us directly or visit our office in Lagos.
                </p>
              </div>

              <ul className="space-y-6">
                {CONTACT_INFO.map(({ icon: Icon, label, value, href }) => (
                  <li key={label} className="flex items-start gap-4">
                    <div className="flex-shrink-0 w-10 h-10 rounded-lg bg-brand-blue-light text-brand-blue flex items-center justify-center">
                      <Icon size={18} />
                    </div>
                    <div>
                      <p className="text-xs font-bold uppercase tracking-wider text-text-muted mb-0.5">{label}</p>
                      <a
                        href={href}
                        target={href.startsWith('http') ? '_blank' : undefined}
                        rel={href.startsWith('http') ? 'noopener noreferrer' : undefined}
                        className="text-sm text-text hover:text-brand-blue transition-colors"
                      >
                        {value}
                      </a>
                    </div>
                  </li>
                ))}
              </ul>

              <div className="bg-brand-blue rounded-2xl p-6 text-white">
                <p className="text-xs font-bold uppercase tracking-widest text-blue-200 mb-2">Response Time</p>
                <p className="text-sm text-blue-100 leading-relaxed">
                  We aim to respond to all enquiries within <span className="text-white font-bold">24 hours</span> on business days. For urgent hiring needs, select <span className="text-brand-amber font-semibold">Employer / Sales Enquiry</span> for priority handling.
                </p>
              </div>
            </div>

          </div>
        </section>

      </main>

      <Footer />
      <FloatingWhatsApp />
    </>
  )
}
