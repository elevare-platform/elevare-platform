// Builds Google-compliant JobPosting JSON-LD (https://schema.org/JobPosting)
// from a job API response, for embedding via <script type="application/ld+json">.

const EMPLOYMENT_TYPE_MAP = {
  FULL_TIME: 'FULL_TIME',
  PART_TIME: 'PART_TIME',
  CONTRACT: 'CONTRACT',
  FREELANCE: 'CONTRACTOR',
  INTERNSHIP: 'INTERN',
}

const DEFAULT_COUNTRY = 'NG'

// job.location is free text like "Lagos, Nigeria" or "Lagos" — best-effort split
// into locality/region so Google can geo-match the posting.
function parseAddress(location) {
  if (!location) return null
  const parts = location.split(',').map((p) => p.trim()).filter(Boolean)
  if (parts.length === 0) return null
  const [addressLocality, addressRegion] = parts
  return {
    '@type': 'PostalAddress',
    addressLocality,
    ...(addressRegion ? { addressRegion } : {}),
    addressCountry: DEFAULT_COUNTRY,
  }
}

function buildJobLocation(job) {
  // Remote roles: Google wants jobLocationType TELECOMMUTE plus an explicit
  // applicantLocationRequirements instead of (or alongside) a jobLocation.
  if (job.work_model === 'REMOTE') {
    return {
      jobLocationType: 'TELECOMMUTE',
      applicantLocationRequirements: {
        '@type': 'Country',
        name: job.work_location === 'INTERNATIONAL' ? 'Worldwide' : 'Nigeria',
      },
    }
  }

  const address = parseAddress(job.location)
  if (!address) return {}
  return {
    jobLocation: {
      '@type': 'Place',
      address,
    },
  }
}

function buildBaseSalary(job) {
  if (job.salary_min == null && job.salary_max == null) return null
  const min = job.salary_min != null ? Number(job.salary_min) : Number(job.salary_max)
  const max = job.salary_max != null ? Number(job.salary_max) : Number(job.salary_min)
  return {
    '@type': 'MonetaryAmount',
    currency: 'NGN',
    value: {
      '@type': 'QuantitativeValue',
      minValue: min,
      maxValue: max,
      unitText: 'YEAR',
    },
  }
}

function buildDescriptionHtml(job) {
  // JobPosting.description must be non-empty HTML; escape then convert
  // newlines so plain-text fields render as paragraphs, not one run-on line.
  const escapeHtml = (s) =>
    s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')

  const section = (heading, content) =>
    content ? `<h2>${escapeHtml(heading)}</h2><p>${escapeHtml(content).replace(/\n+/g, '</p><p>')}</p>` : ''

  if (job.about_the_role) {
    return [
      section('About the Role', job.about_the_role),
      section('Key Responsibilities', job.key_responsibilities),
      section('Requirements', job.requirements),
      section('Preferred Certifications', job.preferred_certifications),
      section('Technical Competencies', job.technical_competencies),
      section('What We Offer', job.what_we_offer),
    ]
      .filter(Boolean)
      .join('')
  }

  if (job.description) {
    return `<p>${escapeHtml(job.description).replace(/\n+/g, '</p><p>')}</p>`
  }

  return `<p>${escapeHtml(job.title)}</p>`
}

// Builds a JobPosting structured-data object for a single job.
// Returns null when the job is not eligible for indexing (e.g. draft/unpublished
// or missing the fields Google requires), so callers can skip rendering the script.
export function buildJobPostingSchema(job, { url } = {}) {
  if (!job || job.status !== 'ACTIVE') return null

  const datePosted = job.created_at ? new Date(job.created_at).toISOString() : null
  if (!datePosted) return null

  const schema = {
    '@context': 'https://schema.org/',
    '@type': 'JobPosting',
    title: job.title,
    description: buildDescriptionHtml(job),
    datePosted,
    hiringOrganization: {
      '@type': 'Organization',
      name: job.company_name || 'Elevare Human Solutions',
      ...(job.company_logo_url ? { logo: job.company_logo_url } : {}),
      ...(job.company_website ? { sameAs: job.company_website } : {}),
    },
    ...buildJobLocation(job),
    ...(url ? { url } : {}),
    ...(EMPLOYMENT_TYPE_MAP[job.contract_type] ? { employmentType: EMPLOYMENT_TYPE_MAP[job.contract_type] } : {}),
  }

  const baseSalary = buildBaseSalary(job)
  if (baseSalary) schema.baseSalary = baseSalary

  // Expired posts: Google drops postings past validThrough automatically, and
  // penalizes sites that keep serving JobPosting markup for closed/expired
  // roles, so only attach it — never fabricate a future date for one that's
  // missing. Jobs already CLOSED are filtered out above.
  if (job.application_deadline) {
    schema.validThrough = new Date(job.application_deadline).toISOString()
  }

  return schema
}
