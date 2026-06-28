import { useCallback, useEffect, useRef, useState } from 'react'
import { Upload, X, FileText, RefreshCw, ChevronDown, UserPlus } from 'lucide-react'
import Navbar from '@/components/layout/Navbar'
import Footer from '@/components/layout/Footer'
import { AdminTable, Th, Td, Pagination } from '@/components/admin/AdminTable'
import CVParseStatusBadge from '@/components/admin/CVParseStatusBadge'
import { useToast } from '@/components/admin/Toast'
import { useAuth } from '@/context/AuthContext'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import api from '@/lib/api'

const SOURCES = ['', 'email', 'referral', 'linkedin', 'other']
const STATUSES = ['', 'new', 'shortlisted', 'promoted_pending', 'promoted', 'archived']

const STATUS_BADGE = {
  new: 'bg-blue-100 text-blue-700',
  shortlisted: 'bg-green-100 text-green-700',
  promoted_pending: 'bg-amber-100 text-amber-700',
  promoted: 'bg-emerald-100 text-emerald-800',
  archived: 'bg-gray-100 text-gray-500',
}

function StatusBadge({ status }) {
  if (!status) return null
  return (
    <span className={cn('inline-flex px-2.5 py-0.5 rounded-full text-xs font-medium capitalize', STATUS_BADGE[status] ?? 'bg-gray-100 text-gray-600')}>
      {status.replace('_', ' ')}
    </span>
  )
}

// ─── Upload panel ─────────────────────────────────────────────────────────────
function UploadPanel({ onUploaded, jobs }) {
  const dropRef = useRef(null)
  const [file, setFile] = useState(null)
  const [source, setSource] = useState('other')
  const [sourceNote, setSourceNote] = useState('')
  const [jobId, setJobId] = useState('')
  const [dragging, setDragging] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState(null)

  const handleDrop = (e) => {
    e.preventDefault()
    setDragging(false)
    const dropped = Array.from(e.dataTransfer.files).find((f) => f.type === 'application/pdf')
    if (dropped) setFile(dropped)
  }

  const handleSubmit = async () => {
    if (!file) return
    setUploading(true)
    setError(null)
    try {
      const form = new FormData()
      form.append('file', file)
      form.append('source', source)
      if (sourceNote) form.append('source_note', sourceNote)
      if (jobId) form.append('sourced_for_job_id', jobId)
      await api.post('/api/v1/talent-pool/submit', form)
      setFile(null)
      setSourceNote('')
      setJobId('')
      onUploaded()
    } catch (err) {
      setError(err.response?.data?.detail ?? 'Upload failed. Please try again.')
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="rounded-xl border border-border bg-white p-5 space-y-4">
      <h2 className="font-semibold text-text">Add to Talent Pool</h2>

      {/* Drop zone */}
      <div
        ref={dropRef}
        onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        className={cn(
          'rounded-lg border-2 border-dashed p-6 text-center transition-colors cursor-pointer',
          dragging ? 'border-brand-blue bg-brand-blue/5' : 'border-border'
        )}
        onClick={() => document.getElementById('tp-file-input').click()}
      >
        {file ? (
          <div className="flex items-center justify-center gap-2 text-sm text-text">
            <FileText size={16} className="text-brand-blue" />
            <span>{file.name}</span>
            <button type="button" onClick={(e) => { e.stopPropagation(); setFile(null) }}
              className="text-text-muted hover:text-red-500">
              <X size={14} />
            </button>
          </div>
        ) : (
          <>
            <Upload size={24} className="mx-auto mb-2 text-text-muted" />
            <p className="text-sm text-text-muted">Drop a PDF or <span className="text-brand-blue">browse</span></p>
          </>
        )}
        <input id="tp-file-input" type="file" accept="application/pdf" className="sr-only"
          onChange={(e) => { if (e.target.files[0]) setFile(e.target.files[0]) }} />
      </div>

      {/* Source */}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-xs text-text-muted mb-1 block">Source</label>
          <select value={source} onChange={(e) => setSource(e.target.value)}
            className="w-full text-sm rounded-lg border border-border px-3 py-2 focus:outline-none focus:ring-2 focus:ring-brand-blue">
            {SOURCES.filter(Boolean).map((s) => (
              <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="text-xs text-text-muted mb-1 block">Attach to job (optional)</label>
          <select value={jobId} onChange={(e) => setJobId(e.target.value)}
            className="w-full text-sm rounded-lg border border-border px-3 py-2 focus:outline-none focus:ring-2 focus:ring-brand-blue">
            <option value="">No job</option>
            {(jobs ?? []).map((j) => <option key={j.id} value={j.id}>{j.title}</option>)}
          </select>
        </div>
      </div>

      <div>
        <label className="text-xs text-text-muted mb-1 block">Source note (optional)</label>
        <input value={sourceNote} onChange={(e) => setSourceNote(e.target.value)}
          placeholder="e.g. Referred by John Doe"
          className="w-full text-sm rounded-lg border border-border px-3 py-2 focus:outline-none focus:ring-2 focus:ring-brand-blue" />
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      <Button onClick={handleSubmit} disabled={!file || uploading} className="w-full">
        {uploading ? 'Uploading…' : 'Add to Talent Pool'}
      </Button>
    </div>
  )
}

// ─── Promote modal ────────────────────────────────────────────────────────────
function PromoteModal({ profileId, onClose, onDone }) {
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)

  const handlePromote = async () => {
    setLoading(true)
    try {
      const { data } = await api.post(`/api/v1/talent-pool/${profileId}/promote`)
      setResult(data)
      if (data.status === 'invite_sent') onDone()
    } catch (err) {
      setResult({ status: 'error', message: err.response?.data?.detail ?? 'Promotion failed.' })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center" onClick={onClose}>
      <div className="absolute inset-0 bg-black/40" aria-hidden="true" />
      <div className="relative bg-white rounded-xl shadow-xl p-6 w-full max-w-sm mx-4 space-y-4"
        onClick={(e) => e.stopPropagation()}>
        <h3 className="font-semibold text-text">Promote to Candidate</h3>

        {!result ? (
          <>
            <p className="text-sm text-text-muted">
              This will send the candidate an invite email to register and claim their profile.
              The application will only be created after they confirm.
            </p>
            <div className="flex gap-2 justify-end">
              <Button variant="outline" onClick={onClose}>Cancel</Button>
              <Button onClick={handlePromote} disabled={loading}>
                {loading ? 'Sending…' : 'Send Invite'}
              </Button>
            </div>
          </>
        ) : result.status === 'invite_sent' ? (
          <>
            <p className="text-sm text-green-700 bg-green-50 rounded-lg p-3">
              Invite sent. The profile will show "Invite sent, pending confirmation" until the candidate registers.
            </p>
            <Button className="w-full" onClick={onClose}>Done</Button>
          </>
        ) : result.status === 'conflict' ? (
          <>
            <p className="text-sm text-amber-700 bg-amber-50 rounded-lg p-3">
              A user with email <strong>{result.conflict_email}</strong> already exists and is active.
              Manual review is required — do not merge automatically.
            </p>
            <Button className="w-full" variant="outline" onClick={onClose}>Close</Button>
          </>
        ) : (
          <>
            <p className="text-sm text-red-700 bg-red-50 rounded-lg p-3">{result.message}</p>
            <Button className="w-full" variant="outline" onClick={onClose}>Close</Button>
          </>
        )}
      </div>
    </div>
  )
}

// ─── Main page ────────────────────────────────────────────────────────────────
export default function TalentPoolPage() {
  const { user } = useAuth()
  const { show, ToastContainer } = useToast()

  const [profiles, setProfiles] = useState([])
  const [cursor, setCursor] = useState(null)
  const [loading, setLoading] = useState(true)
  const [statusFilter, setStatusFilter] = useState('')
  const [sourceFilter, setSourceFilter] = useState('')
  const [jobs, setJobs] = useState([])
  const [promoteId, setPromoteId] = useState(null)

  const loadProfiles = useCallback(async (reset = true) => {
    setLoading(true)
    try {
      const params = { limit: 20 }
      if (statusFilter) params.status = statusFilter
      if (sourceFilter) params.source = sourceFilter
      if (!reset && cursor) params.cursor = cursor
      const { data } = await api.get('/api/v1/talent-pool', { params })
      setProfiles((prev) => reset ? (data.items ?? []) : [...prev, ...(data.items ?? [])])
      setCursor(data.next_cursor ?? null)
    } catch {
      show('Failed to load talent pool', 'error')
    } finally {
      setLoading(false)
    }
  }, [statusFilter, sourceFilter, cursor])

  useEffect(() => { loadProfiles(true) }, [statusFilter, sourceFilter])

  useEffect(() => {
    api.get('/api/v1/jobs/mine', { params: { limit: 100 } })
      .then(({ data }) => setJobs(data.items ?? []))
      .catch(() => {})
  }, [])

  const handleStatusChange = async (profileId, newStatus) => {
    try {
      await api.patch(`/api/v1/talent-pool/${profileId}/status`, { status: newStatus })
      setProfiles((prev) => prev.map((p) => p.id === profileId ? { ...p, status: newStatus } : p))
    } catch {
      show('Failed to update status', 'error')
    }
  }

  return (
    <div className="min-h-screen flex flex-col bg-surface-muted">
      <Navbar />
      <main className="flex-1 pt-16">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-10 space-y-8">
          <ToastContainer />

          <div className="grid lg:grid-cols-3 gap-8">
            {/* Upload panel */}
            <div className="lg:col-span-1">
              <UploadPanel onUploaded={() => loadProfiles(true)} jobs={jobs} />
            </div>

            {/* List panel */}
            <div className="lg:col-span-2 space-y-4">
              <div className="flex items-center justify-between">
                <h1 className="text-xl font-bold text-text">Talent Pool</h1>
                <div className="flex gap-2">
                  <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}
                    className="text-sm rounded-lg border border-border px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-brand-blue">
                    {STATUSES.map((s) => <option key={s} value={s}>{s ? s.replace('_', ' ') : 'All statuses'}</option>)}
                  </select>
                  <select value={sourceFilter} onChange={(e) => setSourceFilter(e.target.value)}
                    className="text-sm rounded-lg border border-border px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-brand-blue">
                    {SOURCES.map((s) => <option key={s} value={s}>{s || 'All sources'}</option>)}
                  </select>
                  <button onClick={() => loadProfiles(true)} aria-label="Refresh"
                    className="p-1.5 rounded-lg border border-border text-text-muted hover:bg-white transition-colors">
                    <RefreshCw size={14} />
                  </button>
                </div>
              </div>

              <AdminTable isEmpty={!loading && profiles.length === 0} empty="No profiles in the talent pool yet.">
                <thead>
                  <tr>
                    <Th>File</Th>
                    <Th>Source</Th>
                    <Th>Status</Th>
                    <Th>Added</Th>
                    <Th>Actions</Th>
                  </tr>
                </thead>
                <tbody>
                  {profiles.map((p) => (
                    <tr key={p.id} className="hover:bg-surface-muted/50">
                      <Td className="font-medium text-text text-sm">Profile {p.id.slice(0, 8)}…</Td>
                      <Td className="text-xs capitalize text-text-muted">{p.source}</Td>
                      <Td><StatusBadge status={p.status} /></Td>
                      <Td className="text-xs text-text-muted">
                        {new Date(p.created_at).toLocaleDateString()}
                      </Td>
                      <Td>
                        <div className="flex items-center gap-3">
                          {/* Status change */}
                          {!['promoted', 'promoted_pending'].includes(p.status) && (
                            <div className="relative">
                              <select
                                value=""
                                onChange={(e) => { if (e.target.value) handleStatusChange(p.id, e.target.value) }}
                                className="appearance-none text-xs rounded border border-border bg-white pl-2 pr-6 py-1 focus:outline-none focus:ring-1 focus:ring-brand-blue cursor-pointer"
                              >
                                <option value="" disabled>Move to…</option>
                                {STATUSES.filter((s) => s && s !== p.status && !['promoted', 'promoted_pending'].includes(s)).map((s) => (
                                  <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>
                                ))}
                              </select>
                              <ChevronDown size={10} className="pointer-events-none absolute right-1.5 top-1/2 -translate-y-1/2 text-text-muted" />
                            </div>
                          )}

                          {/* Promote — admin only */}
                          {user?.role === 'ADMIN' && p.status === 'shortlisted' && (
                            <button
                              onClick={() => setPromoteId(p.id)}
                              className="flex items-center gap-1 text-xs text-brand-blue hover:underline"
                            >
                              <UserPlus size={12} /> Promote
                            </button>
                          )}

                          {/* Pending label */}
                          {p.status === 'promoted_pending' && (
                            <span className="text-xs text-amber-600">
                              Invite sent{p.last_invite_sent_at ? ` · ${new Date(p.last_invite_sent_at).toLocaleDateString()}` : ''}
                            </span>
                          )}
                        </div>
                      </Td>
                    </tr>
                  ))}
                </tbody>
              </AdminTable>

              <Pagination cursor={cursor} onLoadMore={() => loadProfiles(false)} loading={loading} />
            </div>
          </div>
        </div>
      </main>

      {promoteId && (
        <PromoteModal
          profileId={promoteId}
          onClose={() => setPromoteId(null)}
          onDone={() => { setPromoteId(null); loadProfiles(true) }}
        />
      )}

      <Footer />
    </div>
  )
}
