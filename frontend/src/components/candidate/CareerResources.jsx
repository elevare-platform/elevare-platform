import { ArrowRight, FileText, Mic, DollarSign } from 'lucide-react'

/**
 * Static career resource cards.
 * Requirements 8.2 — exactly these 3 cards in this order.
 * Requirement 8.4 — no API calls; data is static.
 */
const RESOURCES = [
  {
    id: 'cv-writing',
    icon: FileText,
    title: 'How to Write a Winning CV',
    description: 'Practical tips to craft a CV that stands out and gets you noticed by top recruiters.',
    href: '/insights/cv-writing',
  },
  {
    id: 'interview-prep',
    icon: Mic,
    title: 'Interview Preparation Guide',
    description: 'Strategies and common questions to help you walk into any interview with confidence.',
    href: '/insights/interview-prep',
  },
  {
    id: 'salary-guide',
    icon: DollarSign,
    title: 'Salary Guide Nigeria 2025',
    description: 'Up-to-date salary benchmarks across industries to help you negotiate what you deserve.',
    href: '/insights/salary-guide',
  },
]

/**
 * ResourceCard — a single static career resource card.
 * Requirement 8.3 — icon, title, one-line description, "Read More →" link.
 */
function ResourceCard({ resource }) {
  const Icon = resource.icon

  return (
    <article className="flex flex-col gap-3 rounded-lg border border-border bg-surface p-5 transition-shadow hover:shadow-md">
      {/* Icon */}
      <div
        className="inline-flex items-center justify-center w-10 h-10 rounded-lg bg-brand-blue/10 flex-shrink-0"
        aria-hidden="true"
      >
        <Icon size={20} className="text-brand-blue" strokeWidth={1.75} />
      </div>

      {/* Title */}
      <h3 className="text-sm font-semibold text-text leading-snug">
        {resource.title}
      </h3>

      {/* One-line description */}
      <p className="text-sm text-text-muted leading-relaxed flex-1">
        {resource.description}
      </p>

      {/* "Read More →" link — Requirement 8.3 */}
      <a
        href={resource.href}
        className="inline-flex items-center gap-1 text-sm font-semibold text-brand-blue hover:text-brand-amber transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-blue rounded"
        aria-label={`Read more about ${resource.title}`}
      >
        Read More <ArrowRight size={13} strokeWidth={2} aria-hidden="true" />
      </a>
    </article>
  )
}

/**
 * CareerResources — renders exactly 3 static career resource cards.
 *
 * Requirements: 8.1, 8.2, 8.3, 8.4
 */
export function CareerResources() {
  return (
    <section aria-labelledby="career-resources-heading">
      <h2
        id="career-resources-heading"
        className="text-lg font-semibold text-text mb-4"
      >
        Career Resources
      </h2>

      {/* 3-column grid on md+, single column on mobile */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        {RESOURCES.map((resource) => (
          <ResourceCard key={resource.id} resource={resource} />
        ))}
      </div>
    </section>
  )
}
