import { useEffect, useRef, useState } from 'react'
import { Check, Copy, Loader2, Share2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import api from '@/lib/api'

const endpoint = (jobId) => `/api/v1/interview-share/jobs/${jobId}`

function formatWhen(iso) {
  return new Date(iso).toLocaleString('en-GB', {
    day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit',
  })
}

/**
 * Share a job's interview results with someone who will not log in (a client): one link
 * per job that opens a read-only page with each candidate's interview and CV assessment,
 * the recording, the questions the AI asked and the transcript. The link works for 3 days,
 * and making a new one stops the old one.
 */
export default function ShareInterviewResults({ jobId }) {
  const [link, setLink] = useState(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [copied, setCopied] = useState(false)
  const input = useRef(null)

  useEffect(() => {
    let cancelled = false
    api.get(endpoint(jobId))
      .then(({ data }) => { if (!cancelled) setLink(data.link) })
      .catch(() => { if (!cancelled) setError('We could not check this job’s share link.') })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [jobId])

  const run = async (action) => {
    setBusy(true)
    setError(null)
    try {
      await action()
    } catch (err) {
      setError(err.response?.data?.message ?? 'That did not work. Please try again.')
    } finally {
      setBusy(false)
    }
  }

  const create = () => run(async () => {
    const { data } = await api.post(endpoint(jobId))
    setLink(data)
    setCopied(false)
  })

  const replace = () => {
    if (!window.confirm('This stops the current link working and makes a new one. Continue?')) return
    create()
  }

  const stop = () => {
    if (!window.confirm('Anyone with the current link will no longer be able to open it. Continue?')) return
    run(async () => {
      await api.delete(endpoint(jobId))
      setLink(null)
    })
  }

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(link.url)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // The clipboard can be refused (an insecure page, a locked-down browser): select
      // the link so it can be copied by hand.
      input.current?.select()
    }
  }

  if (loading) return null

  const live = link && !link.expired

  return (
    <div className="rounded-xl border border-border bg-white p-4 space-y-3">
      <div className="flex items-start gap-2">
        <Share2 size={16} className="text-brand-blue mt-0.5 shrink-0" aria-hidden="true" />
        <div>
          <h3 className="text-sm font-semibold text-text">Share results with your client</h3>
          <p className="text-xs text-text-muted mt-0.5">
            Anyone with the link can see each candidate&apos;s interview and CV assessment, the
            recording and the transcript, with no login. It works for 3 days.
          </p>
        </div>
      </div>

      {error && (
        <p role="alert" className="text-xs text-red-600">{error}</p>
      )}

      {!live && (
        <div className="space-y-2">
          {link?.expired && (
            <p className="text-xs text-amber-800">
              The last link expired on {formatWhen(link.expires_at)}.
            </p>
          )}
          <Button size="sm" onClick={create} disabled={busy}>
            {busy ? <Loader2 size={14} className="animate-spin" /> : link?.expired ? 'Make a new link' : 'Create link'}
          </Button>
        </div>
      )}

      {live && (
        <div className="space-y-2">
          <div className="flex gap-2">
            <input
              ref={input}
              readOnly
              value={link.url}
              aria-label="Interview results link"
              onFocus={(e) => e.target.select()}
              className="flex-1 min-w-0 rounded-lg border border-border bg-surface-muted px-3 py-1.5 text-xs text-text"
            />
            <Button size="sm" variant="outline" onClick={copy}>
              {copied ? <><Check size={14} /> Copied</> : <><Copy size={14} /> Copy</>}
            </Button>
          </div>
          <p className="text-xs text-text-muted">
            Expires {formatWhen(link.expires_at)}.{' '}
            {link.view_count === 0
              ? 'Not opened yet.'
              : `Opened ${link.view_count} ${link.view_count === 1 ? 'time' : 'times'}, last on ${formatWhen(link.last_viewed_at)}.`}
          </p>
          <div className="flex gap-3">
            <button type="button" onClick={replace} disabled={busy} className="text-xs text-brand-blue hover:underline disabled:opacity-60">
              Make a new link
            </button>
            <button type="button" onClick={stop} disabled={busy} className="text-xs text-red-600 hover:underline disabled:opacity-60">
              Stop sharing
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
