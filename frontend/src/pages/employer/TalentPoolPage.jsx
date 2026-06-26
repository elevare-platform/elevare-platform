import { useCallback, useEffect, useRef, useState } from 'react'
import { Upload, X, FileText, RefreshCw, Users } from 'lucide-react'
import Navbar from '@/components/layout/Navbar'
import Footer from '@/components/layout/Footer'
import { AdminTable, Th, Td, Pagination } from '@/components/admin/AdminTable'
import { useToast } from '@/components/admin/Toast'
import { cn } from '@/lib/utils'
import api from '@/lib/api'

// ─── Enums ────────────────────────────────────────────────────────────────────

const STATUS_BADGE = {
  new:               'bg-blue-100 text-blue-700',
  shortlisted:       'bg-green-100 text-green-700',
  promoted_pending:  'bg-amber-100 text-amber-700',
  promoted:          'bg-emerald-100 text-emerald-800',
  archived:          'bg-gray-100 text-gray-500',
}

const STATUS_LABEL = {
  new:               'New',
  shortlisted:       'Shortlisted',
  promoted_pending:  'Invite sent',
  promoted:          'Promoted',
  archived:          'Archived',
}

const SOURCE_OPTIONS = ['', 'email', 'referral', 'linkedin', 'other']
const STATUS_OPTIONS = ['', 'new', 'shortlisted', 'promoted_pending', 'promoted', 'archived']

function StatusBadge({ status }) {
  return (
    <span className={cn(
      'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium',
      STATUS_BADGE[status] ?? 'bg-gray-100 text-gray-600'
    )}>
      {STATUS_LABEL[status] ?? status}
    </span>
  )
}

// ─── Upload panel ─────────────────────────────────────────────────────────────

function UploadPanel({ onUploaded }) {
  const dropRef = useRef(null)
  const [dragging, setDragging] = useState(false)
  const [file, setFile] = useState(null)
  const [source, setSource] = useState('other')
  const [sourceNote, setSourceNote] = useState('')
  const [uploading, setUploading] = useState(false)

  const handleDrop = (e) => {
    e.preventDefault()
    setDragging(false)
    const f = Array.from(e.dataTransfer.files).find((f) => f.type === 'application/pdf')
    if (f) setFile(f)
  }

  const handleUpload = async () => {
    if (!file) return
    setUploading(true)
    try {
      const form = new FormData()
      form.append('file', file)
      form.append('source', source)
      if (sourceNote) form.append('source_note', sourceNote)

      await api.post('/api/v1/talent-pool/submit', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      setFile(null)
      setSourceNote('')
      onUploaded()
    } catch {
      // parent handles error feedback
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
          'rounded-xl border-2 border-dashed p-6 text-center transition-colors',
          dragging ? 'border-brand-blue bg-brand-blue/5' : 'border-border'
        )}
      >
        {file ? (
          <div className="flex items-center justify-center gap-2 text-sm text-text">
            <FileText size={16} className="text-brand-blue" />
            <span>{file.name}</span>
            <button type="button" onClick={() => setFile(null)} aria-label="Remove file"
              className="text-text-muted hover:text-red-500">
              <X size={14} />
            </button>
          </div>
        ) : (
          <>
            <Upload size={28} className="mx-auto mb-2 text-text-muted" />
            <p className="text-sm text-text-muted mb-2">
              Drag a PDF here, or{' '}
              <label className="text-brand-blue cursor-pointer hover:underline">
                browse
                <input type="file" accept="application/pdf" className="sr-only"
                  onChange={(e) => setFile(e.target.files[0])} />
              </label>
            </p>
          </>
        )}
      </div>

      {/* Source */}
      <div className="grid sm:grid-cols-2 gap-3">
        <div>
          <label className="text-xs font-medium text-text-muted block mb-1">Source</label>
          <select
            value={source}
            onChange={(e) => setSource(e.target.value)}
            className="w-full rounded-lg border border-border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-blue"
          >
            {SOURCE_OPTIONS.filter(Boolean).map((s) => (
              <option key={s} value={s} className="capitalize">{s}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="text-xs font-medium text-text-muted block mb-1">Source note (optional)</label>
          <input
            type="text"
            value={sourceNote}
            onChange={(e) => setSourceNote(e.target.value)}
            placeholder="e.g. referred by John"
            className="w-full rounded-lg border border-border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-blue"
          />
        </div>
      </div>

      <button
        type="button"
        onClick={handleUpload}
        disabled={!file || uploading}
        className="w-full rounded-lg bg-brand-blue text-white py-2.5 text-sm font-medium hover:bg-brand-blue/90 disabled:opacity-50 transition-colors"
      >
        {uploading ? 'Uploading…' : 'Add to Talent Pool'}
      </button>
    </div>
  )
}

// ─── Promote confirm modal ────────────────────────────────────────────────────

function PromoteModal({ profile, onClose, onPromoted }) {
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)

  const handlePromote = async () => {
    setLoading(true)
    try {
      const { data } = await api.post(`/api/v1/talent-pool/${profile.id}/promote`)
      setResult(data)
      if (data.status === 'invite_sent') onPromoted()
    } catch {
      setResult({ status: 'error', message: 'Promotion failed. Please try again.' })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="absolute inset-0 bg-black/40" aria-hidden="true" />
      <div
        className="relative w-full max-w-sm bg-white rounded-2xl shadow-2xl p-6 space-y-4"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
      >
        <div className="flex items-center justify-between">
          <h2 className="font-semibold text-text">Promote to Candidate</h2>
          <button type="button" onClick={onClose} aria-label="Close" className="text-text-muted hover:text-text">
            <X size={18} />
          </button>
        </div>

        {!result ? (
          <>
            <p className="text-sm text-text-muted">
              This will send an invite email to the candidate. Their account will be created
              only after they accept and confirm. The application is not created until then.
            </p>
            <div className="flex gap-3 pt-1">
              <button type="button" onClick={onClose}
                className="flex-1 rounded-lg border border-border py-2 text-sm text-text-muted hover:bg-surface-muted transition-colors">
                Cancel
              </button>
              <button type="button" onClick={handlePromote} disabled={loading}
                className="flex-1 rounded-lg bg-brand-blue text-white py-2 text-sm font-medium hover:bg-brand-blue/90 disabled:opacity-50 transition-colors">
                {loading ? 'Sending…' : 'Send invite'}
              </button>
            </div>
          </>
        ) : result.status === 'invite_sent' ? (
          <div className="text-center py-2 space-y-2">
            <p className="text-2xl">✉️</p>
            <p className="font-medium text-text">Invite sent</p>
            <p className="text-xs text-text-muted">
              The candidate will appear as "Invite sent" until they confirm.
            </p>
            <button type="button" onClick={onClose}
              className="mt-3 px-5 py-2 rounded-lg bg-brand-blue text-white text-sm">
              Done
            </button>
          </div>
        ) : result.status === 'conflict' ? (
          <div className="rounded-lg bg-amber-50 border border-amber-200 p-3 space-y-1">
            <p className="text-sm font-medium text-amber-800">Active account found</p>
            <p className="text-xs text-amber-700">
              A user with <strong>{result.conflict_email}</strong> already exists and is active.
              Manual review required — do not create a duplicate account.
            </p>
            <button type="button" onClick={onClose}
              className="mt-2 text-xs text-amber-700 underline">Close</button>
          </div>
        ) : (
          <p className="text-sm text-red-600">{result.message}</p>
        )}
      </div>
    </div>
  )
}

// ─── TalentPoolPage ───────────────────────────────────────────────────────────

export default function TalentPoolPage() {
  const { show, ToastContainer } = useToast()
  const [profiles, setProfiles] = useState([])
  const [loading, setLoading] = useState(true)
  const [cursor, setCursor] = useState(null)
  const [statusFilter, setStatusFilter] = useState('')
  const [sourceFilter, setSourceFilter] = useState('')
  const [promoting, setPromoting] = useState(null) // profile being promoted

  const load = useCallback(async (reset = true) => {
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
  }, [statusFilter, sourceFilter, cursor, show])

  useEffect(() => { load(true) }, [statusFilter, sourceFilter])

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
      <ToastContainer />

      <main className="flex-1 pt-16">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 py-10 space-y-8">
          <div className="flex items-center gap-3">
            <Users size={22} className="text-brand-blue" />
            <div>
              <h1 className="text-2xl font-bold text-text">Talent Pool</h1>
              <p className="text-sm text-text-muted">Sourced candidates not yet in the system.</p>
            </div>
          </div>

          <UploadPanel onUploaded={() => { load(true); show('CV added to talent pool') }} />

          {/* Filters */}
          <div className="flex flex-wrap items-center gap-3">
            <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}
              className="text-sm rounded-lg border border-border px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-brand-blue"
              aria-label="Filter by status">
              {STATUS_OPTIONS.map((s) => (
                <option key={s} value={s}>{s ? STATUS_LABEL[s] ?? s : 'All statuses'}</option>
              ))}
            </select>

            <select value={sourceFilter} onChange={(e) => setSourceFilter(e.target.value)}
              className="text-sm rounded-lg border border-border px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-brand-blue"
              aria-label="Filter by source">
              {SOURCE_OPTIONS.map((s) => (
                <option key={s} value={s} className="capitalize">{s || 'All sources'}</option>
              ))}
            </select>

            <button onClick={() => load(true)} aria-label="Refresh"
              className="p-1.5 rounded-lg border border-border text-text-muted hover:bg-surface-muted transition-colors">
              <RefreshCw size={14} />
            </button>
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
                  <Td className="font-medium text-text text-sm">{p.parsed_submission_id}</Td>
                  <Td className="capitalize text-sm text-text-muted">{p.source}</Td>
                  <Td><StatusBadge status={p.status} /></Td>
                  <Td className="text-xs text-text-muted">
                    {new Date(p.created_at).toLocaleDateString()}
                  </Td>
                  <Td>
                    <div className="flex items-center gap-3">
                      {/* Status update — only for new/shortlisted/archived */}
                      {['new', 'shortlisted', 'archived'].includes(p.status) && (
                        <select
                          value={p.status}
                          onChange={(e) => handleStatusChange(p.id, e.target.value)}
                          className="text-xs rounded-md border border-border px-2 py-1 focus:outline-none"
                          aria-label="Update status"
                        >
                          {['new', 'shortlisted', 'archived'].map((s) => (
                            <option key={s} value={s}>{STATUS_LABEL[s]}</option>
                          ))}
                        </select>
                      )}

                      {/* Promote — only admin can do this, and only for new/shortlisted */}
                      {['new', 'shortlisted'].includes(p.status) && (
                        <button
                          type="button"
                          onClick={() => setPromoting(p)}
                          className="text-xs text-brand-blue hover:underline"
                        >
                          Promote
                        </button>
                      )}

                      {p.status === 'promoted_pending' && (
                        <span className="text-xs text-amber-600">Invite sent, pending confirmation</span>
                      )}
                    </div>
                  </Td>
                </tr>
              ))}
            </tbody>
          </AdminTable>

          <Pagination cursor={cursor} onLoadMore={() => load(false)} loading={loading} />
        </div>
      </main>

      <Footer />

      {promoting && (
        <PromoteModal
          profile={promoting}
          onClose={() => setPromoting(null)}
          onPromoted={() => { setPromoting(null); load(true) }}
        />
      )}
    </div>
  )
}
