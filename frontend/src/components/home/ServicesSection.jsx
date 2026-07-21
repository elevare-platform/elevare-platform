import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  Users,
  Search,
  FileText,
  Layers,
  Cpu,
  GraduationCap,
  ArrowRight,
} from 'lucide-react'
import { useIntersectionObserver } from '@/hooks/useIntersectionObserver'

// ─── Homepage Featured Services ──────────────────────────────────────────────
const SERVICES = [
  {
    id: 'hr-consulting',
    cluster: 'Strategy & Advisory',
    icon: Users,
    name: 'HR Consulting & Advisory',
    description: 'Strategic guidance on HR policy, organizational structures, and scalable workforce solutions.',
  },
  {
    id: 'recruitment-executive-search',
    cluster: 'Talent Acquisition',
    icon: Search,
    name: 'Recruitment & Executive Search',
    description: 'End-to-end talent search and C-suite placements powered by our extensive professional networks.',
  },
  {
    id: 'payroll-management',
    cluster: 'Workforce Operations',
    icon: FileText,
    name: 'Payroll Management',
    description: 'Accurate, timely, and compliant payroll administration tailored to local labor regulations.',
  },
  {
    id: 'staff-outsourcing',
    cluster: 'Workforce Operations',
    icon: Layers,
    name: 'Staff Outsourcing Services',
    description: 'Flexible staffing options and complete workforce management solutions to optimize operations.',
  },
  {
    id: 'workforce-automation',
    cluster: 'HR Technology',
    icon: Cpu,
    name: 'Workforce Automation Systems',
    description: 'Implementing custom HR systems to automate attendance, leave, performance, and real-time tracking.',
  },
  {
    id: 'corporate-training',
    cluster: 'Training & Development',
    icon: GraduationCap,
    name: 'Corporate Training Programs',
    description: 'Bespoke upskilling and professional development programs that elevate team capabilities and productivity.',
  },
]

// ─── Cluster tag colors ──────────────────────────────────────────────────────
const CLUSTER_STYLES = {
  'Strategy & Advisory':    { bg: '#e8f0fb', color: '#1A4D8F' },
  'Talent Acquisition':     { bg: '#fffbeb', color: '#b45309' },
  'Workforce Operations':   { bg: '#f0fdf4', color: '#15803d' },
  'HR Technology':          { bg: '#faf5ff', color: '#6b21a8' },
  'Training & Development': { bg: '#fef2f2', color: '#991b1b' },
}

// ─── Framer Motion card variants — staggered scroll-triggered reveal ──────────
const cardVariants = {
  hidden:  { opacity: 0, y: 28, scale: 0.97 },
  visible: (i) => ({
    opacity: 1,
    y: 0,
    scale: 1,
    transition: {
      duration: 0.5,
      delay: i * 0.08,
      ease: [0.16, 1, 0.3, 1],
    },
  }),
}

// ─── ServiceCard ──────────────────────────────────────────────────────────────
function ServiceCard({ service, index, isVisible }) {
  const Icon = service.icon
  const clusterStyle = CLUSTER_STYLES[service.cluster] || { bg: '#f1f5f9', color: '#334155' }

  return (
    <motion.article
      custom={index}
      variants={cardVariants}
      initial="hidden"
      animate={isVisible ? 'visible' : 'hidden'}
      className="svc-card group"
      style={{
        background: '#ffffff',
        borderRadius: '0.875rem',
        border: '1px solid #e2e8f0',
        padding: '2rem',
        display: 'flex',
        flexDirection: 'column',
        gap: '1rem',
        position: 'relative',
        overflow: 'hidden',
        boxShadow: '0 2px 8px rgba(0,0,0,0.04), 0 1px 3px rgba(0,0,0,0.03)',
      }}
    >
      {/* Top-edge accent bar — slides in on hover */}
      <span className="svc-card-accent" aria-hidden="true" />

      {/* Icon Wrapper */}
      <div
        className="svc-icon-wrap"
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          width: 52,
          height: 52,
          borderRadius: '0.75rem',
          background: '#e8f0fb',
          flexShrink: 0,
        }}
        aria-hidden="true"
      >
        <Icon
          size={24}
          className="svc-icon text-brand-blue"
          strokeWidth={2}
        />
      </div>

      {/* Cluster label */}
      <span
        style={{
          display: 'inline-block',
          fontSize: '0.72rem',
          fontWeight: 600,
          letterSpacing: '0.06em',
          textTransform: 'uppercase',
          padding: '4px 10px',
          borderRadius: '4px',
          background: clusterStyle.bg,
          color: clusterStyle.color,
          alignSelf: 'flex-start',
        }}
      >
        {service.cluster}
      </span>

      {/* Service name */}
      <h3
        style={{
          margin: 0,
          fontSize: '1.25rem',
          fontWeight: 700,
          color: '#1e293b',
          lineHeight: 1.3,
        }}
      >
        {service.name}
      </h3>

      {/* Description */}
      <p
        style={{
          margin: 0,
          fontSize: '0.925rem',
          color: '#64748b',
          lineHeight: 1.6,
          flexGrow: 1,
        }}
      >
        {service.description}
      </p>

      {/* Learn more link */}
      <Link
        to="/services"
        aria-label={`Learn more about ${service.name}`}
        className="svc-learn-more"
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          fontSize: '0.9rem',
          fontWeight: 600,
          color: '#1A4D8F',
          textDecoration: 'none',
          marginTop: '0.5rem',
        }}
      >
        <span className="svc-learn-more-text">Learn more</span>
        <ArrowRight
          size={16}
          strokeWidth={2.5}
          className="svc-learn-more-arrow"
          aria-hidden="true"
        />
      </Link>
    </motion.article>
  )
}

// ─── ServicesSection ──────────────────────────────────────────────────────────
export default function ServicesSection() {
  const [sectionRef, isVisible] = useIntersectionObserver({ threshold: 0.1, triggerOnce: true })

  return (
    <section
      ref={sectionRef}
      aria-label="Our services"
      style={{ background: '#F8F9FA', padding: '6.5rem 1rem' }}
    >
      <div style={{ maxWidth: '72rem', margin: '0 auto' }}>

        {/* Section header */}
        <div style={{ textAlign: 'center', marginBottom: '4.5rem' }}>
          <p
            style={{
              margin: '0 0 0.75rem',
              fontSize: '0.875rem',
              fontWeight: 700,
              color: '#E87722',
              letterSpacing: '0.12em',
              textTransform: 'uppercase',
            }}
          >
            What We Offer
          </p>
          <h2
            style={{
              margin: '0 0 1.25rem',
              fontSize: 'clamp(2rem, 4vw, 2.75rem)',
              fontWeight: 800,
              color: '#1e293b',
              lineHeight: 1.2,
              letterSpacing: '-0.02em',
              fontFamily: "'Inter', system-ui, sans-serif",
            }}
          >
            Workforce Solutions Built for Growth
          </h2>
          <p
            style={{
              margin: 0,
              fontSize: '1.125rem',
              color: '#64748b',
              maxWidth: '38rem',
              marginLeft: 'auto',
              marginRight: 'auto',
              lineHeight: 1.7,
            }}
          >
            Aligning talent strategy with modern operational structures. We deliver premium HR, recruiting, and automation services to scale your business.
          </p>
        </div>

        {/* Services grid */}
        <div className="services-grid">
          {SERVICES.map((service, i) => (
            <ServiceCard
              key={service.id}
              service={service}
              index={i}
              isVisible={isVisible}
            />
          ))}
        </div>

        {/* View All Services CTA */}
        <div style={{ textAlign: 'center', marginTop: '4rem' }} className="flex flex-col sm:flex-row justify-center items-center gap-3">
          <Link
            to="/services"
            className="inline-flex items-center gap-2 px-8 py-3.5 text-sm font-semibold text-white bg-brand-blue hover:bg-brand-blue-dark rounded-md transition-all shadow-md hover:shadow-lg hover:-translate-y-0.5 active:translate-y-0"
          >
            View All Services
            <ArrowRight size={16} strokeWidth={2.5} aria-hidden="true" />
          </Link>
          <Link
            to="/talent-pipeline"
            className="inline-flex items-center gap-2 px-8 py-3.5 text-sm font-semibold text-brand-blue bg-brand-blue-light hover:bg-brand-blue hover:text-white rounded-md transition-all shadow-sm hover:shadow-md"
          >
            Explore AI Recruiter
            <ArrowRight size={16} strokeWidth={2.5} aria-hidden="true" />
          </Link>
        </div>

      </div>
    </section>
  )
}
