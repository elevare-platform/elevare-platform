import { ArrowRight } from 'lucide-react'

// ─── Articles data (Requirements 10.1) ───────────────────────────────────────
// 3 hardcoded article previews

export const ARTICLES = [
  {
    id: 'talent-retention-2025',
    category: 'HR Trends',
    title: '5 Talent Retention Strategies That Actually Work in 2025',
    date: '2025-04-10',
    href: '#',
  },
  {
    id: 'hiring-nigeria',
    category: 'Recruitment',
    title: 'How to Build a High-Performing Team in Nigeria\'s Competitive Job Market',
    date: '2025-03-22',
    href: '#',
  },
  {
    id: 'onboarding-remote',
    category: 'Workforce Ops',
    title: 'Remote Onboarding Done Right: A Practical Guide for HR Leaders',
    date: '2025-02-14',
    href: '#',
  },
]

// ─── Category tag colours ─────────────────────────────────────────────────────

const CATEGORY_STYLES = {
  'HR Trends':     { bg: '#fffbeb', color: '#b45309' },
  'Recruitment':   { bg: '#f0fdf4', color: '#15803d' },
  'Workforce Ops': { bg: '#eff6ff', color: '#1d4ed8' },
}

const DEFAULT_TAG_STYLE = { bg: '#f1f5f9', color: '#475569' }

// ─── Date formatter ───────────────────────────────────────────────────────────

function formatDate(isoDate) {
  return new Date(isoDate).toLocaleDateString('en-GB', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  })
}

// ─── ArticleCard ──────────────────────────────────────────────────────────────

function ArticleCard({ article }) {
  const tagStyle = CATEGORY_STYLES[article.category] ?? DEFAULT_TAG_STYLE

  return (
    <article
      className="premium-card"
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
      {/* Category tag — Requirements 10.1 */}
      <span
        style={{
          display: 'inline-block',
          fontSize: '0.6875rem',
          fontWeight: 600,
          letterSpacing: '0.06em',
          textTransform: 'uppercase',
          padding: '2px 8px',
          borderRadius: 999,
          background: tagStyle.bg,
          color: tagStyle.color,
          alignSelf: 'flex-start',
        }}
      >
        {article.category}
      </span>

      {/* Title — Requirements 10.1 */}
      <h3
        style={{
          margin: 0,
          fontSize: '1rem',
          fontWeight: 700,
          color: '#1e293b',
          lineHeight: 1.4,
          flexGrow: 1,
        }}
      >
        {article.title}
      </h3>

      {/* Publication date — Requirements 10.1 */}
      <time
        dateTime={article.date}
        style={{
          fontSize: '0.8125rem',
          color: '#94a3b8',
          fontWeight: 500,
        }}
      >
        {formatDate(article.date)}
      </time>

      {/* Read More link — Requirements 10.2 */}
      <a
        href={article.href}
        aria-label={`Read more about: ${article.title}`}
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
        Read More <ArrowRight size={14} strokeWidth={2} aria-hidden="true" />
      </a>
    </article>
  )
}

// ─── InsightsStrip ────────────────────────────────────────────────────────────

export default function InsightsStrip() {
  return (
    <section
      aria-label="Insights and articles"
      style={{ background: '#ffffff', padding: '5rem 1rem' }}
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
            Insights
          </p>
          <h2
            style={{
              margin: '0 0 1rem',
              fontSize: 'clamp(1.625rem, 3vw, 2.125rem)',
              fontWeight: 800,
              color: '#1e293b',
              lineHeight: 1.2,
              fontFamily: "'Inter', system-ui, sans-serif",
            }}
          >
            HR Expertise, Straight from the Source
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
            Practical guides, industry trends, and career advice from the Elevare team.
          </p>
        </div>

        {/* Articles grid — Requirements 10.3 (mobile: 1 col), 10.4 (desktop: 3 col) */}
        <div className="insights-grid">
          {ARTICLES.map((article) => (
            <ArticleCard key={article.id} article={article} />
          ))}
        </div>

      </div>
    </section>
  )
}
