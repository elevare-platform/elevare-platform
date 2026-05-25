import {
  Users,
  Search,
  FileText,
  GraduationCap,
  BookOpen,
  Award,
  ClipboardList,
  Briefcase,
  ArrowRight,
} from 'lucide-react'

// ─── Services data (Requirements 3.1, 3.2) ───────────────────────────────────
// 8 services across 3 clusters

const SERVICES = [
  // Cluster 1: Core HR & Recruitment
  {
    id: 'talent-acquisition',
    cluster: 'Core HR & Recruitment',
    icon: Search,
    name: 'Talent Acquisition',
    description: 'End-to-end recruitment from job brief to signed offer, powered by our vetted candidate pool.',
  },
  {
    id: 'hr-consulting',
    cluster: 'Core HR & Recruitment',
    icon: Users,
    name: 'HR Consulting',
    description: 'Strategic HR advisory to help you build policies, structures, and people processes that scale.',
  },
  {
    id: 'executive-search',
    cluster: 'Core HR & Recruitment',
    icon: Briefcase,
    name: 'Executive Search',
    description: 'Discreet, targeted search for C-suite and senior leadership roles across industries.',
  },
  // Cluster 2: Training & Development
  {
    id: 'learning-development',
    cluster: 'Training & Development',
    icon: GraduationCap,
    name: 'Learning & Development',
    description: 'Customised training programmes that upskill your workforce and drive measurable performance.',
  },
  {
    id: 'onboarding-programs',
    cluster: 'Training & Development',
    icon: BookOpen,
    name: 'Onboarding Programmes',
    description: 'Structured onboarding journeys that get new hires productive faster and reduce early attrition.',
  },
  {
    id: 'leadership-coaching',
    cluster: 'Training & Development',
    icon: Award,
    name: 'Leadership Coaching',
    description: 'One-on-one and group coaching to develop high-potential managers into confident leaders.',
  },
  // Cluster 3: Workforce Operations
  {
    id: 'payroll-compliance',
    cluster: 'Workforce Operations',
    icon: FileText,
    name: 'Payroll & Compliance',
    description: 'Accurate, timely payroll processing with full compliance to Nigerian labour regulations.',
  },
  {
    id: 'workforce-planning',
    cluster: 'Workforce Operations',
    icon: ClipboardList,
    name: 'Workforce Planning',
    description: 'Data-driven headcount planning and org design to align your people strategy with business goals.',
  },
]

// ─── Cluster tag colours ──────────────────────────────────────────────────────

const CLUSTER_STYLES = {
  'Core HR & Recruitment': { bg: '#fffbeb', color: '#b45309' },
  'Training & Development': { bg: '#f0fdf4', color: '#15803d' },
  'Workforce Operations': { bg: '#eff6ff', color: '#1d4ed8' },
}

// ─── ServiceCard ──────────────────────────────────────────────────────────────

function ServiceCard({ service }) {
  const Icon = service.icon
  const clusterStyle = CLUSTER_STYLES[service.cluster]

  return (
    <article
      style={{
        background: '#ffffff',
        borderRadius: '0.75rem',
        border: '1px solid #e2e8f0',
        boxShadow: '0 1px 8px rgba(0,0,0,0.05)',
        padding: '1.5rem',
        display: 'flex',
        flexDirection: 'column',
        gap: '0.75rem',
        transition: 'box-shadow 0.2s, transform 0.2s',
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.boxShadow = '0 8px 24px rgba(26,77,143,0.12)'
        e.currentTarget.style.transform = 'translateY(-2px)'
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.boxShadow = '0 1px 8px rgba(0,0,0,0.05)'
        e.currentTarget.style.transform = 'translateY(0)'
      }}
    >
      {/* Icon */}
      <div
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          width: 44,
          height: 44,
          borderRadius: '0.625rem',
          background: '#e8f0fb',
          flexShrink: 0,
        }}
        aria-hidden="true"
      >
        <Icon size={22} color="#1A4D8F" strokeWidth={1.75} />
      </div>

      {/* Cluster label (amber/coloured tag) — Requirements 3.2 */}
      <span
        style={{
          display: 'inline-block',
          fontSize: '0.6875rem',
          fontWeight: 600,
          letterSpacing: '0.06em',
          textTransform: 'uppercase',
          padding: '2px 8px',
          borderRadius: 999,
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
          fontSize: '1rem',
          fontWeight: 700,
          color: '#1e293b',
          lineHeight: 1.3,
        }}
      >
        {service.name}
      </h3>

      {/* One-line description */}
      <p
        style={{
          margin: 0,
          fontSize: '0.875rem',
          color: '#64748b',
          lineHeight: 1.6,
          flexGrow: 1,
        }}
      >
        {service.description}
      </p>

      {/* Arrow link — Requirements 3.3 */}
      <a
        href="#"
        aria-label={`Learn more about ${service.name}`}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '0.25rem',
          fontSize: '0.875rem',
          fontWeight: 600,
          color: '#1A4D8F',
          textDecoration: 'none',
          marginTop: 'auto',
          transition: 'gap 0.2s',
        }}
        onMouseEnter={(e) => (e.currentTarget.style.gap = '0.5rem')}
        onMouseLeave={(e) => (e.currentTarget.style.gap = '0.25rem')}
      >
        Learn more <ArrowRight size={14} strokeWidth={2} aria-hidden="true" />
      </a>
    </article>
  )
}

// ─── ServicesSection ──────────────────────────────────────────────────────────

export default function ServicesSection() {
  return (
    <section
      aria-label="Our services"
      style={{ background: '#F8F9FA', padding: '5rem 1rem' }}
    >
      <div style={{ maxWidth: '72rem', margin: '0 auto' }}>

        {/* Section header */}
        <div style={{ textAlign: 'center', marginBottom: '3rem' }}>
          <p
            style={{
              margin: '0 0 0.5rem',
              fontSize: '0.8125rem',
              fontWeight: 600,
              color: '#E87722',
              letterSpacing: '0.08em',
              textTransform: 'uppercase',
            }}
          >
            What We Do
          </p>
          <h2
            style={{
              margin: '0 0 1rem',
              fontSize: 'clamp(1.625rem, 3vw, 2.125rem)',
              fontWeight: 800,
              color: '#1e293b',
              lineHeight: 1.2,
            }}
          >
            Comprehensive HR Solutions
          </h2>
          <p
            style={{
              margin: 0,
              fontSize: '1rem',
              color: '#64748b',
              maxWidth: '36rem',
              marginLeft: 'auto',
              marginRight: 'auto',
              lineHeight: 1.6,
            }}
          >
            From finding your next hire to developing your entire workforce, Elevare covers every stage of the talent lifecycle.
          </p>
        </div>

        {/* Services grid — Requirements 3.4 (mobile: 1 col), 3.5 (desktop: 3 col) */}
        <div className="services-grid">
          {SERVICES.map((service) => (
            <ServiceCard key={service.id} service={service} />
          ))}
        </div>

        {/* View All Services link */}
        <div style={{ textAlign: 'center', marginTop: '2.5rem' }}>
          <a
            href="#"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.375rem',
              fontSize: '0.9375rem',
              fontWeight: 600,
              color: '#1A4D8F',
              textDecoration: 'none',
              borderBottom: '2px solid #1A4D8F',
              paddingBottom: '2px',
              transition: 'color 0.2s, border-color 0.2s',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.color = '#E87722'
              e.currentTarget.style.borderColor = '#E87722'
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.color = '#1A4D8F'
              e.currentTarget.style.borderColor = '#1A4D8F'
            }}
          >
            View All Services <ArrowRight size={16} strokeWidth={2} aria-hidden="true" />
          </a>
        </div>

      </div>
    </section>
  )
}
