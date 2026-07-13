import { useEffect, useState } from 'react'
import { X, MapPin, Briefcase, Calendar, Building2, Users, Mail, Phone, Globe, ExternalLink } from 'lucide-react'
import StatusBadge from './StatusBadge'
import api from '@/lib/api'

export default function JobDetailDrawer({ jobId, onClose, onModerate }) {
  const [job, setJob] = useState(null)
  const [loading, setLoading] = useState(false)
  const [rejectMode, setRejectMode] = useState(false)
  const [reason, setReason] = useState('')
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    if (!jobId) return
    setLoading(true)
    setRejectMode(false)
    setReason('')
    api.get(`/api/v1/jobs/${jobId}`)
      .then((r) => setJob(r.data))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [jobId])

  const handleModerate = async (action, moderationReason = null) => {
    setSubmitting(true)
    try {
      await api.patch(`/api/v1/admin/jobs/${jobId}/moderate`, {
        action,
        reason: moderationReason || null,
      })
      const r = await api.get(`/api/v1/jobs/${jobId}`)
      setJob(r.data)
      setRejectMode(false)
      setReason('')
      onModerate?.()
    } catch { /* silently fail */ }
    finally { setSubmitting(false) }
  }

  return (
    <div className="fixed inset-0 z-40 flex justify-end">
      <div className="absolute inset-0 bg-black/30" onClick={onClose} />
      <aside
        className="relative z-50 w-full max-w-lg bg-white h-full shadow-xl flex flex-col overflow-y-auto"
        role="dialog"
        aria-label="Job details"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border">
          <h2 className="font-semibold text-text">Job Details</h2>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-surface-muted" aria-label="Close">
            <X size={16} />
          </button>
        </div>

        {loading && (
          <div className="flex-1 flex items-center justify-center">
            <div className="w-6 h-6 border-2 border-brand-blue border-t-transparent rounded-full animate-spin" />
          </div>
        )}

        {!loading && job && (
          <div className="flex-1 px-6 py-5 space-y-6">
            {/* Title + badges */}
            <div>
              <h3 className="text-xl font-bold text-text font-sans">{job.title}</h3>
              <div className="flex flex-wrap gap-2 mt-2">
                <StatusBadge value={job.status} />
                <StatusBadge value={job.moderation_status} />
                {job.contract_type && <StatusBadge value={job.contract_type} />}
              </div>
            </div>

            {/* Company + Employer info */}
            <div className="rounded-xl border border-border divide-y divide-border">
              {/* Company section */}
              <div className="flex items-start gap-3 p-4">
                <Building2 size={16} className="text-text-muted flex-shrink-0 mt-0.5" />
                <div className="min-w-0">
                  <p className="font-semibold text-sm text-text">
                    {job.company_name ?? '—'}
                  </p>
                  <p className="text-xs text-text-muted mt-0.5">
                    {[job.company_industry, job.company_size ? `${job.company_size} employees` : null]
                      .filter(Boolean).join(' · ') || 'No company details'}
                  </p>
                  {job.company_website && (
                    <a
                      href={job.company_website}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 text-xs text-brand-blue hover:underline mt-1"
                    >
                      <Globe size={11} />
                      {job.company_website}
                      <ExternalLink size={10} />
                    </a>
                  )}
                  {job.company_description && (
                    <p className="text-xs text-text-muted mt-1.5 leading-relaxed">{job.company_description}</p>
                  )}
                </div>
              </div>

              {/* Employer contact section */}
              <div className="p-4 space-y-2">
                <p className="text-xs font-semibold text-text-muted uppercase tracking-wider">Employer Contact</p>
                {(job.employer_first_name || job.employer_last_name) && (
                  <p className="text-sm text-text font-medium">
                    {[job.employer_first_name, job.employer_last_name].filter(Boolean).join(' ')}
                  </p>
                )}
                {job.employer_email && (
                  <a
                    href={`mailto:${job.employer_email}`}
                    className="flex items-center gap-2 text-xs text-brand-blue hover:underline"
                  >
                    <Mail size={12} />
                    {job.employer_email}
                  </a>
                )}
                {job.employer_phone && (
                  <div className="flex items-center gap-2 text-xs text-text-muted">
                    <Phone size={12} />
                    {job.employer_phone}
                  </div>
                )}
                {!job.employer_email && !job.employer_phone && (
                  <p className="text-xs text-text-muted italic">No contact details available</p>
                )}
              </div>
            </div>

            {/* Meta */}
            <div className="grid grid-cols-2 gap-3 text-sm">
              {job.location && (
                <div className="flex items-center gap-2 text-text-muted">
                  <MapPin size={13} />
                  <span>{job.location}</span>
                </div>
              )}
              {job.work_model && (
                <div className="flex items-center gap-2 text-text-muted">
                  <Briefcase size={13} />
                  <span>{job.work_model}</span>
                </div>
              )}
              {job.openings_count && (
                <div className="flex items-center gap-2 text-text-muted">
                  <Users size={13} />
                  <span>{job.openings_count} opening{job.openings_count !== 1 ? 's' : ''}</span>
                </div>
              )}
              {job.created_at && (
                <div className="flex items-center gap-2 text-text-muted">
                  <Calendar size={13} />
                  <span>{new Date(job.created_at).toLocaleDateString()}</span>
                </div>
              )}
            </div>

            {/* Salary */}
            {(job.salary_min || job.salary_max) && (
              <div className="rounded-xl border border-border p-4">
                <p className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-1">Salary</p>
                <p className="text-sm text-text">
                  {job.salary_min && `₦${Number(job.salary_min).toLocaleString()}`}
                  {job.salary_min && job.salary_max && ' – '}
                  {job.salary_max && `₦${Number(job.salary_max).toLocaleString()}`}
                </p>
              </div>
            )}

            {/* Skills */}
            {job.required_skills?.length > 0 && (
              <div>
                <p className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-2">Required Skills</p>
                <div className="flex flex-wrap gap-2">
                  {job.required_skills.map((s) => (
                    <span key={s} className="px-2 py-0.5 bg-surface-muted rounded-full text-xs text-text-muted">
                      {s}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Description — structured (new jobs) or legacy fallback */}
            <div>
              <p className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-2">Description</p>
              {job.about_the_role ? (
                <div className="space-y-4">
                  {[
                    ['About the Role',          job.about_the_role],
                    ['Key Responsibilities',    job.key_responsibilities],
                    ['Requirements',            job.requirements],
                    ['Preferred Certifications',job.preferred_certifications],
                    ['Technical Competencies',  job.technical_competencies],
                    ['What We Offer',           job.what_we_offer],
                  ].map(([label, content]) =>
                    content ? (
                      <div key={label}>
                        <p className="text-xs font-medium text-text mb-1">{label}</p>
                        <p className="text-sm text-text-muted leading-relaxed whitespace-pre-line">{content}</p>
                      </div>
                    ) : null
                  )}
                </div>
              ) : (
                <p className="text-sm text-text leading-relaxed whitespace-pre-line">
                  {job.description ?? '—'}
                </p>
              )}
            </div>

            {/* Moderation actions */}
            <div className="space-y-2 pt-2 border-t border-border">
              <p className="text-xs font-semibold text-text-muted uppercase tracking-wider">Moderation</p>

              {/* Reject reason form */}
              {rejectMode && (
                <div className="space-y-2">
                  <label htmlFor="reject-reason" className="text-xs text-text-muted">
                    Reason for rejection (optional — shown to employer)
                  </label>
                  <textarea
                    id="reject-reason"
                    rows={3}
                    value={reason}
                    onChange={(e) => setReason(e.target.value)}
                    placeholder="e.g. Job description violates posting guidelines…"
                    className="w-full text-sm rounded-lg border border-border px-3 py-2 focus:outline-none focus:ring-2 focus:ring-brand-blue resize-none"
                  />
                  <div className="flex gap-2">
                    <button
                      onClick={() => handleModerate('reject', reason)}
                      disabled={submitting}
                      className="px-4 py-2 text-sm rounded-lg bg-red-100 text-red-700 hover:bg-red-200 font-medium transition-colors disabled:opacity-50"
                    >
                      {submitting ? 'Rejecting…' : 'Confirm Reject'}
                    </button>
                    <button
                      onClick={() => { setRejectMode(false); setReason('') }}
                      className="px-4 py-2 text-sm rounded-lg border border-border text-text-muted hover:bg-surface-muted font-medium transition-colors"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              )}

              {!rejectMode && (
                <div className="flex flex-wrap gap-2">
                  {job.moderation_status === 'PENDING' && (
                    <>
                      <button
                        onClick={() => handleModerate('approve')}
                        disabled={submitting}
                        className="px-4 py-2 text-sm rounded-lg bg-green-100 text-green-700 hover:bg-green-200 font-medium transition-colors disabled:opacity-50"
                      >
                        Approve
                      </button>
                      <button
                        onClick={() => setRejectMode(true)}
                        className="px-4 py-2 text-sm rounded-lg bg-red-100 text-red-700 hover:bg-red-200 font-medium transition-colors"
                      >
                        Reject
                      </button>
                    </>
                  )}
                  {job.status === 'ACTIVE' && (
                    <button
                      onClick={() => handleModerate('close')}
                      disabled={submitting}
                      className="px-4 py-2 text-sm rounded-lg border border-border text-text-muted hover:bg-surface-muted font-medium transition-colors disabled:opacity-50"
                    >
                      Close Job
                    </button>
                  )}
                  {job.moderation_status === 'APPROVED' && job.status !== 'ACTIVE' && (
                    <p className="text-xs text-text-muted italic">No moderation actions available.</p>
                  )}
                  {job.moderation_status === 'REJECTED' && (
                    <button
                      onClick={() => handleModerate('approve')}
                      disabled={submitting}
                      className="px-4 py-2 text-sm rounded-lg bg-green-100 text-green-700 hover:bg-green-200 font-medium transition-colors disabled:opacity-50"
                    >
                      Re-approve
                    </button>
                  )}
                </div>
              )}
            </div>
          </div>
        )}
      </aside>
    </div>
  )
}
