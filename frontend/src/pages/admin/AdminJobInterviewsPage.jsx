import { useEffect, useState, useCallback } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft, PlayCircle } from 'lucide-react'
import AdminLayout from '@/components/admin/AdminLayout'
import { AdminTable, Th, Td } from '@/components/admin/AdminTable'
import InterviewDetailModal from '@/components/employer/InterviewDetailModal'
import ReviewedTag from '@/components/employer/ReviewedTag'
import api from '@/lib/api'
import { cn } from '@/lib/utils'

// What an interview's state is called here. A FAILED interview is told apart by why it failed.
const STATUS = {
  PENDING: { label: 'Sent: awaiting response', className: 'text-amber-600' },
  IN_PROGRESS: { label: 'In progress', className: 'text-blue-600' },
  UPLOADED: { label: 'Being scored', className: 'text-blue-600' },
  SCORED: { label: 'Completed', className: 'text-green-600' },
  EXPIRED: { label: 'Link expired', className: 'text-red-600' },
  ENDED_CONDUCT: { label: 'Ended early', className: 'text-amber-600' },
  STOPPED: { label: 'Stopped by the candidate', className: 'text-amber-600' },
}
const FAILED = {
  NEVER_FINISHED: { label: 'Recording not received', className: 'text-red-600' },
  SCORING_FAILED: { label: 'Scoring failed', className: 'text-red-600' },
}

// An interview there is something to open for.
const OPENABLE = ['UPLOADED', 'SCORED', 'ENDED_CONDUCT', 'STOPPED', 'FAILED']

function statusOf(item) {
  if (item.interview_status === 'FAILED') return FAILED[item.interview_failure] ?? FAILED.SCORING_FAILED
  return STATUS[item.interview_status] ?? { label: 'Not invited yet', className: 'text-text-muted' }
}

/**
 * AdminJobInterviewsPage - an Elevare administrator's view of one job's interview list, for any
 * account's job (the Colton account's included): who was interviewed, the score shown for each
 * scored interview, and "Review interview", which opens the same window the employer has plus the
 * admin-only box to change the competency ratings and the total.
 */
export default function AdminJobInterviewsPage() {
  const { jobId } = useParams()
  const [job, setJob] = useState(null)
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [open, setOpen] = useState(null)

  // Reads the job's interview list: the items, or the words for why they could not be read.
  const fetchList = useCallback(
    () =>
      api
        .get('/api/v1/interview-list', { params: { job_id: jobId } })
        .then(({ data }) => ({ items: data.items ?? [], error: null }))
        .catch((err) => ({
          items: null,
          error:
            err?.response?.status === 404
              ? 'That job could not be found.'
              : 'We could not load this job’s interviews. Please try again.',
        })),
    [jobId]
  )

  const showList = useCallback((result) => {
    if (result.items) setItems(result.items)
    setError(result.error)
    setLoading(false)
  }, [])

  useEffect(() => {
    let cancelled = false
    fetchList().then((result) => {
      if (!cancelled) showList(result)
    })
    // The job's name is a courtesy: the list works without it.
    api
      .get(`/api/v1/jobs/${jobId}`)
      .then(({ data }) => {
        if (!cancelled) setJob(data)
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [fetchList, showList, jobId])

  return (
    <AdminLayout>
      <div className="space-y-4">
        <div>
          <Link to="/admin/jobs" className="inline-flex items-center gap-1 text-xs font-medium text-brand-blue hover:underline">
            <ArrowLeft size={12} aria-hidden="true" /> Back to jobs
          </Link>
          <h1 className="mt-2 text-xl font-bold text-text">Interviews{job?.title ? `: ${job.title}` : ''}</h1>
          <p className="text-sm text-text-muted">
            Every candidate on this job&apos;s interview list. Open an interview to read it and to review its score.
          </p>
        </div>

        {error && (
          <p role="alert" className="text-sm text-red-600">
            {error}
          </p>
        )}

        {loading ? (
          <p className="text-sm text-text-muted">Loading…</p>
        ) : (
          !error && (
            <AdminTable isEmpty={items.length === 0} empty="Nobody is on this job's interview list yet.">
              <thead>
                <tr>
                  <Th>Candidate</Th>
                  <Th>Interview</Th>
                  <Th>Score</Th>
                  <Th>Actions</Th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => {
                  const status = statusOf(item)
                  return (
                    <tr key={item.id} className="hover:bg-surface-muted/50">
                      <Td>
                        <p className="font-medium text-text">{item.candidate_name ?? 'Unnamed candidate'}</p>
                        {item.current_title && <p className="text-xs text-text-muted">{item.current_title}</p>}
                      </Td>
                      <Td>
                        <span className={cn('text-xs font-medium', status.className)}>{status.label}</span>
                      </Td>
                      <Td>
                        {item.interview_score != null ? (
                          <span className="inline-flex items-center gap-1.5">
                            <span className="font-semibold text-text" data-testid="admin-score">{item.interview_score}</span>
                            {item.interview_reviewed && <ReviewedTag />}
                          </span>
                        ) : (
                          <span className="text-text-muted"> - </span>
                        )}
                      </Td>
                      <Td>
                        {OPENABLE.includes(item.interview_status) ? (
                          <button
                            type="button"
                            onClick={() => setOpen(item)}
                            className="inline-flex items-center gap-1 text-xs font-medium text-brand-blue hover:underline"
                          >
                            <PlayCircle size={13} aria-hidden="true" /> Review interview
                          </button>
                        ) : (
                          <span className="text-xs text-text-muted"> - </span>
                        )}
                      </Td>
                    </tr>
                  )
                })}
              </tbody>
            </AdminTable>
          )
        )}
      </div>

      {open && (
        <InterviewDetailModal
          jobId={jobId}
          talentPoolProfileId={open.talent_pool_profile_id}
          candidateName={open.candidate_name}
          onClose={() => {
            setOpen(null)
            // A score may have been reviewed in the window: read the list again.
            fetchList().then(showList)
          }}
        />
      )}
    </AdminLayout>
  )
}
