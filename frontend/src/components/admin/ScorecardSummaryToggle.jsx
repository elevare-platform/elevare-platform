import { useEffect, useState } from 'react'
import api from '@/lib/api'
import { cn } from '@/lib/utils'

/**
 * ScorecardSummaryToggle - the admin's switch for a job's scorecard Evaluation Summary (practical
 * case rating, strengths, human decision). Off: the scorecard is shown and printed without that
 * section for everyone, and the review panel does not offer its fields. What was filled in is kept,
 * so switching back on shows it again. Elevare admins only (the server refuses anyone else).
 */
export default function ScorecardSummaryToggle({ jobId }) {
  const [show, setShow] = useState(null) // null until the server has said
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)
  const [readError, setReadError] = useState(null)

  useEffect(() => {
    let cancelled = false
    api
      .get(`/api/v1/interviews/jobs/${jobId}/scorecard-summary`)
      .then(({ data }) => {
        if (!cancelled) setShow(Boolean(data.show_summary))
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
      const { data } = await api.put(`/api/v1/interviews/jobs/${jobId}/scorecard-summary`, {
        show_summary: !show,
      })
      setShow(Boolean(data.show_summary))
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
        aria-label="Show the scorecard's Evaluation Summary"
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
        <p className="text-sm font-semibold text-text">Show the scorecard&apos;s Evaluation Summary</p>
        <p className="text-xs text-text-muted">
          {show === false
            ? 'Off: the scorecard has no Evaluation Summary (practical case rating, strengths, human decision) here, on the shared link or in the PDF.'
            : 'On: the scorecard ends with its Evaluation Summary: practical case rating, strengths and human decision.'}
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
