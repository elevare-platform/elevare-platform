// Helpers for a job's scoring profile (docs/08_DECISIONS.md, item 36): competencies with weights
// that add up to 100, which are key, and the thresholds of the suggested bands. The server applies
// the same rules and is the authority; these give instant feedback and keep the editor's list
// handling in one tested place.

export const MIN_COMPETENCIES = 2
export const MAX_COMPETENCIES = 12
export const MAX_NAME_CHARS = 80

export const BAND_NAMES = {
  strong: 'Strong shortlist',
  shortlist: 'Shortlist',
  hold: 'Hold for evidence',
  not: 'Do not shortlist',
}

// The colours a band is shown in, wherever it appears.
export const BAND_STYLE = {
  [BAND_NAMES.strong]: 'bg-green-100 text-green-800 border-green-200',
  [BAND_NAMES.shortlist]: 'bg-green-50 text-green-700 border-green-200',
  [BAND_NAMES.hold]: 'bg-amber-100 text-amber-800 border-amber-200',
  [BAND_NAMES.not]: 'bg-gray-100 text-gray-700 border-gray-200',
}

/** A new, empty competency for the employer to fill in. `key` is only for the screen's list. */
export function blankCompetency(key) {
  return { key, name: '', weight: '', isKey: false }
}

/** The editor's rows from a profile or a template (`competencies` as the server sends them). */
export function rowsFrom(competencies, newKey) {
  return competencies.map((item) => ({ key: newKey(), name: item.name, weight: item.weight, isKey: Boolean(item.key) }))
}

const cleanName = (value) => String(value ?? '').split(/\s+/).filter(Boolean).join(' ')

/** The sum of the weights typed so far (a blank or a non-number counts as 0). */
export function totalWeight(rows) {
  return rows.reduce((sum, row) => sum + (Number.isFinite(Number(row.weight)) ? Number(row.weight) : 0), 0)
}

/**
 * What is wrong with the profile, in words the employer can act on. Mirrors the server's rules so
 * Save can say why it will not work.
 */
export function problemsWith(rows, bands, keyMinRating) {
  const found = []
  if (rows.length < MIN_COMPETENCIES || rows.length > MAX_COMPETENCIES) {
    found.push(`A scoring profile needs between ${MIN_COMPETENCIES} and ${MAX_COMPETENCIES} competencies.`)
  }
  const seen = new Set()
  rows.forEach((row, index) => {
    const name = cleanName(row.name)
    const weight = Number(row.weight)
    if (!name) found.push(`Competency ${index + 1} needs a name.`)
    else if (name.length > MAX_NAME_CHARS) found.push(`Competency ${index + 1} has a name over ${MAX_NAME_CHARS} characters.`)
    else if (seen.has(name.toLowerCase())) found.push(`"${name}" is listed twice.`)
    seen.add(name.toLowerCase())
    if (row.weight === '' || !Number.isInteger(weight) || weight < 1 || weight > 100) {
      found.push(`Competency ${index + 1} needs a whole-number weight from 1 to 100.`)
    }
  })
  const total = totalWeight(rows)
  if (rows.length >= MIN_COMPETENCIES && total !== 100) {
    found.push(`The weights add up to ${total}%, and must add up to 100%.`)
  }
  const { strong, shortlist, hold } = Object.fromEntries(Object.entries(bands).map(([k, v]) => [k, Number(v)]))
  if ([strong, shortlist, hold].some((v) => !Number.isInteger(v) || v < 1 || v > 100)) {
    found.push('The band thresholds must be whole numbers from 1 to 100.')
  } else if (!(strong > shortlist && shortlist > hold)) {
    found.push('The band thresholds must go down: Strong shortlist, then Shortlist, then Hold.')
  }
  if (![1, 2, 3, 4, 5].includes(Number(keyMinRating))) found.push('The minimum rating for key competencies must be from 1 to 5.')
  return found
}

/** The request body for saving: tidy names, whole weights, the key flag as `key`. */
export function toRequest(rows, bands, keyMinRating, templateCode) {
  return {
    competencies: rows.map((row) => ({ name: cleanName(row.name), weight: Number(row.weight), key: Boolean(row.isKey) })),
    bands: { strong: Number(bands.strong), shortlist: Number(bands.shortlist), hold: Number(bands.hold) },
    key_min_rating: Number(keyMinRating),
    template_code: templateCode || null,
  }
}

/** The band a total falls in, by a job's cut-offs (`{ strong, shortlist, hold }`): the same rule the
 *  server applies, used to preview a score someone is about to set. */
export function bandForScore(score, bands) {
  if (score >= bands.strong) return BAND_NAMES.strong
  if (score >= bands.shortlist) return BAND_NAMES.shortlist
  if (score >= bands.hold) return BAND_NAMES.hold
  return BAND_NAMES.not
}
