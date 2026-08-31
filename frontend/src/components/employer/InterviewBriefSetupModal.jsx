import { useState } from 'react'
import { X } from 'lucide-react'
import api from '@/lib/api'

/**
 * InterviewBriefSetupModal - lets an employer add a job's AI interview brief
 * inline, without leaving the Applicants page, so the "Send interview link"
 * flow doesn't need a separate trip to Edit Job.
 */
export default function InterviewBriefSetupModal({ jobId, onClose, onSaved }) {
  const [brief, setBrief] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!brief.trim()) {
      setError('Enter a brief for the AI interviewer to work from.')
      return
    }
    setLoading(true)
    setError(null)
    try {
      const { data } = await api.patch(`/api/v1/jobs/${jobId}`, { interview_brief: brief.trim() })
      onSaved(data)
    } catch (err) {
      const body = err.response?.data
      if (body?.details?.length > 0) {
        setError(body.details.map((e) => `${e.field}: ${e.message}`).join(' · '))
      } else {
        const msg = body?.message ?? body?.detail
        setError(typeof msg === 'string' ? msg : 'Something went wrong. Please try again.')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4">
      <div className="w-full max-w-lg rounded-xl border border-border bg-white p-6 space-y-4">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-lg font-bold text-text">Set up AI interview</h2>
            <p className="text-sm text-text-muted mt-1">
              This brief tells the AI interviewer what to ask about. It is never shown to
              candidates directly.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-text-muted hover:text-text flex-shrink-0"
            aria-label="Close"
          >
            <X size={18} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-3">
          <textarea
            value={brief}
            onChange={(e) => setBrief(e.target.value)}
            rows={6}
            placeholder="e.g. Screen for 3+ years of backend experience, focus on system design and past ownership of production incidents..."
            className="w-full rounded-lg border border-border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-blue/40"
          />
          {error && <p className="text-xs text-red-600">{error}</p>}
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              className="px-3 py-1.5 rounded-lg text-xs font-semibold text-text-muted hover:bg-surface-muted transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-brand-blue text-white hover:bg-brand-blue/90 transition-colors disabled:opacity-50"
            >
              {loading ? 'Saving…' : 'Save and enable'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
