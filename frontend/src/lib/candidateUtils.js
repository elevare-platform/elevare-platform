// Fields that contribute to Profile Strength (Requirement 3.1)
export const STRENGTH_FIELDS = ['bio', 'skills', 'years_of_experience', 'location']

// computeStrength returns an integer in [0, 100] representing how complete
// the candidate's profile is, based on the four strength fields plus a CV.
// Each of the 4 fields contributes 20%; having at least one CV contributes 20%.
export function computeStrength(profile) {
  if (!profile) return 0
  const filled = STRENGTH_FIELDS.filter((f) => {
    const v = profile[f]
    if (Array.isArray(v)) return v.length > 0
    return v !== null && v !== undefined && v !== ''
  })
  const hasCV = Array.isArray(profile.cvs) && profile.cvs.length > 0
  const total = STRENGTH_FIELDS.length + 1  // 4 fields + 1 for CV
  return Math.round(((filled.length + (hasCV ? 1 : 0)) / total) * 100)
}

// isEmptyState returns true when the candidate has no CVs, no documents,
// and none of the four profile strength fields are filled (Requirement 10.1).
export function isEmptyState(profile) {
  if (!profile) return true
  const noCvs = !profile.cvs || profile.cvs.length === 0
  const noDocs = !profile.documents || profile.documents.length === 0
  const noStrengthFields = STRENGTH_FIELDS.every((f) => {
    const v = profile[f]
    if (Array.isArray(v)) return v.length === 0
    return v === null || v === undefined || v === ''
  })
  return noCvs && noDocs && noStrengthFields
}
