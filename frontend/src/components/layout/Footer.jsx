import { Link } from 'react-router-dom'
import { Globe, Share2, AtSign, Mail } from 'lucide-react'
import ElevareLogo from '@/components/ui/ElevareLogo'

// ─── Footer ───────────────────────────────────────────────────────────────────
// Requirements: 11.1 – 11.7
// Dark background (#1A1A2E), five-column grid on desktop, bottom bar.

// Column 2 — Learn More (Req 11.3)
const LEARN_MORE_LINKS = [
  { label: 'About Us', href: '#' },
  { label: 'How It Works', href: '#' },
  { label: 'Pricing', href: '#' },
  { label: 'Blog', href: '#' },
  { label: 'Contact Us', href: '#' },
]

// Column 3 — For Employers (Req 11.4)
const EMPLOYER_LINKS = [
  { label: 'Post a Job', href: '#' },
  { label: 'How It Works', href: '#' },
  { label: 'Pricing', href: '#' },
  { label: 'Success Stories', href: '#' },
  { label: 'Contact Sales', href: '#' },
]

// Column 4 — For Candidates (Req 11.5)
const CANDIDATE_LINKS = [
  { label: 'Browse Jobs', href: '#' },
  { label: 'Create Profile', href: '#' },
  { label: 'Career Resources', href: '#' },
  { label: 'Interview Tips', href: '#' },
  { label: 'Salary Guide', href: '#' },
]

// Column 5 — Connect (Req 11.6)
const SOCIAL_LINKS = [
  { label: 'LinkedIn', href: '#', Icon: Globe },
  { label: 'Twitter / X', href: '#', Icon: Share2 },
  { label: 'Instagram', href: '#', Icon: AtSign },
]

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

export default function Footer() {
  return (
    <footer
      style={{ background: '#1A1A2E' }}
      aria-label="Site footer"
    >
      {/* ── Main grid ── */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        {/* Five-column grid: 2 cols mobile → 3 cols tablet → 5 cols desktop (Req 11.1) */}
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-10">

          {/* Column 1 — Brand (Req 11.2) — full width on mobile */}
          <div className="col-span-2 md:col-span-3 lg:col-span-1">
            {/* Logo + wordmark in white */}
            <div className="flex items-center gap-2 mb-4">
              <ElevareLogo size={28} variant="white" />
              <span className="font-bold text-white tracking-widest text-sm uppercase">
                ELEVARE
              </span>
            </div>

            {/* Tagline */}
            <p className="text-sm leading-relaxed mb-6" style={{ color: 'rgba(255,255,255,0.6)' }}>
              Connecting exceptional talent with ambitious companies.
            </p>


          </div>

          {/* Column 2 — Learn More (Req 11.3) */}
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

          {/* Column 3 — For Employers (Req 11.4) */}
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

          {/* Column 4 — For Candidates (Req 11.5) */}
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

          {/* Column 5 — Connect (Req 11.6) */}
          <div>
            <FooterHeading>Connect</FooterHeading>
            <ul className="space-y-3">
              {SOCIAL_LINKS.map(({ label, href, Icon }) => (
                <li key={label}>
                  <a
                    href={href}
                    className="flex items-center gap-2 text-sm transition-colors"
                    style={{ color: 'rgba(255,255,255,0.6)' }}
                    onMouseEnter={(e) => (e.currentTarget.style.color = '#ffffff')}
                    onMouseLeave={(e) => (e.currentTarget.style.color = 'rgba(255,255,255,0.6)')}
                    aria-label={label}
                  >
                    <Icon size={16} aria-hidden="true" />
                    {label}
                  </a>
                </li>
              ))}

              {/* Email link */}
              <li>
                <a
                  href="mailto:hello@elevarehuman.com"
                  className="flex items-center gap-2 text-sm transition-colors"
                  style={{ color: 'rgba(255,255,255,0.6)' }}
                  onMouseEnter={(e) => (e.currentTarget.style.color = '#ffffff')}
                  onMouseLeave={(e) => (e.currentTarget.style.color = 'rgba(255,255,255,0.6)')}
                >
                  <Mail size={16} aria-hidden="true" />
                  hello@elevarehuman.com
                </a>
              </li>
            </ul>
          </div>

        </div>
      </div>

      {/* ── Bottom bar (Req 11.7) ── */}
      <div
        className="border-t"
        style={{ borderColor: 'rgba(255,255,255,0.1)' }}
      >
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-5 flex flex-col sm:flex-row items-center justify-between gap-3">
          {/* Left — copyright */}
          <p className="text-xs" style={{ color: 'rgba(255,255,255,0.4)' }}>
            © 2025 Elevare Human Solutions Ltd. All rights reserved.
          </p>

          {/* Right — Privacy Policy + Terms */}
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
