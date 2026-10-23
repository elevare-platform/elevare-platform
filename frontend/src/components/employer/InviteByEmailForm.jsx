import { useState } from 'react'
import { Mail, Send } from 'lucide-react'
import api from '@/lib/api'

// A plain check so an obvious typo is caught before a request; the server checks it properly.
const LOOKS_LIKE_EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

function messageFrom(err) {
  const body = err?.response?.data
  const text = body?.message ?? body?.detail
  if (typeof text === 'string') return text
  if (err?.response?.status === 422) return 'That does not look like an email address.'
  return 'Something went wrong. Please try again.'
}

/**
 * InviteByEmailForm - sends a job's AI interview to a typed email address, with no CV and no
 * account needed. The address goes on the job's interview list (and stays there if the email
 * could not be sent, so it can be sent again from its row). `onInvited` runs after the server
 * has answered, so the list and the credits shown can be refreshed.
 */
export default function InviteByEmailForm({ jobId, onInvited }) {
  const [email, setEmail] = useState('')
  const [sending, setSending] = useState(false)
  const [result, setResult] = useState(null) // { ok: boolean, text: string }

  const submit = async (event) => {
    event.preventDefault()
    const address = email.trim()
    if (sending) return
    if (!LOOKS_LIKE_EMAIL.test(address)) {
      setResult({ ok: false, text: 'Enter a valid email address.' })
      return
    }
    setSending(true)
    setResult(null)
    try {
      const { data } = await api.post(`/api/v1/interviews/jobs/${jobId}/invite-by-email`, { email: address })
      if (data.sent) {
        setResult({ ok: true, text: `Interview link sent to ${address.toLowerCase()}.` })
        setEmail('')
      } else {
        setResult({
          ok: false,
          text: `${address.toLowerCase()} is on the interview list, but the link was not sent: ${data.reason}`,
        })
      }
      onInvited?.()
    } catch (err) {
      setResult({ ok: false, text: messageFrom(err) })
    } finally {
      setSending(false)
    }
  }

  return (
    // noValidate: the browser's own bubble would replace our message, which says it in our words.
    <form onSubmit={submit} noValidate className="rounded-xl border border-border bg-white p-3.5 space-y-2" aria-label="Invite by email">
      <p className="flex items-center gap-1.5 text-xs font-semibold text-text">
        <Mail size={13} aria-hidden="true" /> Send the interview to an email address
      </p>
      <p className="text-xs text-text-muted">
        No CV needed. The address is added to this list, so you can follow the interview here.
      </p>
      <div className="flex flex-wrap items-center gap-2">
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="candidate@example.com"
          aria-label="Candidate's email address"
          autoComplete="off"
          className="min-w-0 flex-1 rounded-lg border border-border px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-blue/40"
        />
        <button
          type="submit"
          disabled={sending || !email.trim()}
          className="inline-flex items-center gap-1.5 rounded-lg bg-brand-blue px-3 py-1.5 text-xs font-semibold text-white transition-colors hover:bg-brand-blue/90 disabled:opacity-50"
        >
          <Send size={13} /> {sending ? 'Sending…' : 'Send interview'}
        </button>
      </div>
      {result && (
        <p role={result.ok ? 'status' : 'alert'} className={result.ok ? 'text-xs text-green-700' : 'text-xs text-red-600'}>
          {result.text}
        </p>
      )}
    </form>
  )
}
