import { useState, useEffect, useRef } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { ChevronDown, Menu, X, User, LogOut, LayoutDashboard } from 'lucide-react'
import { useAuth, getPostAuthRedirect } from '@/context/AuthContext'
import { Button } from '@/components/ui/button'
import ElevareLogo from '@/components/ui/ElevareLogo'

// ─── Dropdown data ────────────────────────────────────────────────────────────

const EMPLOYERS_ITEMS = [
  { label: 'Post a Job', href: '/employer/jobs/new' },
  { label: 'How It Works', href: '#' },
  { label: 'Pricing', href: '#' },
  { label: 'Contact Sales', href: '#' },
]

const CANDIDATES_ITEMS = [
  { label: 'Browse Jobs', href: '/jobs' },
  { label: 'How It Works', href: '#' },
  { label: 'Career Resources', href: '#' },
  { label: 'Create Profile', href: '#' },
]

// ─── Dropdown panel (shared) ──────────────────────────────────────────────────

function DropdownPanel({ items }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      transition={{ duration: 0.18, ease: 'easeOut' }}
      className="absolute top-full left-0 mt-2 w-48 bg-white rounded-lg shadow-lg border border-border py-1 z-50"
      role="menu"
    >
      {items.map((item) => (
        <Link
          key={item.label}
          to={item.href}
          className="block px-4 py-2 text-sm text-text hover:bg-surface-muted hover:text-brand-blue transition-colors focus:outline-none focus-visible:bg-surface-muted focus-visible:text-brand-blue"
          role="menuitem"
        >
          {item.label}
        </Link>
      ))}
    </motion.div>
  )
}

// ─── Nav dropdown trigger ─────────────────────────────────────────────────────

function NavDropdown({ label, items, isOpen, onOpen, onClose }) {
  const wrapperRef = useRef(null)

  return (
    <div
      ref={wrapperRef}
      className="relative"
      onMouseEnter={onOpen}
      onMouseLeave={onClose}
    >
      <button
        className="flex items-center gap-1 text-sm font-medium text-text hover:text-brand-blue transition-colors py-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-blue rounded"
        aria-haspopup="true"
        aria-expanded={isOpen}
        onFocus={onOpen}
      >
        {label}
        <ChevronDown
          size={14}
          className={`transition-transform duration-200 ${isOpen ? 'rotate-180' : ''}`}
        />
      </button>
      <AnimatePresence>
        {isOpen && <DropdownPanel items={items} />}
      </AnimatePresence>
    </div>
  )
}

// ─── Avatar dropdown ──────────────────────────────────────────────────────────

function AvatarDropdown({ user, onLogout }) {
  const [open, setOpen] = useState(false)
  const ref = useRef(null)
  const navigate = useNavigate()

  // Close on outside click
  useEffect(() => {
    if (!open) return
    const handler = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  const initials = user?.first_name
    ? user.first_name[0].toUpperCase()
    : user?.email?.[0]?.toUpperCase() ?? 'U'

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2 text-sm font-medium text-text hover:text-brand-blue transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-blue rounded-full"
        aria-haspopup="true"
        aria-expanded={open}
        aria-label="User menu"
      >
        <span className="w-8 h-8 rounded-full bg-brand-blue text-white flex items-center justify-center text-xs font-bold">
          {initials}
        </span>
        <ChevronDown size={14} className={`transition-transform duration-200 ${open ? 'rotate-180' : ''}`} />
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.18, ease: 'easeOut' }}
            className="absolute top-full right-0 mt-2 w-44 bg-white rounded-lg shadow-lg border border-border py-1 z-50"
            role="menu"
          >
            <button
              onClick={() => { setOpen(false); navigate(getPostAuthRedirect(user)) }}
              className="flex items-center gap-2 w-full px-4 py-2 text-sm text-text hover:bg-surface-muted hover:text-brand-blue transition-colors focus:outline-none focus-visible:bg-surface-muted"
              role="menuitem"
            >
              <LayoutDashboard size={14} /> Dashboard
            </button>
            <button
              onClick={() => { setOpen(false); onLogout() }}
              className="flex items-center gap-2 w-full px-4 py-2 text-sm text-text hover:bg-surface-muted hover:text-red-600 transition-colors focus:outline-none focus-visible:bg-surface-muted"
              role="menuitem"
            >
              <LogOut size={14} /> Sign Out
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

// ─── Mobile accordion item (for expandable sub-menus in drawer) ──────────────

function MobileAccordionItem({ label, items, onClose }) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div className="border-b border-border/50">
      <button
        className="flex items-center justify-between w-full py-3 text-base font-medium text-text hover:text-brand-blue transition-colors focus-visible:outline-none focus-visible:text-brand-blue"
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
      >
        {label}
        <ChevronDown
          size={16}
          className={`transition-transform duration-200 ${expanded ? 'rotate-180' : ''}`}
        />
      </button>
      <AnimatePresence initial={false}>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2, ease: 'easeInOut' }}
            className="overflow-hidden"
          >
            <div className="pb-2 pl-4 space-y-1">
              {items.map((item) => (
                <a
                  key={item.label}
                  href={item.href}
                  onClick={onClose}
                  className="block py-2 text-sm text-text-muted hover:text-brand-blue transition-colors focus-visible:outline-none focus-visible:text-brand-blue"
                >
                  {item.label}
                </a>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

// ─── Mobile drawer ────────────────────────────────────────────────────────────

function MobileDrawer({ isOpen, onClose, user, onLogout, onBookConsultation }) {
  const navigate = useNavigate()

  // Prevent body scroll when drawer is open
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden'
    } else {
      document.body.style.overflow = ''
    }
    return () => { document.body.style.overflow = '' }
  }, [isOpen])

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 bg-black/40 z-40"
            onClick={onClose}
            aria-hidden="true"
          />

          {/* Drawer panel */}
          <motion.div
            initial={{ x: '-100%' }}
            animate={{ x: 0 }}
            exit={{ x: '-100%' }}
            transition={{ duration: 0.28, ease: 'easeInOut' }}
            className="fixed inset-y-0 left-0 w-full max-w-xs bg-white z-50 flex flex-col shadow-xl"
            role="dialog"
            aria-modal="true"
            aria-label="Navigation menu"
          >
            {/* Drawer header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-border">
              <Link to="/" onClick={onClose} className="flex items-center gap-2">
                <ElevareLogo size={28} />
                <span className="font-bold text-brand-blue tracking-widest text-sm uppercase">Elevare</span>
              </Link>
              <button
                onClick={onClose}
                className="p-2 rounded-md text-text-muted hover:text-text hover:bg-surface-muted transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-blue"
                aria-label="Close menu"
              >
                <X size={20} />
              </button>
            </div>

            {/* Nav links */}
            <nav className="flex-1 overflow-y-auto px-6 py-4 space-y-0" aria-label="Mobile navigation">
              {/* Expandable: For Employers */}
              <MobileAccordionItem
                label="For Employers"
                items={EMPLOYERS_ITEMS}
                onClose={onClose}
              />
              {/* Expandable: For Candidates */}
              <MobileAccordionItem
                label="For Candidates"
                items={CANDIDATES_ITEMS}
                onClose={onClose}
              />
              {['About Us', 'How It Works', 'Contact Us'].map((label) => (
                <a
                  key={label}
                  href="#"
                  onClick={onClose}
                  className="block py-3 text-base font-medium text-text hover:text-brand-blue border-b border-border/50 transition-colors focus-visible:outline-none focus-visible:text-brand-blue"
                >
                  {label}
                </a>
              ))}

              {/* Book a Consultation CTA — always visible in mobile drawer */}
              {onBookConsultation && (
                <div className="pt-4">
                  <Button
                    className="w-full bg-brand-blue hover:bg-brand-blue/90 text-white border-0"
                    onClick={() => { onClose(); onBookConsultation() }}
                  >
                    Book a Consultation
                  </Button>
                </div>
              )}
            </nav>

            {/* Bottom auth area */}
            <div className="px-6 py-6 border-t border-border space-y-3">
              {user ? (
                <>
                  <button
                    onClick={() => { onClose(); navigate(getPostAuthRedirect(user)) }}
                    className="flex items-center gap-2 w-full py-2 text-sm font-medium text-text hover:text-brand-blue transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-blue rounded"
                  >
                    <LayoutDashboard size={16} /> Dashboard
                  </button>
                  <button
                    onClick={() => { onClose(); onLogout() }}
                    className="flex items-center gap-2 w-full py-2 text-sm font-medium text-red-600 hover:text-red-700 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-400 rounded"
                  >
                    <LogOut size={16} /> Sign Out
                  </button>
                </>
              ) : (
                <>
                  <Link to="/login" onClick={onClose} className="block">
                    <Button variant="outline" className="w-full">Login</Button>
                  </Link>
                  <Link to="/register" onClick={onClose} className="block">
                    <Button className="w-full bg-brand-amber hover:bg-brand-amber-dark text-white border-0">Register</Button>
                  </Link>
                </>
              )}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}

// ─── Navbar ───────────────────────────────────────────────────────────────────

export default function Navbar({ onBookConsultation }) {
  const { user, logout } = useAuth()
  const [scrolled, setScrolled] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)
  const [employersOpen, setEmployersOpen] = useState(false)
  const [candidatesOpen, setCandidatesOpen] = useState(false)
  const navRef = useRef(null)

  // Scroll shadow
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 10)
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  // Close dropdowns on outside click
  useEffect(() => {
    const handler = (e) => {
      if (navRef.current && !navRef.current.contains(e.target)) {
        setEmployersOpen(false)
        setCandidatesOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  return (
    <>
      <header
        ref={navRef}
        className={`fixed top-0 left-0 right-0 z-30 bg-white transition-shadow duration-200 ${
          scrolled ? 'shadow-md' : 'shadow-none'
        }`}
        role="banner"
      >
        <nav
          className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between"
          aria-label="Main navigation"
        >
          {/* Logo + wordmark */}
          <Link
            to="/"
            className="flex items-center gap-2 flex-shrink-0 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-blue rounded"
            aria-label="Elevare home"
          >
            <ElevareLogo size={32} />
            <span className="font-bold text-brand-blue tracking-widest text-sm uppercase">
              Elevare
            </span>
          </Link>

          {/* Centre nav — desktop only */}
          <div className="hidden md:flex items-center gap-3 lg:gap-6">
            <NavDropdown
              label="For Employers"
              items={EMPLOYERS_ITEMS}
              isOpen={employersOpen}
              onOpen={() => { setEmployersOpen(true); setCandidatesOpen(false) }}
              onClose={() => setEmployersOpen(false)}
            />
            <NavDropdown
              label="For Candidates"
              items={CANDIDATES_ITEMS}
              isOpen={candidatesOpen}
              onOpen={() => { setCandidatesOpen(true); setEmployersOpen(false) }}
              onClose={() => setCandidatesOpen(false)}
            />
            {['About Us', 'How It Works', 'Contact Us'].map((label) => (
              <a
                key={label}
                href="#"
                className="text-sm font-medium text-text hover:text-brand-blue transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-blue rounded py-1 whitespace-nowrap"
              >
                {label}
              </a>
            ))}
          </div>

          {/* Right side — desktop only */}
          <div className="hidden md:flex items-center gap-2 lg:gap-3">
            {onBookConsultation && (
              <Button
                size="sm"
                className="bg-brand-blue hover:bg-brand-blue/90 text-white border-0 whitespace-nowrap text-xs lg:text-sm px-3 lg:px-4"
                onClick={onBookConsultation}
              >
                Book a Consultation
              </Button>
            )}
            {user ? (
              <AvatarDropdown user={user} onLogout={logout} />
            ) : (
              <>
                <Link to="/login">
                  <Button variant="ghost" size="sm" className="text-xs lg:text-sm px-2 lg:px-3">Login</Button>
                </Link>
                <Link to="/register">
                  <Button
                    size="sm"
                    className="bg-brand-amber hover:bg-brand-amber-dark text-white border-0 text-xs lg:text-sm px-3 lg:px-4"
                  >
                    Register
                  </Button>
                </Link>
              </>
            )}
          </div>

          {/* Hamburger — mobile only */}
          <button
            className="md:hidden p-2 rounded-md text-text-muted hover:text-text hover:bg-surface-muted transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-blue"
            onClick={() => setMobileOpen(true)}
            aria-label="Open navigation menu"
            aria-expanded={mobileOpen}
            aria-controls="mobile-drawer"
          >
            <Menu size={22} />
          </button>
        </nav>
      </header>

      {/* Mobile drawer */}
      <MobileDrawer
        isOpen={mobileOpen}
        onClose={() => setMobileOpen(false)}
        user={user}
        onLogout={logout}
        onBookConsultation={onBookConsultation}
      />
    </>
  )
}
