import { useState } from 'react'
import { Search, Loader2, X, Info } from 'lucide-react'
import Navbar from '@/components/layout/Navbar'
import Footer from '@/components/layout/Footer'
import { useToast } from '@/components/admin/Toast'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import api from '@/lib/api'
import { useSavedCandidates } from '@/hooks/useSavedCandidates'
import CandidateSearchResultCard from '@/components/employer/CandidateSearchResultCard'

const SENIORITY_OPTIONS = ['JUNIOR', 'MID', 'SENIOR', 'LEAD', 'EXECUTIVE']
const AVAILABILITY_OPTIONS = [
  { value: 'IMMEDIATE', label: 'Immediate' },
  { value: 'TWO_WEEKS', label: 'Within 2 weeks' },
  { value: 'ONE_MONTH', label: 'Within 1 month' },
  { value: 'FLEXIBLE', label: 'Flexible' },
]

const EMPTY_FILTERS = {
  skills: [],
  job_title: '',
  min_experience: '',
  max_experience: '',
  location: '',
  seniority: [],
  availability: [],
  query: '',
}

function toggleInList(list, value) {
  return list.includes(value) ? list.filter((v) => v !== value) : [...list, value]
}

// Small hover tooltip for explaining a field inline, without sending the
// recruiter away to read docs. `group/tooltip` is a scoped group name so it
// doesn't collide with other `group` hover effects on the page.
function InfoTooltip({ text }) {
  return (
    <span className="relative inline-flex group/tooltip">
      <Info size={13} className="text-text-muted cursor-help" aria-label={text} tabIndex={0} />
      <span
        role="tooltip"
        className="pointer-events-none absolute left-1/2 -translate-x-1/2 bottom-full mb-2 w-64 rounded-lg bg-gray-900 text-white text-xs leading-snug p-2.5 opacity-0 group-hover/tooltip:opacity-100 group-focus-within/tooltip:opacity-100 transition-opacity z-10"
      >
        {text}
      </span>
    </span>
  )
}

// Converts UI filter state (strings for numeric inputs, '' for unset) into
// the payload shape the backend's CandidateSearchFilters schema expects.
function toPayload(filters) {
  return {
    skills: filters.skills.length ? filters.skills : null,
    job_title: filters.job_title || null,
    min_experience: filters.min_experience === '' ? null : Number(filters.min_experience),
    max_experience: filters.max_experience === '' ? null : Number(filters.max_experience),
    location: filters.location || null,
    seniority: filters.seniority.length ? filters.seniority : null,
    availability: filters.availability.length ? filters.availability : null,
    query: filters.query || null,
  }
}

export default function CandidateSearchPage() {
  const { show, ToastContainer } = useToast()
  const savedCandidates = useSavedCandidates()

  const [filters, setFilters] = useState(EMPTY_FILTERS)
  const [skillInput, setSkillInput] = useState('')

  const [results, setResults] = useState(null)
  const [searching, setSearching] = useState(false)

  const addSkill = () => {
    const skill = skillInput.trim()
    if (skill && !filters.skills.includes(skill)) {
      setFilters((f) => ({ ...f, skills: [...f.skills, skill] }))
    }
    setSkillInput('')
  }

  const runSearch = async () => {
    setSearching(true)
    try {
      const payload = toPayload(filters)
      const { data } = await api.post('/api/v1/candidates/search', payload)
      setResults(data)
    } catch (err) {
      show(err.response?.data?.message ?? 'Search failed', 'error')
    } finally {
      setSearching(false)
    }
  }

  return (
    <div className="min-h-screen bg-background flex flex-col">
      <Navbar />
      <ToastContainer />

      <main className="flex-1 max-w-5xl mx-auto w-full px-4 sm:px-6 pt-16 pb-8 space-y-6">
        <div>
          <h1 className="text-xl font-bold text-text">Candidate Search</h1>
          <p className="text-text-muted text-sm mt-1">
            Search across candidate profiles by skill, experience, location, seniority, and availability.
          </p>
        </div>

        {/* Filters  -  structured fields for precise attributes, plus a free-text
            field for anything better matched by meaning than by an exact filter.
            Both are submitted together in one search; no LLM step in between. */}
        <div className="rounded-xl border border-border bg-white p-5 space-y-4">
          <p className="text-sm font-semibold text-text">Filters</p>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="text-xs font-medium text-text-muted">Skills</label>
              <div className="flex gap-2 mt-1">
                <input
                  type="text"
                  value={skillInput}
                  onChange={(e) => setSkillInput(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addSkill() } }}
                  placeholder="Add a skill and press Enter"
                  className="flex-1 rounded-lg border border-border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-blue/30"
                />
              </div>
              {filters.skills.length > 0 && (
                <div className="flex flex-wrap gap-1.5 mt-2">
                  {filters.skills.map((skill) => (
                    <span key={skill} className="flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-brand-blue/10 text-brand-blue border border-brand-blue/30">
                      {skill}
                      <button onClick={() => setFilters((f) => ({ ...f, skills: f.skills.filter((s) => s !== skill) }))}>
                        <X size={11} />
                      </button>
                    </span>
                  ))}
                </div>
              )}
            </div>

            <div>
              <label className="text-xs font-medium text-text-muted">Job title</label>
              <input
                type="text"
                value={filters.job_title}
                onChange={(e) => setFilters((f) => ({ ...f, job_title: e.target.value }))}
                placeholder="e.g. Backend Engineer"
                className="mt-1 w-full rounded-lg border border-border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-blue/30"
              />
            </div>

            <div>
              <label className="text-xs font-medium text-text-muted">Location</label>
              <input
                type="text"
                value={filters.location}
                onChange={(e) => setFilters((f) => ({ ...f, location: e.target.value }))}
                placeholder="e.g. Lagos"
                className="mt-1 w-full rounded-lg border border-border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-blue/30"
              />
            </div>

            <div>
              <label className="text-xs font-medium text-text-muted">Experience range (years)</label>
              <div className="flex items-center gap-2 mt-1">
                <input
                  type="number"
                  min="0"
                  value={filters.min_experience}
                  onChange={(e) => setFilters((f) => ({ ...f, min_experience: e.target.value }))}
                  placeholder="Min"
                  className="w-full rounded-lg border border-border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-blue/30"
                />
                <span className="text-text-muted text-sm">-</span>
                <input
                  type="number"
                  min="0"
                  value={filters.max_experience}
                  onChange={(e) => setFilters((f) => ({ ...f, max_experience: e.target.value }))}
                  placeholder="Max"
                  className="w-full rounded-lg border border-border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-blue/30"
                />
              </div>
            </div>

            <div>
              <label className="flex items-center gap-1.5 text-xs font-medium text-text-muted">
                Describe the ideal candidate (optional)
                <InfoTooltip text="Goes beyond the filters above. Matches candidates whose overall profile reads as similar in meaning, even if they don't use these exact words. Use it for things that are hard to turn into a filter, like 'fintech experience' or 'scaled a system under heavy traffic'." />
              </label>
              <input
                type="text"
                value={filters.query}
                onChange={(e) => setFilters((f) => ({ ...f, query: e.target.value }))}
                placeholder="e.g. fintech experience, led a system migration"
                className="mt-1 w-full rounded-lg border border-border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-blue/30"
              />
            </div>
          </div>

          <div>
            <label className="text-xs font-medium text-text-muted">Seniority</label>
            <div className="flex flex-wrap gap-2 mt-1.5">
              {SENIORITY_OPTIONS.map((level) => (
                <button
                  key={level}
                  type="button"
                  onClick={() => setFilters((f) => ({ ...f, seniority: toggleInList(f.seniority, level) }))}
                  className={cn(
                    'px-3 py-1.5 rounded-full text-xs border transition-colors',
                    filters.seniority.includes(level)
                      ? 'bg-brand-blue text-white border-brand-blue'
                      : 'bg-white text-text-muted border-border hover:border-brand-blue/40'
                  )}
                >
                  {level.charAt(0) + level.slice(1).toLowerCase()}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="text-xs font-medium text-text-muted">Availability</label>
            <div className="flex flex-wrap gap-2 mt-1.5">
              {AVAILABILITY_OPTIONS.map(({ value, label }) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => setFilters((f) => ({ ...f, availability: toggleInList(f.availability, value) }))}
                  className={cn(
                    'px-3 py-1.5 rounded-full text-xs border transition-colors',
                    filters.availability.includes(value)
                      ? 'bg-brand-blue text-white border-brand-blue'
                      : 'bg-white text-text-muted border-border hover:border-brand-blue/40'
                  )}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          <div className="flex items-center gap-2 pt-2">
            <Button onClick={() => runSearch()} disabled={searching}>
              {searching ? <Loader2 size={16} className="animate-spin mr-1.5" /> : <Search size={16} className="mr-1.5" />}
              Search
            </Button>
            <Button variant="outline" onClick={() => { setFilters(EMPTY_FILTERS); setResults(null) }}>
              Clear
            </Button>
          </div>
        </div>

        {/* Results */}
        {results && (
          <div className="space-y-3">
            <p className="text-sm text-text-muted">{results.total} result{results.total !== 1 ? 's' : ''}</p>
            {results.results.length === 0 ? (
              <div className="rounded-xl border border-border bg-white p-8 text-center text-text-muted text-sm">
                No candidates matched these filters.
              </div>
            ) : (
              results.results.map((result) => (
                <CandidateSearchResultCard key={result.profile.id} result={result} savedCandidates={savedCandidates} />
              ))
            )}
          </div>
        )}
      </main>

      <Footer />
    </div>
  )
}
