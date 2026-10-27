import { useEffect, useState } from 'react'
import { Check, ClipboardList, Loader2, Pencil, Search, Trash2, X } from 'lucide-react'
import api from '@/lib/api'
import { cn } from '@/lib/utils'
import { formatSeconds } from '@/lib/interviewQuestions'

const TABS = [
  { key: 'built_in', label: 'Colton Group sets' },
  { key: 'company', label: "My company's sets" },
  { key: 'jobs', label: 'My other jobs' },
]

const LIBRARY_URL = '/api/v1/interviews/question-templates'

// The server's own words when it sent any (its messages name the problem).
function serverMessage(err, fallback) {
  const body = err?.response?.data
  const detail = body?.details?.map((item) => item.message).filter(Boolean).join(' ')
  const message = detail || body?.message || body?.detail
  return typeof message === 'string' ? message : fallback
}

const plural = (count, word) => `${count} ${word}${count === 1 ? '' : 's'}`

function Meta({ entry }) {
  const bits = [plural(entry.question_count, 'question'), formatSeconds(entry.total_seconds)]
  if (entry.has_practical) bits.push('practical case')
  if (entry.has_scoring_profile) bits.push('scoring profile')
  return <p className="text-xs text-text-muted">{bits.join(' · ')}</p>
}

function QuestionList({ questions }) {
  return (
    <ol className="mt-2 list-decimal space-y-1 pl-5 text-xs text-text" data-testid="library-preview">
      {questions.map((item, index) => (
        <li key={`${index}-${item.text}`}>
          {item.text}
          {item.is_practical && (
            <span className="ml-1.5 rounded-full bg-brand-blue/10 px-1.5 py-0.5 text-[10px] font-semibold text-brand-blue">
              Practical case
            </span>
          )}
          <span className="ml-1.5 text-text-muted">({formatSeconds(item.time_limit_seconds)})</span>
        </li>
      ))}
    </ol>
  )
}

/**
 * QuestionLibraryModal - where an employer starts a job's interview questions from a ready-made
 * set (docs/08_DECISIONS.md, item 46): the Colton Group's role sets, the sets their company saved,
 * and the questions of the company's other jobs. Search, preview, then "Use this set", which puts
 * the set's questions, scoring profile and follow-up choice on the job in one step. A company's
 * own set can be renamed or deleted by the person who saved it or the company owner.
 *
 * `onApplied(data, name)` is called with the server's reply (the questions to show, and whether
 * they were saved or are only a draft to shorten).
 */
export default function QuestionLibraryModal({ jobId, hasQuestions, onApplied, onClose }) {
  const [tab, setTab] = useState('built_in')
  const [query, setQuery] = useState('')
  const [search, setSearch] = useState('')
  const [library, setLibrary] = useState(null) // { search, built_in, company, can_save }
  const [jobs, setJobs] = useState(null) // { search, items }
  const [failed, setFailed] = useState(false)
  const [error, setError] = useState(null)
  const [open, setOpen] = useState(null) // the id of the card being previewed
  const [jobPreview, setJobPreview] = useState({}) // job id -> questions
  const [busy, setBusy] = useState(null)
  const [renaming, setRenaming] = useState(null) // { id, name }

  // The search settles a moment after the typing stops.
  useEffect(() => {
    const timer = setTimeout(() => setSearch(query.trim()), 250)
    return () => clearTimeout(timer)
  }, [query])

  useEffect(() => {
    let cancelled = false
    api
      .get(LIBRARY_URL, { params: search ? { q: search } : undefined })
      .then(({ data }) => {
        if (!cancelled) setLibrary({ search, ...data })
      })
      .catch(() => {
        if (!cancelled) setFailed(true)
      })
    return () => {
      cancelled = true
    }
  }, [search])

  useEffect(() => {
    if (tab !== 'jobs') return undefined
    let cancelled = false
    api
      .get(`${LIBRARY_URL}/jobs`, { params: { ...(search ? { q: search } : {}), exclude_job_id: jobId } })
      .then(({ data }) => {
        if (!cancelled) setJobs({ search, items: data.items ?? [] })
      })
      .catch(() => {
        if (!cancelled) setFailed(true)
      })
    return () => {
      cancelled = true
    }
  }, [tab, search, jobId])

  const loading = tab === 'jobs' ? jobs?.search !== search : library?.search !== search

  const use = async (entry) => {
    const withProfile = entry.has_scoring_profile
    const message = hasQuestions
      ? `Replace this job's questions${withProfile ? ' and scoring profile' : ''} with "${entry.name}"? Interviews already started keep the questions they began with.`
      : `Start from "${entry.name}"?${withProfile ? ' It also sets the job\'s scoring profile.' : ''}`
    if (!window.confirm(message)) return
    setBusy(entry.id)
    setError(null)
    try {
      const base = `/api/v1/interviews/jobs/${jobId}/questions`
      const [url, body] =
        entry.kind === 'BUILT_IN'
          ? [`${base}/from-template`, { code: entry.id }]
          : entry.kind === 'COMPANY'
            ? [`${base}/from-saved-template`, { template_id: entry.id }]
            : [`${base}/from-job`, { source_job_id: entry.id }]
      const { data } = await api.post(url, body)
      onApplied(data, entry.name)
    } catch (err) {
      setError(serverMessage(err, 'We could not load that set just now. Please try again.'))
    } finally {
      setBusy(null)
    }
  }

  const preview = async (entry) => {
    setOpen((current) => (current === entry.id ? null : entry.id))
    if (entry.kind === 'JOB' && !jobPreview[entry.id]) {
      try {
        const { data } = await api.get(`/api/v1/interviews/jobs/${entry.id}/questions`)
        setJobPreview((current) => ({ ...current, [entry.id]: data.questions }))
      } catch {
        setError('We could not load those questions just now. Please try again.')
      }
    }
  }

  const rename = async () => {
    setBusy(renaming.id)
    setError(null)
    try {
      const { data } = await api.patch(`${LIBRARY_URL}/${renaming.id}`, { name: renaming.name })
      setLibrary((current) => ({ ...current, company: current.company.map((item) => (item.id === data.id ? data : item)) }))
      setRenaming(null)
    } catch (err) {
      setError(serverMessage(err, 'Something went wrong. Please try again.'))
    } finally {
      setBusy(null)
    }
  }

  const remove = async (entry) => {
    if (!window.confirm(`Delete "${entry.name}"? Jobs already started from it are not affected.`)) return
    setBusy(entry.id)
    setError(null)
    try {
      await api.delete(`${LIBRARY_URL}/${entry.id}`)
      setLibrary((current) => ({ ...current, company: current.company.filter((item) => item.id !== entry.id) }))
    } catch (err) {
      setError(serverMessage(err, 'Something went wrong. Please try again.'))
    } finally {
      setBusy(null)
    }
  }

  const entries =
    tab === 'jobs'
      ? (jobs?.items ?? []).map((item) => ({
          id: item.job_id,
          kind: 'JOB',
          name: item.title,
          question_count: item.question_count,
          total_seconds: item.total_seconds,
          has_practical: item.has_practical,
          has_scoring_profile: false,
        }))
      : (library?.[tab] ?? [])

  const emptyText = {
    built_in: 'No Colton Group set matches your search.',
    company: search
      ? 'None of your company\'s sets match your search.'
      : 'Your company has not saved a set yet. Write the questions for a job, then choose "Save as template" to keep them here.',
    jobs: search ? 'None of your other jobs match your search.' : 'None of your company\'s other jobs have interview questions yet.',
  }[tab]

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/40 px-4 py-6">
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Template library"
        className="flex max-h-full w-full max-w-2xl flex-col rounded-xl border border-border bg-white"
      >
        <div className="flex items-start justify-between gap-4 p-6 pb-3">
          <div>
            <h2 className="text-lg font-bold text-text">Template library</h2>
            <p className="mt-1 text-sm text-text-muted">
              Start this job from a ready-made set of questions. You can change anything afterwards.
            </p>
          </div>
          <button type="button" onClick={onClose} className="flex-shrink-0 text-text-muted hover:text-text" aria-label="Close the library">
            <X size={18} />
          </button>
        </div>

        <div className="space-y-3 px-6">
          <div className="relative">
            <Search size={14} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-text-muted" aria-hidden="true" />
            <input
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search by role, competency or question"
              aria-label="Search the library"
              data-testid="library-search"
              className="w-full rounded-lg border border-border py-2 pl-8 pr-3 text-sm focus:outline-none focus:ring-2 focus:ring-brand-blue/40"
            />
          </div>
          <div className="flex gap-1.5 overflow-x-auto" role="tablist" aria-label="Where to start from">
            {TABS.map((item) => {
              const count = item.key === 'jobs' ? jobs?.items.length : library?.[item.key]?.length
              return (
                <button
                  key={item.key}
                  type="button"
                  role="tab"
                  aria-selected={tab === item.key}
                  onClick={() => { setTab(item.key); setOpen(null) }}
                  className={cn(
                    'whitespace-nowrap rounded-full px-3 py-1.5 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-blue',
                    tab === item.key ? 'bg-brand-blue text-white' : 'border border-border bg-surface text-text-muted hover:text-text'
                  )}
                >
                  {item.label}
                  {count != null && <span className="ml-1.5 opacity-80">{count}</span>}
                </button>
              )
            })}
          </div>
        </div>

        <div className="flex-1 space-y-3 overflow-y-auto px-6 py-4">
          {failed && (
            <p role="alert" className="text-sm text-red-600">The library could not be loaded. Please close this and try again.</p>
          )}
          {error && (
            <p role="alert" className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">{error}</p>
          )}
          {!failed && loading && (
            <p className="flex items-center gap-2 text-sm text-text-muted">
              <Loader2 size={14} className="animate-spin" /> Loading…
            </p>
          )}
          {!failed && !loading && entries.length === 0 && (
            <p data-testid="library-empty" className="rounded-lg border border-dashed border-border px-4 py-6 text-center text-sm text-text-muted">
              {emptyText}
            </p>
          )}

          {!failed && !loading && entries.map((entry) => {
            const isOpen = open === entry.id
            const questions = entry.kind === 'JOB' ? jobPreview[entry.id] : entry.questions
            const isRenaming = renaming?.id === entry.id
            return (
              <div key={`${entry.kind}-${entry.id}`} data-testid="library-card" className="rounded-lg border border-border p-3">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    {isRenaming ? (
                      <div className="flex items-center gap-1.5">
                        <input
                          aria-label="New name"
                          value={renaming.name}
                          onChange={(event) => setRenaming({ ...renaming, name: event.target.value })}
                          maxLength={120}
                          className="min-w-0 flex-1 rounded-lg border border-border px-2 py-1 text-sm"
                        />
                        <button type="button" onClick={rename} disabled={busy === entry.id} aria-label="Save the new name" className="rounded p-1 text-green-700 hover:bg-green-50">
                          <Check size={15} />
                        </button>
                        <button type="button" onClick={() => setRenaming(null)} aria-label="Cancel renaming" className="rounded p-1 text-text-muted hover:bg-surface-muted">
                          <X size={15} />
                        </button>
                      </div>
                    ) : (
                      <p className="flex items-center gap-1.5 text-sm font-semibold text-text">
                        <ClipboardList size={14} className="flex-shrink-0 text-text-muted" aria-hidden="true" />
                        <span className="truncate">{entry.name}</span>
                      </p>
                    )}
                    <Meta entry={entry} />
                    {entry.kind === 'COMPANY' && (
                      <p className="text-xs text-text-muted">
                        Saved by {entry.created_by_name}
                        {entry.created_at ? ` on ${new Date(entry.created_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })}` : ''}
                      </p>
                    )}
                  </div>
                  <div className="flex flex-shrink-0 items-center gap-1.5">
                    {entry.kind === 'COMPANY' && entry.can_edit && !isRenaming && (
                      <>
                        <button type="button" onClick={() => setRenaming({ id: entry.id, name: entry.name })} aria-label={`Rename ${entry.name}`} className="rounded p-1.5 text-text-muted hover:bg-surface-muted">
                          <Pencil size={13} />
                        </button>
                        <button type="button" onClick={() => remove(entry)} disabled={busy === entry.id} aria-label={`Delete ${entry.name}`} className="rounded p-1.5 text-red-600 hover:bg-red-50">
                          <Trash2 size={13} />
                        </button>
                      </>
                    )}
                    <button
                      type="button"
                      onClick={() => preview(entry)}
                      aria-expanded={isOpen}
                      className="rounded-lg border border-border px-2.5 py-1 text-xs font-semibold text-text hover:bg-surface-muted"
                    >
                      {isOpen ? 'Hide' : 'Preview'}
                    </button>
                    <button
                      type="button"
                      onClick={() => use(entry)}
                      disabled={busy !== null}
                      className="inline-flex items-center gap-1.5 rounded-lg bg-brand-blue px-2.5 py-1 text-xs font-semibold text-white hover:bg-brand-blue/90 disabled:opacity-50"
                    >
                      {busy === entry.id && <Loader2 size={12} className="animate-spin" />}
                      Use this set
                    </button>
                  </div>
                </div>
                {isOpen && (questions ? <QuestionList questions={questions} /> : (
                  <p className="mt-2 flex items-center gap-2 text-xs text-text-muted"><Loader2 size={12} className="animate-spin" /> Loading…</p>
                ))}
              </div>
            )
          })}
        </div>

        <div className="flex justify-end p-6 pt-2">
          <button type="button" onClick={onClose} className="rounded-lg px-3 py-1.5 text-xs font-semibold text-text-muted hover:bg-surface-muted">
            Close
          </button>
        </div>
      </div>
    </div>
  )
}
