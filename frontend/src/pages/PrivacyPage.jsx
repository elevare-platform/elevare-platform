import Navbar from '@/components/layout/Navbar'
import Footer from '@/components/layout/Footer'
import { FloatingWhatsApp } from '@/components/ui/FloatingWhatsApp'
import { Helmet } from 'react-helmet-async'
import { Link } from 'react-router-dom'
import { AlertCircle } from 'lucide-react'

const SECTIONS = [
  {
    title: 'Data We Collect',
    content:
      'We collect information you provide directly — such as your name, email address, CV, and professional experience — as well as usage data collected automatically when you interact with our platform.',
  },
  {
    title: 'How We Use Your Data',
    content:
      'Your data is used to match candidates with relevant job opportunities, enable employers to manage applications, communicate platform updates, and improve our services. We do not sell your personal data to third parties.',
  },
  {
    title: 'Data Sharing',
    content:
      'Candidate profile information is shared with employers only when you apply for a role or set your profile to visible. Contact form submissions are shared internally with the relevant Elevare team.',
  },
  {
    title: 'Data Retention',
    content:
      'We retain your data for as long as your account is active. You may request deletion of your account and associated data at any time by contacting us.',
  },
  {
    title: 'Your Rights',
    content:
      'Under GDPR and the Nigeria Data Protection Regulation (NDPR), you have the right to access, correct, or delete your personal data. You may also withdraw consent or request a copy of the data we hold about you.',
  },
  {
    title: 'Contact Us',
    content: null,
  },
]

export default function PrivacyPage() {
  return (
    <>
      <Helmet>
        <title>Privacy Policy | Elevare Human Solutions</title>
        <meta name="description" content="Read Elevare's privacy policy — how we collect, use, and protect your personal data in compliance with GDPR and Nigeria's NDPR." />
        <link rel="canonical" href="https://elevare.com.ng/privacy" />
      </Helmet>
      <Navbar />
      <main className="pt-16 bg-[#fafbfc]">
        <section className="relative overflow-hidden bg-brand-blue py-20 text-white">
          <div className="absolute inset-0 bg-gradient-to-tr from-brand-blue via-brand-blue-dark to-brand-blue-light opacity-80" />
          <div className="relative z-10 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
            <p className="text-brand-amber font-bold text-xs tracking-widest uppercase mb-4">Legal</p>
            <h1 className="text-4xl sm:text-5xl font-extrabold tracking-tight leading-tight">Privacy Policy</h1>
          </div>
        </section>

        <section className="py-16 sm:py-24 max-w-3xl mx-auto px-4 sm:px-6 lg:px-8">
          {/* Draft notice */}
          <div className="flex items-start gap-3 bg-amber-50 border border-amber-200 rounded-lg px-5 py-4 mb-12">
            <AlertCircle size={18} className="text-amber-500 flex-shrink-0 mt-0.5" />
            <p className="text-sm text-amber-800">
              This policy is being finalised. Please{' '}
              <Link to="/contact" className="font-semibold underline hover:text-amber-900">
                contact us
              </Link>{' '}
              for any questions in the meantime.
            </p>
          </div>

          <div className="space-y-10">
            {SECTIONS.map((s) => (
              <div key={s.title}>
                <h2 className="text-lg font-extrabold text-text mb-3">{s.title}</h2>
                {s.content ? (
                  <p className="text-sm text-text-muted leading-relaxed">{s.content}</p>
                ) : (
                  <p className="text-sm text-text-muted leading-relaxed">
                    For privacy-related enquiries, email us at{' '}
                    <a href="mailto:hr@elevare.com.ng" className="text-brand-blue hover:underline font-medium">
                      hr@elevare.com.ng
                    </a>{' '}
                    or use our{' '}
                    <Link to="/contact" className="text-brand-blue hover:underline font-medium">
                      contact form
                    </Link>
                    .
                  </p>
                )}
              </div>
            ))}
          </div>

          <p className="mt-16 text-xs text-text-muted">Last updated: June 2026</p>
        </section>
      </main>
      <Footer />
      <FloatingWhatsApp />
    </>
  )
}
