import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Mail } from 'lucide-react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import ElevareLogo from '@/components/ui/ElevareLogo'

// Inline SVG brand icons (lucide-react does not ship brand icons)
function LinkedInIcon({ size = 16 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4v-7a6 6 0 0 1 6-6z" />
      <rect x="2" y="9" width="4" height="12" />
      <circle cx="4" cy="4" r="2" />
    </svg>
  )
}

function TwitterXIcon({ size = 16 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
    </svg>
  )
}

function InstagramIcon({ size = 16 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="2" y="2" width="20" height="20" rx="5" ry="5" />
      <path d="M16 11.37A4 4 0 1 1 12.63 8 4 4 0 0 1 16 11.37z" />
      <line x1="17.5" y1="6.5" x2="17.51" y2="6.5" />
    </svg>
  )
}

// ─── Footer ───────────────────────────────────────────────────────────────────
// Requirements: 12.1–12.6, 11.3–11.5

const RC_NUMBER = 'RC: 1234567'

// Column 2 — Learn More
const LEARN_MORE_LINKS = [
  { label: 'About Us', href: '#' },
  { label: 'How It Works', href: '#' },
  { label: 'Pricing', href: '#' },
  { label: 'Blog', href: '#' },
  { label: 'Contact Us', href: '#' },
]

// Column 3 — For Employers
const EMPLOYER_LINKS = [
  { label: 'Post a Job', href: '#' },
  { label: 'How It Works', href: '#' },
  { label: 'Pricing', href: '#' },
  { label: 'Success Stories', href: '#' },
  { label: 'Contact Sales', href: '#' },
]

// Column 4 — For Candidates
const CANDIDATE_LINKS = [
  { label: 'Browse Jobs', href: '#' },
  { label: 'Create Profile', href: '#' },
  { label: 'Career Resources', href: '#' },
  { label: 'Interview Tips', href: '#' },
  { label: 'Salary Guide', href: '#' },
]

// Column 5 — Connect (Req 12.4)
const SOCIAL_LINKS = [
  { label: 'LinkedIn', href: 'https://linkedin.com', Icon: LinkedInIcon },
  { label: 'Twitter / X', href: 'https://twitter.com', Icon: TwitterXIcon },
  { label: 'Instagram', href: 'https://instagram.com', Icon: InstagramIcon },
]

// Newsletter zod schema (Req 11.4)
const newsletterSchema = z.object({
  email: z.string().min(1, 'Email is required').email('Please enter a valid email address'),
})

function FooterHeading({ children }) {
  return (
    <h3 className="text-white font-semibold text-sm uppercase tracking-wider mb-4">
      {children}
    </h3>
  )
}

function FooterLink({ href, children }) {
  return (
    <li>
      <Link
        to={href}
        className="text-sm transition-colors"
        style={{ color: 'rgba(255,255,255,0.6)' }}
        onMouseEnter={(e) => (e.currentTarget.style.color = '#ffffff')}
        onMouseLeave={(e) => (e.currentTarget.style.color = 'rgba(255,255,255,0.6)')}
      >
        {children}
      </Link>
    </li>
  )
}

// Newsletter signup sub-component (Req 11.3, 11.4, 11.5)
function NewsletterSignup() {
  const [submitted, setSubmitted] = useState(false)

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm({
    resolver: zodResolver(newsletterSchema),
  })

  const onSubmit = (data) => {
    console.log('Newsletter signup:', data)
    setSubmitted(true)
    reset()
  }

  return (
    <div>
      <FooterHeading>Stay Updated</FooterHeading>
      {submitted ? (
        <p
          className="text-sm"
          style={{ color: 'rgba(255,255,255,0.8)' }}
          role="status"
          data-testid="newsletter-success"
        >
          Thanks for subscribing!
        </p>
      ) : (
        <form onSubmit={handleSubmit(onSubmit)} noValidate aria-label="Newsletter signup">
          <div className="flex flex-col sm:flex-row gap-2">
            <div className="flex-1 min-w-0">
              <input
                type="email"
                placeholder="Your email address"
                aria-label="Email address for newsletter"
                aria-invalid={!!errors.email}
                aria-describedby={errors.email ? 'newsletter-email-error' : undefined}
                className="w-full rounded-md px-3 py-2 text-sm text-gray-900 bg-white placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-amber-400"
                data-testid="newsletter-email-input"
                {...register('email')}
              />
            </div>
            <button
              type="submit"
              className="rounded-md px-4 py-2 text-sm font-semibold text-white transition-colors whitespace-nowrap"
              style={{ background: '#F59E0B' }}
              onMouseEnter={(e) => (e.currentTarget.style.background = '#D97706')}
              onMouseLeave={(e) => (e.currentTarget.style.background = '#F59E0B')}
            >
              Subscribe
            </button>
          </div>
          {errors.email && (
            <p
              id="newsletter-email-error"
              className="mt-1 text-xs"
              style={{ color: '#FCA5A5' }}
              role="alert"
              data-testid="newsletter-email-error"
            >
              {errors.email.message}
            </p>
          )}
        </form>
      )}
    </div>
  )
}

export default function Footer({ onBookConsultation }) {
  return (
    <footer
      style={{ background: '#1A1A2E' }}
      aria-label="Site footer"
    >
      {/* ── Main grid ── */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        {/*
          Desktop: 5-column grid (Req 12.5)
          Mobile: 2-column grid, brand column full-width (Req 12.6)
        */}
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-10">

          {/* Column 1 — Brand (Req 12.1) — full width on mobile */}
          <div className="col-span-2 lg:col-span-1">
            {/* Logo + wordmark */}
            <div className="flex items-center gap-2 mb-3">
              <ElevareLogo size={28} variant="white" />
              <span className="font-bold text-white tracking-widest text-sm uppercase">
                ELEVARE
              </span>
            </div>

            {/* Tagline */}
            <p className="text-sm leading-relaxed mb-2" style={{ color: 'rgba(255,255,255,0.6)' }}>
              Connecting exceptional talent with ambitious companies.
            </p>

            {/* RC Number (Req 12.1) */}
            <p
              className="text-xs mb-5"
              style={{ color: 'rgba(255,255,255,0.4)' }}
              data-testid="footer-rc-number"
            >
              {RC_NUMBER}
            </p>

            {/* Book a Consultation CTA (Req 12.3) */}
            <button
              type="button"
              onClick={onBookConsultation}
              className="rounded-md px-4 py-2 text-sm font-semibold text-white transition-colors"
              style={{ background: '#F59E0B' }}
              onMouseEnter={(e) => (e.currentTarget.style.background = '#D97706')}
              onMouseLeave={(e) => (e.currentTarget.style.background = '#F59E0B')}
              data-testid="footer-book-consultation"
            >
              Book a Consultation
            </button>
          </div>

          {/* Column 2 — Learn More (Req 12.2) */}
          <div>
            <FooterHeading>Learn More</FooterHeading>
            <ul className="space-y-3">
              {LEARN_MORE_LINKS.map((link) => (
                <FooterLink key={link.label} href={link.href}>
                  {link.label}
                </FooterLink>
              ))}
            </ul>
          </div>

          {/* Column 3 — For Employers (Req 12.2) */}
          <div>
            <FooterHeading>For Employers</FooterHeading>
            <ul className="space-y-3">
              {EMPLOYER_LINKS.map((link) => (
                <FooterLink key={link.label} href={link.href}>
                  {link.label}
                </FooterLink>
              ))}
            </ul>
          </div>

          {/* Column 4 — For Candidates (Req 12.2) */}
          <div>
            <FooterHeading>For Candidates</FooterHeading>
            <ul className="space-y-3">
              {CANDIDATE_LINKS.map((link) => (
                <FooterLink key={link.label} href={link.href}>
                  {link.label}
                </FooterLink>
              ))}
            </ul>
          </div>

          {/* Column 5 — Connect + Newsletter (Req 12.2, 12.4, 11.3) */}
          <div className="col-span-2 lg:col-span-1 space-y-8">
            {/* Social links (Req 12.4) */}
            <div>
              <FooterHeading>Connect</FooterHeading>
              <ul className="space-y-3">
                {SOCIAL_LINKS.map(({ label, href, Icon }) => (
                  <li key={label}>
                    <a
                      href={href}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-2 text-sm transition-colors"
                      style={{ color: 'rgba(255,255,255,0.6)' }}
                      onMouseEnter={(e) => (e.currentTarget.style.color = '#ffffff')}
                      onMouseLeave={(e) => (e.currentTarget.style.color = 'rgba(255,255,255,0.6)')}
                      aria-label={label}
                      data-testid={`social-link-${label.toLowerCase().replace(/\s*\/\s*x$/i, '').trim()}`}
                    >
                      <Icon size={16} aria-hidden="true" />
                      {label}
                    </a>
                  </li>
                ))}

                {/* Email */}
                <li>
                  <a
                    href="mailto:info@elevare.com.ng"
                    className="flex items-center gap-2 text-sm transition-colors"
                    style={{ color: 'rgba(255,255,255,0.6)' }}
                    onMouseEnter={(e) => (e.currentTarget.style.color = '#ffffff')}
                    onMouseLeave={(e) => (e.currentTarget.style.color = 'rgba(255,255,255,0.6)')}
                  >
                    <Mail size={16} aria-hidden="true" />
                    info@elevare.com.ng
                  </a>
                </li>
              </ul>
            </div>

            {/* Newsletter signup (Req 11.3, 11.4, 11.5) */}
            <NewsletterSignup />
          </div>

        </div>
      </div>

      {/* ── Bottom bar ── */}
      <div
        className="border-t"
        style={{ borderColor: 'rgba(255,255,255,0.1)' }}
      >
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-5 flex flex-col sm:flex-row items-center justify-between gap-3">
          <p className="text-xs" style={{ color: 'rgba(255,255,255,0.4)' }}>
            © 2025 Elevare Human Solutions Ltd. All rights reserved.
          </p>
          <div className="flex items-center gap-4">
            <Link
              to="#"
              className="text-xs transition-colors"
              style={{ color: 'rgba(255,255,255,0.4)' }}
              onMouseEnter={(e) => (e.currentTarget.style.color = 'rgba(255,255,255,0.8)')}
              onMouseLeave={(e) => (e.currentTarget.style.color = 'rgba(255,255,255,0.4)')}
            >
              Privacy Policy
            </Link>
            <Link
              to="#"
              className="text-xs transition-colors"
              style={{ color: 'rgba(255,255,255,0.4)' }}
              onMouseEnter={(e) => (e.currentTarget.style.color = 'rgba(255,255,255,0.8)')}
              onMouseLeave={(e) => (e.currentTarget.style.color = 'rgba(255,255,255,0.4)')}
            >
              Terms
            </Link>
          </div>
        </div>
      </div>
    </footer>
  )
}
