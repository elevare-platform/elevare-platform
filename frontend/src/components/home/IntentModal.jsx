import { useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'

// ─── Icons ────────────────────────────────────────────────────────────────────

function EmployerIcon() {
  return (
    <svg width="32" height="32" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect x="3" y="7" width="18" height="12" rx="2" stroke="currentColor" strokeWidth="1.6" />
      <path d="M8 7V5.5C8 4.67157 8.67157 4 9.5 4H14.5C15.3284 4 16 4.67157 16 5.5V7" stroke="currentColor" strokeWidth="1.6" />
      <path d="M3 12H21" stroke="currentColor" strokeWidth="1.6" />
    </svg>
  )
}

function CandidateIcon() {
  return (
    <svg width="32" height="32" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
      <circle cx="12" cy="8" r="3.5" stroke="currentColor" strokeWidth="1.6" />
      <path d="M5 20c0-3.866 3.134-7 7-7s7 3.134 7 7" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  )
}

function CloseIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M18 6L6 18M6 6l12 12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  )
}

// ─── INTENT CONFIGS ───────────────────────────────────────────────────────────

const INTENTS = {
  employer: {
    icon: <EmployerIcon />,
    iconColor: '#1a4d8f',
    iconBg: 'rgba(26, 77, 143, 0.12)',
    badge: 'Employer Portal',
    badgeColor: '#1a4d8f',
    title: "You're entering the Employer Portal",
    description:
      "Elevare's employer platform gives you access to talent acquisition, workforce transformation advisory, and recruitment consulting. You'll complete a brief company profile to get started, including a KYC step to verify your organisation.",
    features: [
      'Search and browse a curated talent pool',
      'AI-suggested candidate matches for your roles',
      'CV parsing and automated candidate scoring',
    ],
    primaryLabel: 'Continue as Employer →',
    primaryRoute: '/register',
    switchLabel: "I'm looking for a job instead",
    switchRoute: '/jobs',
  },
  candidate: {
    icon: <CandidateIcon />,
    iconColor: '#E87722',
    iconBg: 'rgba(232, 119, 34, 0.12)',
    badge: 'Candidate Portal',
    badgeColor: '#E87722',
    title: "You're entering the Candidate Portal",
    description:
      "Browse hundreds of roles across Africa, build your professional profile, and track every application in one place. Create your candidate account to get started.",
    features: [
      'Browse and apply to curated roles',
      'Build a standout professional profile',
      'Track applications in real time',
    ],
    primaryLabel: 'Continue as Candidate →',
    primaryRoute: '/jobs',
    switchLabel: "I'm an employer looking to hire",
    switchRoute: '/register',
  },
}

// ─── IntentModal ──────────────────────────────────────────────────────────────

/**
 * @param {{ intent: 'employer' | 'candidate' | null, onClose: () => void }} props
 */
export default function IntentModal({ intent, onClose }) {
  const navigate = useNavigate()
  const overlayRef = useRef(null)
  const config = intent ? INTENTS[intent] : null

  // Close on Escape
  useEffect(() => {
    if (!intent) return
    const handler = (e) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [intent, onClose])

  // Prevent body scroll while open
  useEffect(() => {
    if (intent) {
      document.body.style.overflow = 'hidden'
    } else {
      document.body.style.overflow = ''
    }
    return () => { document.body.style.overflow = '' }
  }, [intent])

  if (!config) return null

  const handlePrimary = () => {
    onClose()
    navigate(config.primaryRoute)
  }

  const handleSwitch = () => {
    onClose()
    navigate(config.switchRoute)
  }

  const handleOverlayClick = (e) => {
    if (e.target === overlayRef.current) onClose()
  }

  return (
    <div
      ref={overlayRef}
      className="intent-modal-overlay"
      role="dialog"
      aria-modal="true"
      aria-labelledby="intent-modal-title"
      onClick={handleOverlayClick}
    >
      <div className="intent-modal-card">

        {/* Close button */}
        <button
          className="intent-modal-close"
          onClick={onClose}
          aria-label="Close"
        >
          <CloseIcon />
        </button>

        {/* Icon + badge */}
        <div className="intent-modal-header">
          <div
            className="intent-modal-icon"
            style={{ color: config.iconColor, background: config.iconBg }}
          >
            {config.icon}
          </div>
          <span
            className="intent-modal-badge"
            style={{ color: config.badgeColor, background: config.iconBg }}
          >
            {config.badge}
          </span>
        </div>

        {/* Title */}
        <h2 id="intent-modal-title" className="intent-modal-title">
          {config.title}
        </h2>

        {/* Description */}
        <p className="intent-modal-description">{config.description}</p>

        {/* Feature list */}
        <ul className="intent-modal-features" aria-label="What you get">
          {config.features.map((f) => (
            <li key={f} className="intent-modal-feature-item">
              <span
                className="intent-modal-feature-dot"
                style={{ background: config.iconColor }}
                aria-hidden="true"
              />
              {f}
            </li>
          ))}
        </ul>

        {/* Divider */}
        <div className="intent-modal-divider" />

        {/* Actions */}
        <div className="intent-modal-actions">
          <button
            id="intent-modal-primary-btn"
            className="intent-modal-btn-primary"
            style={{ background: config.iconColor }}
            onClick={handlePrimary}
          >
            {config.primaryLabel}
          </button>
          <button
            id="intent-modal-switch-btn"
            className="intent-modal-btn-switch"
            onClick={handleSwitch}
          >
            {config.switchLabel}
          </button>
        </div>

      </div>
    </div>
  )
}
