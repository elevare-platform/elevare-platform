import { useCallback, useEffect, useRef, useState } from 'react'
import { Loader2, Plus, Trash2, X } from 'lucide-react'
import api from '@/lib/api'
import {
  BAND_NAMES,
  MAX_COMPETENCIES,
  blankCompetency,
  problemsWith,
  rowsFrom,
  toRequest,
  totalWeight,
} from '@/lib/scoringProfile'

// The server's own words when it sent any (its messages name the problem).
function serverMessage(err, fallback) {
  const body = err?.response?.data
  const detail = body?.details?.map((item) => item.message).filter(Boolean).join(' ')
  const message = detail || body?.message || body?.detail
  return typeof message === 'string' ? message : fallback
}

/**
 * ScoringProfileModal - a job's scoring profile for the strict interview: the competencies the AI
 * rates, each with a weight (they must add up to 100%), which are KEY (a key competency rated under
 * the minimum holds the suggested band at "Hold for evidence"), and the thresholds of the suggested
 * bands. A ready-made template (the Colton Group's three roles) can be the starting point.
 *
 * A job without a profile is scored by the generic scorecard as before. Shown only when the
 * platform's interview style is "strict" (see InterviewListTab).
 */
export default function ScoringProfileModal({ jobId, onClose, onSaved }) {
  const nextKey = useRef(0)
  const newKey = useCallback(() => `c${nextKey.current++}`, [])

  const [status, setStatus] = useState('loading') // loading | ready | error
  const [info, setInfo] = useState(null) // the server's templates and defaults
  const [rows, setRows] = useState([])
  const [bands, setBands] = useState({ strong: 85, shortlist: 75, hold: 65 })
  const [keyMin, setKeyMin] = useState(3)
  const [templateCode, setTemplateCode] = useState(null)
  const [hasProfile, setHasProfile] = useState(false)
  const [dirty, setDirty] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false
    api
      .get(`/api/v1/interviews/jobs/${jobId}/scoring-profile`)
      .then(({ data }) => {
        if (cancelled) return
        setInfo(data)
        setBands(data.profile?.bands ?? data.default_bands)
        setKeyMin(data.profile?.key_min_rating ?? data.default_key_min_rating)
        setRows(data.profile ? rowsFrom(data.profile.competencies, newKey) : [])
        setTemplateCode(data.profile?.template_code ?? null)
        setHasProfile(Boolean(data.profile))
        setStatus('ready')
      })
      .catch(() => {
        if (!cancelled) setStatus('error')
      })
    return () => {
      cancelled = true
    }
  }, [jobId, newKey])

  const edit = (updater) => {
    setRows(updater)
    setDirty(true)
    setError(null)
  }

  const change = (index, field, value) =>
    edit((list) => list.map((row, position) => (position === index ? { ...row, [field]: value } : row)))

  const startFromTemplate = (code) => {
    const template = info.templates.find((item) => item.code === code)
    if (!template) return
    if (rows.length > 0 && !window.confirm(`Replace your competencies with the ${template.title} template?`)) return
    setRows(rowsFrom(template.competencies, newKey))
    setTemplateCode(template.code)
    setBands(info.default_bands)
    setKeyMin(info.default_key_min_rating)
    setDirty(true)
    setError(null)
  }

  const close = () => {
    if (dirty && !window.confirm('You have unsaved changes. Close without saving?')) return
    onClose()
  }

  const save = async () => {
    setSaving(true)
    setError(null)
    try {
      const { data } = await api.put(`/api/v1/interviews/jobs/${jobId}/scoring-profile`, toRequest(rows, bands, keyMin, templateCode))
      onSaved?.(data)
      onClose()
    } catch (err) {
      setError(serverMessage(err, 'Something went wrong. Please try again.'))
    } finally {
      setSaving(false)
    }
  }

  const remove = async () => {
    if (!window.confirm('Remove the scoring profile? This job goes back to the generic scorecard. Interviews already scored keep their reports.')) return
    setSaving(true)
    setError(null)
    try {
      const { data } = await api.delete(`/api/v1/interviews/jobs/${jobId}/scoring-profile`)
      onSaved?.(data)
      onClose()
    } catch (err) {
      setError(serverMessage(err, 'Something went wrong. Please try again.'))
    } finally {
      setSaving(false)
    }
  }

  const problems = problemsWith(rows, bands, keyMin)
  const total = totalWeight(rows)
  const atLimit = rows.length >= MAX_COMPETENCIES

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4 py-6">
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Scoring profile"
        className="flex max-h-full w-full max-w-2xl flex-col rounded-xl border border-border bg-white"
      >
        <div className="flex items-start justify-between gap-4 p-6 pb-3">
          <div>
            <h2 className="text-lg font-bold text-text">Scoring profile</h2>
            <p className="text-sm text-text-muted mt-1">
              The competencies the AI rates in this interview, and what each is worth. The score is
              worked out from the AI&apos;s 1 to 5 rating of each one. Without a profile the AI chooses
              the competencies from the interview brief.
            </p>
          </div>
          <button type="button" onClick={close} className="text-text-muted hover:text-text flex-shrink-0" aria-label="Close">
            <X size={18} />
          </button>
        </div>

        <div className="flex-1 space-y-4 overflow-y-auto px-6 pb-2">
          {status === 'loading' && (
            <p className="flex items-center gap-2 text-sm text-text-muted">
              <Loader2 size={14} className="animate-spin" /> Loading…
            </p>
          )}
          {status === 'error' && (
            <p role="alert" className="text-sm text-red-600">
              The scoring profile could not be loaded. Please close this and try again.
            </p>
          )}

          {status === 'ready' && (
            <>
              <div className="flex flex-wrap items-center gap-2">
                <label htmlFor="profile-template" className="text-xs font-semibold text-text">Start from a template</label>
                <select
                  id="profile-template"
                  value=""
                  onChange={(event) => event.target.value && startFromTemplate(event.target.value)}
                  className="rounded-lg border border-border bg-white px-2 py-1 text-xs"
                >
                  <option value="">Choose…</option>
                  {info.templates.map((template) => (
                    <option key={template.code} value={template.code}>{template.title}</option>
                  ))}
                </select>
              </div>

              {rows.length === 0 && (
                <p className="rounded-lg border border-dashed border-border px-4 py-6 text-center text-sm text-text-muted">
                  No competencies yet. Start from a template, or add your own.
                </p>
              )}

              <ul className="space-y-2">
                {rows.map((row, index) => (
                  <li key={row.key} className="flex flex-wrap items-center gap-2 rounded-lg border border-border p-2">
                    <input
                      aria-label={`Competency ${index + 1} name`}
                      value={row.name}
                      onChange={(event) => change(index, 'name', event.target.value)}
                      placeholder="Competency"
                      className="min-w-0 flex-1 rounded-lg border border-border px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-blue/40"
                    />
                    <label className="flex items-center gap-1 text-xs text-text-muted">
                      <input
                        aria-label={`Competency ${index + 1} weight`}
                        type="number"
                        min={1}
                        max={100}
                        value={row.weight}
                        onChange={(event) => change(index, 'weight', event.target.value === '' ? '' : Number(event.target.value))}
                        className="w-16 rounded-lg border border-border px-2 py-1.5 text-sm text-text"
                      />
                      %
                    </label>
                    <label className="flex items-center gap-1 text-xs text-text">
                      <input
                        type="checkbox"
                        aria-label={`Competency ${index + 1} is key`}
                        checked={row.isKey}
                        onChange={(event) => change(index, 'isKey', event.target.checked)}
                      />
                      Key
                    </label>
                    <button
                      type="button"
                      onClick={() => edit((list) => list.filter((_, position) => position !== index))}
                      aria-label={`Remove competency ${index + 1}`}
                      className="rounded p-1 text-red-600 hover:bg-red-50"
                    >
                      <Trash2 size={14} />
                    </button>
                  </li>
                ))}
              </ul>

              <div className="flex items-center justify-between gap-3">
                <button
                  type="button"
                  onClick={() => edit((list) => [...list, blankCompetency(newKey())])}
                  disabled={atLimit}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-xs font-semibold text-text transition-colors hover:bg-surface-muted disabled:opacity-50"
                >
                  <Plus size={13} /> Add a competency
                </button>
                <span
                  data-testid="weight-total"
                  className={total === 100 ? 'text-xs font-medium text-green-700' : 'text-xs font-medium text-red-600'}
                >
                  Weights: {total}% of 100%
                </span>
              </div>

              <div className="space-y-2 rounded-lg border border-border p-3">
                <p className="text-xs font-semibold text-text">Key competencies</p>
                <label className="flex flex-wrap items-center gap-2 text-xs text-text-muted">
                  A key competency rated under
                  <select
                    aria-label="Minimum rating for key competencies"
                    value={keyMin}
                    onChange={(event) => { setKeyMin(Number(event.target.value)); setDirty(true) }}
                    className="rounded-lg border border-border bg-white px-2 py-1 text-xs text-text"
                  >
                    {[1, 2, 3, 4, 5].map((n) => <option key={n} value={n}>{n}</option>)}
                  </select>
                  out of 5 is flagged, and the band is held at Hold for evidence. It never rejects anyone: a person decides.
                </label>
              </div>

              <div className="space-y-2 rounded-lg border border-border p-3">
                <p className="text-xs font-semibold text-text">Suggested bands (provisional)</p>
                <p className="text-xs text-text-muted">
                  A label on the weighted total, for the panel to read. The thresholds are proposals, not validated cutoffs.
                </p>
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
                  {['strong', 'shortlist', 'hold'].map((band) => (
                    <label key={band} className="flex items-center gap-2 text-xs text-text-muted">
                      <span className="w-28">{BAND_NAMES[band]} from</span>
                      <input
                        aria-label={`${BAND_NAMES[band]} from`}
                        type="number"
                        min={1}
                        max={100}
                        value={bands[band]}
                        onChange={(event) => { setBands({ ...bands, [band]: event.target.value === '' ? '' : Number(event.target.value) }); setDirty(true) }}
                        className="w-16 rounded-lg border border-border px-2 py-1 text-sm text-text"
                      />
                    </label>
                  ))}
                </div>
                <p className="text-xs text-text-muted">Under {bands.hold || '…'}: {BAND_NAMES.not}.</p>
              </div>

              {dirty && problems.length > 0 && (
                <ul role="alert" data-testid="profile-problems" className="space-y-0.5 text-xs text-red-600">
                  {problems.map((problem) => <li key={problem}>{problem}</li>)}
                </ul>
              )}
              {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
            </>
          )}
        </div>

        <div className="flex items-center justify-between gap-3 p-6 pt-3">
          <div>
            {hasProfile && (
              <button
                type="button"
                onClick={remove}
                disabled={saving}
                className="text-xs font-medium text-red-600 underline hover:text-red-700 disabled:opacity-50"
              >
                Remove the scoring profile
              </button>
            )}
          </div>
          <div className="flex items-center gap-2">
            <button type="button" onClick={close} className="rounded-lg border border-border px-4 py-2 text-sm font-medium text-text hover:bg-surface-muted">
              Cancel
            </button>
            <button
              type="button"
              onClick={save}
              disabled={saving || status !== 'ready' || problems.length > 0 || !dirty}
              className="inline-flex items-center gap-1.5 rounded-lg bg-brand-blue px-4 py-2 text-sm font-semibold text-white hover:bg-brand-blue/90 disabled:opacity-50"
            >
              {saving && <Loader2 size={14} className="animate-spin" />}
              Save scoring profile
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
