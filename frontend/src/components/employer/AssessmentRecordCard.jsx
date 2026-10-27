import { useState } from 'react'
import { FileText, Loader2 } from 'lucide-react'

const PANEL_DECISIONS = [
  { value: 'STRONG_SHORTLIST', label: 'Strong shortlist' },
  { value: 'SHORTLIST', label: 'Shortlist' },
  { value: 'HOLD', label: 'Hold' },
  { value: 'DO_NOT_SHORTLIST', label: 'Do not shortlist' },
]

// The shortest reason that says something: a sentence or two (the server checks the same).
const MIN_RATIONALE_CHARS = 10

const formatDate = (iso) =>
  iso ? new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }) : null

function List({ title, items, ordered = false, empty }) {
  const Tag = ordered ? 'ol' : 'ul'
  return (
    <div className="space-y-1">
      <p className="text-xs font-semibold text-text">{title}</p>
      {items.length > 0 ? (
        <Tag className={`space-y-0.5 pl-4 text-xs text-text ${ordered ? 'list-decimal' : 'list-disc'}`}>
          {items.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </Tag>
      ) : (
        <p className="text-xs text-text-muted">{empty}</p>
      )}
    </div>
  )
}

/**
 * AssessmentRecordCard - the candidate assessment record the client's pack asks for: who, when and
 * for what role, the top three strengths and gaps, what to verify and what to ask referees, and
 * the hiring panel's decision with its reason and sign-off (docs/16_COLTON_BRIEF.md, Section 7).
 *
 * `onDecide(decision, rationale)` makes the panel decision part editable (the employer's own
 * view); without it, as on a shared link, the decision is not shown at all, because it is the
 * company's internal decision. The decision is always a person's: it stops at the shortlist.
 */
export default function AssessmentRecordCard({ record, onDecide }) {
  const [decision, setDecision] = useState('')
  const [rationale, setRationale] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)

  const latest = record.panel_decision
  const date = formatDate(record.interview_date)
  const tooShort = rationale.trim().length < MIN_RATIONALE_CHARS

  const submit = async (event) => {
    event.preventDefault()
    setSaving(true)
    setError(null)
    try {
      await onDecide(decision, rationale.trim())
      setDecision('')
      setRationale('')
    } catch (err) {
      const body = err?.response?.data
      setError(body?.details?.map((item) => item.message).join(' ') || body?.message || 'Something went wrong. Please try again.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <section className="space-y-4 rounded-xl border border-border p-4" data-testid="assessment-record" aria-label="Candidate assessment record">
      <p className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-text-muted">
        <FileText size={12} aria-hidden="true" /> Candidate assessment record
      </p>

      <dl className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-xs sm:grid-cols-3">
        <div>
          <dt className="text-text-muted">Reference</dt>
          <dd className="font-medium text-text" data-testid="record-reference">{record.reference}</dd>
        </div>
        <div>
          <dt className="text-text-muted">Role</dt>
          <dd className="font-medium text-text">{record.role}</dd>
        </div>
        <div>
          <dt className="text-text-muted">Date</dt>
          <dd className="font-medium text-text">{date ?? 'Not recorded'}</dd>
        </div>
        <div>
          <dt className="text-text-muted">Interview length</dt>
          <dd className="font-medium text-text">
            {record.duration_minutes != null ? `${record.duration_minutes} min` : 'Not recorded'}
          </dd>
        </div>
        <div className="col-span-2">
          <dt className="text-text-muted">Interviewer</dt>
          <dd className="font-medium text-text">{record.interviewer}</dd>
        </div>
      </dl>

      <div className="grid gap-4 sm:grid-cols-2">
        <List title="Top three demonstrated strengths" items={record.top_strengths} ordered empty="None recorded." />
        <List title="Top three gaps or risks" items={record.top_gaps} ordered empty="None recorded." />
      </div>
      <List
        title="Unverified claims (what the candidate said, not checked)"
        items={record.claims_to_verify}
        empty="None to check."
      />
      <List
        title="Questions for referees"
        items={record.reference_check_questions}
        empty="None suggested."
      />

      {onDecide && (
        <div className="space-y-3 border-t border-border pt-3" data-testid="panel-decision">
          <p className="text-xs font-semibold text-text">Hiring panel decision</p>
          <p className="text-xs text-text-muted">
            Recorded by a person, with the reason. The assessment above only supports it; it never decides.
          </p>

          {latest ? (
            <div className="rounded-lg bg-surface-muted/50 px-3 py-2 text-xs" data-testid="latest-decision">
              <p className="font-semibold text-text">{latest.label}</p>
              <p className="mt-0.5 whitespace-pre-wrap text-text">{latest.rationale}</p>
              <p className="mt-1 text-text-muted">
                Signed off by {latest.decided_by_name} on {formatDate(latest.decided_at)}
              </p>
            </div>
          ) : (
            <p className="text-xs text-text-muted" data-testid="no-decision">No decision recorded yet.</p>
          )}

          <form onSubmit={submit} className="space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <label htmlFor="panel-decision-choice" className="text-xs text-text-muted">
                {latest ? 'Change the decision' : 'Decision'}
              </label>
              <select
                id="panel-decision-choice"
                value={decision}
                onChange={(event) => setDecision(event.target.value)}
                className="rounded-lg border border-border bg-white px-2 py-1 text-xs"
              >
                <option value="">Choose…</option>
                {PANEL_DECISIONS.map((item) => (
                  <option key={item.value} value={item.value}>{item.label}</option>
                ))}
              </select>
            </div>
            <label htmlFor="panel-decision-reason" className="sr-only">Reason for the decision</label>
            <textarea
              id="panel-decision-reason"
              value={rationale}
              onChange={(event) => setRationale(event.target.value)}
              rows={2}
              maxLength={2000}
              placeholder="Why the panel decided this, in a sentence or two"
              className="w-full rounded-lg border border-border px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-brand-blue/40"
            />
            {error && (
              <p role="alert" className="text-xs text-red-600">{error}</p>
            )}
            <button
              type="submit"
              disabled={!decision || tooShort || saving}
              className="inline-flex items-center gap-1.5 rounded-lg bg-brand-blue px-3 py-1.5 text-xs font-semibold text-white transition-colors hover:bg-brand-blue/90 disabled:opacity-50"
            >
              {saving && <Loader2 size={13} className="animate-spin" />}
              {saving ? 'Saving…' : 'Record decision'}
            </button>
          </form>
        </div>
      )}
    </section>
  )
}
