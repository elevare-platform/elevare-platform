import { useEffect, useState } from 'react'
import api from '@/lib/api'
import { cn } from '@/lib/utils'

/**
 * ScoreVisibilityToggle - the switch for a job's interview score and provisional band. Off: the
 * employer's screens and the shared link are not sent the total, the band, the practical case's
 * total or the assessment lines that state them; the competency ratings and the evidence stay.
 * The scores are still worked out and kept, so switching back on shows them all again.
 * For the job's company or an Elevare admin (the server refuses anyone else).
 */
export default function ScoreVisibilityToggle({ jobId }) {
  const [show, setShow] = useState(null) // null until the server has said
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)
  const [readError, setReadError] = useState(null)

  useEffect(() => {
    let cancelled = false
    api
      .get(`/api/v1/interviews/jobs/${jobId}/score-visibility`)
      .then(({ data }) => {
        if (!cancelled) setShow(Boolean(data.show_scores))
      })
      .catch(() => {
        if (!cancelled) setReadError('We could not read this setting.')
      })
    return () => {
      cancelled = true
    }
  }, [jobId])

  const flip = async () => {
    if (saving || show === null) return
    setSaving(true)
    setError(null)
    try {
      const { data } = await api.put(`/api/v1/interviews/jobs/${jobId}/score-visibility`, {
        show_scores: !show,
      })
      setShow(Boolean(data.show_scores))
    } catch (err) {
      const message = err?.response?.data?.message
      setError(
        err?.response
          ? (typeof message === 'string' ? message : 'Something went wrong. Please try again.')
          : 'We could not reach the server. Check your connection and try again.'
      )
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-3 rounded-xl border border-border bg-white px-4 py-3">
      <button
        type="button"
        role="switch"
        aria-checked={show === true}
        aria-label="Show interview scores and suggested bands"
        disabled={show === null || saving}
        onClick={flip}
        className={cn(
          'relative inline-flex h-6 w-11 flex-shrink-0 items-center rounded-full transition-colors disabled:opacity-50',
          show ? 'bg-brand-blue' : 'bg-gray-300'
        )}
      >
        <span
          className={cn(
            'inline-block h-5 w-5 rounded-full bg-white shadow transition-transform',
            show ? 'translate-x-5' : 'translate-x-0.5'
          )}
        />
      </button>
      <div className="min-w-0 flex-1">
        <p className="text-sm font-semibold text-text">Show interview scores and suggested bands</p>
        <p className="text-xs text-text-muted">
          {show === false
            ? 'Off: the total score and the provisional band are not shown here or on the shared link. The ratings and the evidence still are.'
            : 'On: the total score and the provisional band are shown here and on the shared link.'}
        </p>
        {readError && <p className="text-xs text-text-muted">{readError}</p>}
        {error && (
          <p role="alert" className="text-xs text-red-600">
            {error}
          </p>
        )}
      </div>
    </div>
  )
}
