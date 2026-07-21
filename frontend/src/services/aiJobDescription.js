import api from '@/lib/api'

/**
 * AI Job Description service — abstracts the (not-yet-built) backend endpoint.
 *
 * TODO(backend): replace with a real call once `POST /api/v1/ai/job-description`
 * ships (see backend roadmap). Expected request/response shape is documented
 * inline below so this file only needs its try branch un-stubbed later.
 */

export const AI_MODES = {
  GENERATE: 'GENERATE',
  IMPROVE: 'IMPROVE',
  REWRITE_PROFESSIONAL: 'REWRITE_PROFESSIONAL',
  MORE_INCLUSIVE: 'MORE_INCLUSIVE',
  SHORTEN: 'SHORTEN',
  EXPAND: 'EXPAND',
  IMPROVE_CLARITY: 'IMPROVE_CLARITY',
}

export const AI_MODE_LABELS = {
  [AI_MODES.GENERATE]: 'Generate from scratch',
  [AI_MODES.IMPROVE]: 'Improve',
  [AI_MODES.REWRITE_PROFESSIONAL]: 'Rewrite professionally',
  [AI_MODES.MORE_INCLUSIVE]: 'Make more inclusive',
  [AI_MODES.SHORTEN]: 'Shorten',
  [AI_MODES.EXPAND]: 'Expand',
  [AI_MODES.IMPROVE_CLARITY]: 'Improve clarity',
}

// Modes that make sense with no existing text in the field yet.
export const MODES_REQUIRING_NO_TEXT = new Set([AI_MODES.GENERATE])
// Modes that require existing text to operate on.
export const MODES_REQUIRING_TEXT = new Set([
  AI_MODES.IMPROVE,
  AI_MODES.REWRITE_PROFESSIONAL,
  AI_MODES.MORE_INCLUSIVE,
  AI_MODES.SHORTEN,
  AI_MODES.EXPAND,
  AI_MODES.IMPROVE_CLARITY,
])

/**
 * Backend's JobContext schema (backend/app/modules/ai/schema.py) only knows
 * title / seniority / skills / industry / company_name — translate the
 * JobForm's field names into that shape here, at the service boundary.
 */
function toBackendJobContext(jobContext) {
  return {
    title: jobContext?.title || '',
    seniority: jobContext?.seniority_level || undefined,
    skills: jobContext?.required_skills?.length ? jobContext.required_skills : undefined,
  }
}

/**
 * @param {Object} params
 * @param {string} params.mode - one of AI_MODES
 * @param {string} params.field - form field key, e.g. "about_the_role"
 * @param {string} params.currentText - existing textarea contents (may be empty)
 * @param {Object} params.jobContext - other form values useful as prompt context
 *   (title, seniority_level, contract_type, location, required_skills, etc.)
 * @returns {Promise<{ text: string }>}
 */
export async function generateJobDescriptionText({ mode, field, currentText, jobContext }) {
  try {
    const { data } = await api.post('/api/v1/ai/job-description', {
      mode,
      field,
      current_text: currentText || undefined,
      job_context: toBackendJobContext(jobContext),
    })
    return { text: data.generated_text }
  } catch (err) {
    // Endpoint doesn't exist yet (404) or backend unreachable in this environment —
    // fall back to a local mock so the UX can be built/demoed end-to-end now.
    // TODO(backend): remove this fallback once the real endpoint ships.
    if (import.meta.env.DEV) {
      console.warn('[aiJobDescription] backend endpoint unavailable, using mock response', err)
    }
    return { text: mockGenerate({ mode, field, currentText, jobContext }) }
  }
}

function mockGenerate({ mode, field, currentText, jobContext }) {
  const title = jobContext?.title?.trim() || 'this role'
  const skills = (jobContext?.required_skills || []).slice(0, 4).join(', ')

  const fieldLabels = {
    about_the_role: 'About the Role',
    key_responsibilities: 'Key Responsibilities',
    requirements: 'Requirements',
  }
  const label = fieldLabels[field] || field

  switch (mode) {
    case AI_MODES.GENERATE:
      if (field === 'key_responsibilities') {
        return [
          `Own and deliver core outcomes for ${title}.`,
          'Collaborate cross-functionally with product, design, and engineering stakeholders.',
          skills ? `Apply expertise in ${skills} to day-to-day work.` : 'Apply strong domain expertise to day-to-day work.',
          'Continuously identify opportunities to improve processes and outcomes.',
        ].join('\n')
      }
      if (field === 'requirements') {
        return [
          `Proven experience in a similar ${title} position.`,
          skills ? `Hands-on experience with ${skills}.` : 'Strong relevant technical or domain skills.',
          'Excellent communication and collaboration skills.',
          'Ability to work independently and manage priorities.',
        ].join('\n')
      }
      return `We're looking for a ${title} to join our team. In this role, you'll take ownership of key initiatives, work closely with a talented cross-functional team, and help drive meaningful outcomes for the business.`

    case AI_MODES.IMPROVE:
      return `${currentText.trim()}\n\nThis role offers the opportunity to make a real impact while working alongside a supportive, high-performing team.`

    case AI_MODES.REWRITE_PROFESSIONAL:
      return currentText
        .split('\n')
        .map((line) => line.trim())
        .filter(Boolean)
        .map((line) => (line.endsWith('.') ? line : `${line}.`))
        .join('\n')

    case AI_MODES.MORE_INCLUSIVE:
      return currentText
        .replace(/\bguys\b/gi, 'team')
        .replace(/\brockstar\b/gi, 'high performer')
        .replace(/\bninja\b/gi, 'expert')
        .concat('\n\nWe welcome applicants from all backgrounds and encourage you to apply even if you don\'t meet every requirement.')

    case AI_MODES.SHORTEN: {
      const sentences = currentText.split(/(?<=[.!?])\s+/).filter(Boolean)
      return sentences.slice(0, Math.max(1, Math.ceil(sentences.length / 2))).join(' ')
    }

    case AI_MODES.EXPAND:
      return `${currentText.trim()}\n\nWe're seeking someone who brings both technical depth and strong collaboration skills, and who's excited to grow with us as ${label.toLowerCase()} evolve over time.`

    case AI_MODES.IMPROVE_CLARITY:
      return currentText
        .split('\n')
        .map((l) => l.trim())
        .filter(Boolean)
        .join('\n')

    default:
      return currentText
  }
}
