import { useEffect, useState } from 'react'
import api from '@/lib/api'
import { cn } from '@/lib/utils'

// The three parts of a job's interview results an Elevare admin can leave out for employers and
// the shared link. Each is on until switched off; an admin always sees everything.
const SWITCHES = [
  {
    field: 'show_score_number',
    label: 'Show the score number',
    on: 'On: the total score and the points are shown, with the band.',
    off: 'Off: no total, no points and no cut-offs. The suggested band and the 1 to 5 ratings are still shown.',
  },
  {
    field: 'show_gaps',
    label: 'Show the gaps and risks',
    on: 'On: the top three gaps or risks and the gaps and risks in the written assessment are shown.',
    off: 'Off: the top three gaps or risks and the gaps and risks in the written assessment are left out.',
  },
  {
    field: 'show_writeup',
    label: 'Show the written assessment',
    on: 'On: the written assessment under Interview Assessment is shown.',
    off: 'Off: the written assessment is not shown here or on the shared link. The band, ratings and scorecard are still shown.',
  },
]

/**
 * ResultDisplayToggles - the admin's switches for what an employer and the shared link are shown of
 * a job's interview results: the score number, the gaps and risks, the written assessment. Nothing
 * is deleted: switching back on shows it all again, and an admin always sees everything. Elevare
 * admins only (the server refuses anyone else).
 */
export default function ResultDisplayToggles({ jobId }) {
  const url = `/api/v1/interviews/jobs/${jobId}/result-display`
  const [shown, setShown] = useState(null) // null until the server has said
  const [saving, setSaving] = useState(null) // the field being changed
  const [error, setError] = useState(null)
  const [readError, setReadError] = useState(null)

  useEffect(() => {
    let cancelled = false
    api
      .get(`/api/v1/interviews/jobs/${jobId}/result-display`)
      .then(({ data }) => {
        if (!cancelled) setShown(data)
      })
      .catch(() => {
        if (!cancelled) setReadError('We could not read these settings.')
      })
    return () => {
      cancelled = true
    }
  }, [jobId])

  const flip = async (field) => {
    if (saving || shown === null) return
    setSaving(field)
    setError(null)
    try {
      const { data } = await api.put(url, { [field]: !shown[field] })
      setShown(data)
    } catch (err) {
      const message = err?.response?.data?.message
      setError(
        err?.response
          ? (typeof message === 'string' ? message : 'Something went wrong. Please try again.')
          : 'We could not reach the server. Check your connection and try again.'
      )
    } finally {
      setSaving(null)
    }
  }

  return (
    <div className="space-y-2 rounded-xl border border-border bg-white px-4 py-3" data-testid="result-display">
      {SWITCHES.map(({ field, label, on, off }) => {
        const isOn = shown?.[field]
        return (
          <div key={field} className="flex flex-wrap items-center gap-3">
            <button
              type="button"
              role="switch"
              aria-checked={isOn === true}
              aria-label={label}
              disabled={shown === null || saving !== null}
              onClick={() => flip(field)}
              className={cn(
                'relative inline-flex h-6 w-11 flex-shrink-0 items-center rounded-full transition-colors disabled:opacity-50',
                isOn ? 'bg-brand-blue' : 'bg-gray-300'
              )}
            >
              <span
                className={cn(
                  'inline-block h-5 w-5 rounded-full bg-white shadow transition-transform',
                  isOn ? 'translate-x-5' : 'translate-x-0.5'
                )}
              />
            </button>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-semibold text-text">{label}</p>
              <p className="text-xs text-text-muted">{isOn === false ? off : on}</p>
            </div>
          </div>
        )
      })}
      {readError && <p className="text-xs text-text-muted">{readError}</p>}
      {error && (
        <p role="alert" className="text-xs text-red-600">
          {error}
        </p>
      )}
    </div>
  )
}
