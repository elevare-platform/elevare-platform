import Navbar from '@/components/layout/Navbar'
import Footer from '@/components/layout/Footer'
import { FloatingWhatsApp } from '@/components/ui/FloatingWhatsApp'
import { Helmet } from 'react-helmet-async'
import { Link } from 'react-router-dom'

const SECTIONS = [
  {
    title: 'Acceptance of Terms',
    content:
      'By accessing or using the Elevare platform, you agree to be bound by these Terms of Service. If you do not agree, please do not use the platform.',
  },
  {
    title: 'Use of the Platform',
    content:
      'Elevare is a recruitment platform connecting employers and candidates. You agree to use the platform only for lawful purposes and in accordance with these terms. You must not misuse, reverse-engineer, or attempt to gain unauthorised access to any part of the platform.',
  },
  {
    title: 'Employer Responsibilities',
    content:
      'Employers are responsible for the accuracy of job listings and the legality of their hiring practices. Job listings must not discriminate on protected grounds. Elevare reserves the right to remove any listing that violates these terms.',
  },
  {
    title: 'Candidate Responsibilities',
    content:
      'Candidates are responsible for the accuracy of their profile and CV. Submitting false information may result in account suspension. Applications must represent genuine interest in the role.',
  },
  {
    title: 'Third-Party Mail Integrations',
    content:
      'Employers may connect a Gmail or Zoho Mail account to automatically import CVs from their recruitment inbox. This is optional, requires the employer\'s explicit authorisation via that provider\'s OAuth consent screen, and can be revoked at any time. See our Privacy Policy for details on how this data is accessed and used.',
  },
  {
    title: 'Intellectual Property',
    content:
      'All content on the Elevare platform (including design, copy, and software) is owned by Elevare Human Solutions Ltd. You may not reproduce or distribute any content without written permission.',
  },
  {
    title: 'Limitation of Liability',
    content:
      'Elevare is not liable for any loss or damage arising from your use of the platform, including but not limited to hiring decisions, employment outcomes, or data inaccuracies.',
  },
  {
    title: 'Changes to These Terms',
    content:
      'We may update these terms from time to time. Continued use of the platform after changes constitutes acceptance of the revised terms.',
  },
  {
    title: 'Contact Us',
    content: null,
  },
]

export default function TermsPage() {
  return (
    <>
      <Helmet>
        <title>Terms of Service | Elevare Human Solutions</title>
        <meta name="description" content="Read Elevare's terms of service, the rules and guidelines governing use of our recruitment platform." />
        <link rel="canonical" href="https://elevare.com.ng/terms" />
      </Helmet>
      <Navbar />
      <main className="pt-16 bg-[#fafbfc]">
        <section className="relative overflow-hidden bg-brand-blue py-20 text-white">
          <div className="absolute inset-0 bg-gradient-to-tr from-brand-blue via-brand-blue-dark to-brand-blue-light opacity-80" />
          <div className="relative z-10 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
            <p className="text-brand-amber font-bold text-xs tracking-widest uppercase mb-4">Legal</p>
            <h1 className="text-4xl sm:text-5xl font-extrabold tracking-tight leading-tight">Terms of Service</h1>
          </div>
        </section>

        <section className="py-16 sm:py-24 max-w-3xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="space-y-10">
            {SECTIONS.map((s) => (
              <div key={s.title}>
                <h2 className="text-lg font-extrabold text-text mb-3">{s.title}</h2>
                {s.content ? (
                  <p className="text-sm text-text-muted leading-relaxed">{s.content}</p>
                ) : (
                  <p className="text-sm text-text-muted leading-relaxed">
                    For terms-related enquiries, email us at{' '}
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

          <p className="mt-16 text-xs text-text-muted">Last updated: July 2026</p>
        </section>
      </main>
      <Footer />
      <FloatingWhatsApp />
    </>
  )
}
