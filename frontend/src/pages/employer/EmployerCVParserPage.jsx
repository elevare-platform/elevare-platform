import { useCallback, useEffect, useRef, useState } from 'react'
import { Upload, X, FileText, RefreshCw, ExternalLink, Download } from 'lucide-react'
import Navbar from '@/components/layout/Navbar'
import Footer from '@/components/layout/Footer'
import { AdminTable, Th, Td, Pagination } from '@/components/admin/AdminTable'
import CVParseStatusBadge from '@/components/admin/CVParseStatusBadge'
import { useToast } from '@/components/admin/Toast'
import { useCVParser } from '@/hooks/useCVParser'
import { useAuth } from '@/context/AuthContext'

const TERMINAL = ['completed', 'failed', 'flagged']
const STATUSES = ['', 'pending', 'processing', 'completed', 'flagged', 'failed']

// ─── File card shown in the upload zone ───────────────────────────────────────
function FileCard({ file, submission, onRemove, onPoll }) {
  const status = submission?.parse_status ?? 'pending'

  useEffect(() => {
    if (!submission || TERMINAL.includes(status)) return
    const timer = setInterval(() => onPoll(submission.id), 3000)
    return () => clearInterval(timer)
  }, [submission, status, onPoll])

  return (
    <div className="flex items-center justify-between p-3 rounded-lg border border-border bg-white text-sm">
      <div className="flex items-center gap-2 min-w-0">
        <FileText size={16} className="shrink-0 text-text-muted" />
        <span className="truncate text-text">{file.name}</span>
        <span className="text-text-muted shrink-0">
          ({(file.size / 1024).toFixed(0)} KB)
        </span>
      </div>
      <div className="flex items-center gap-2 shrink-0">
        <CVParseStatusBadge status={status} />
        {!submission && (
          <button onClick={() => onRemove(file)} aria-label="Remove file"
            className="text-text-muted hover:text-red-500 transition-colors">
            <X size={14} />
          </button>
        )}
      </div>
    </div>
  )
}

// ─── Result detail panel ──────────────────────────────────────────────────────
function ResultPanel({ submission, onDownload, onDiscard, downloading }) {
  if (!submission) return null
  const data = submission.parsed_data ?? {}
  const isFailed = submission.parse_status === 'failed'
  const isFlagged = submission.parse_status === 'flagged'
  const hasFile = !!submission.r2_key

  return (
    <div className="rounded-xl border border-border bg-white p-5 space-y-4">
      {submission.flag_reasons?.length > 0 && (
        <div className="rounded-lg bg-amber-50 border border-amber-200 p-3 text-sm text-amber-800">
          <strong>Flagged for review:</strong>{' '}
          {submission.flag_reasons.join(', ')}
        </div>
      )}
      {isFailed && (
        <div className="rounded-lg bg-red-50 border border-red-200 p-3 text-sm text-red-700">
          Parsing failed. Please review the CV manually.
        </div>
      )}

      <div className="grid grid-cols-2 gap-4 text-sm">
        <Field label="Name" value={data.full_name} />
        <Field label="Email" value={data.email} />
        <Field label="Phone" value={data.phone} />
        <Field label="Location" value={data.location} />
        <Field label="Current Title" value={data.current_title} />
        <Field label="Seniority" value={data.seniority_level} />
        <Field label="Years Experience" value={data.years_experience} />
        <Field label="Language" value={data.detected_language} />
      </div>

      {data.skills?.length > 0 && (
        <div>
          <p className="text-xs font-medium text-text-muted uppercase tracking-wide mb-2">Skills</p>
          <div className="flex flex-wrap gap-1.5">
            {data.skills.map((s) => (
              <span key={s} className="px-2 py-0.5 rounded-full bg-brand-blue/10 text-brand-blue text-xs">
                {s}
              </span>
            ))}
          </div>
        </div>
      )}

      {data.summary && (
        <div>
          <p className="text-xs font-medium text-text-muted uppercase tracking-wide mb-1">Summary</p>
          <p className="text-sm text-text">{data.summary}</p>
        </div>
      )}

      <div className="flex gap-2 pt-2">
        {hasFile && (
          <button
            onClick={() => onDownload(submission.id)}
            disabled={downloading}
            className="flex items-center gap-1.5 px-4 py-2 text-sm rounded-lg border border-border text-text hover:bg-surface-muted disabled:opacity-40 transition-colors"
          >
            <Download size={14} />
            {downloading ? 'Preparing…' : 'Download CV'}
          </button>
        )}
        <button
          onClick={() => onDiscard(submission.id)}
          className="px-4 py-2 text-sm rounded-lg border border-border text-text-muted hover:bg-surface-muted transition-colors"
        >
          Close
        </button>
      </div>
    </div>
  )
}

function Field({ label, value }) {
  return (
    <div>
      <p className="text-xs text-text-muted">{label}</p>
      <p className="font-medium text-text">{value ?? '—'}</p>
    </div>
  )
}

// ─── Main page ────────────────────────────────────────────────────────────────
// ─── Exported Inner Component ────────────────────────────────────────────────
export function EmployerCVParser() {
  const { user } = useAuth()
  const { submitBatch, listSubmissions, pollSubmission, downloadCV, loading } = useCVParser()
  const { show, ToastContainer } = useToast()
  const dropRef = useRef(null)

  const [files, setFiles] = useState([])
  const [submissions, setSubmissions] = useState([])
  const [fileMap, setFileMap] = useState({})
  const [selected, setSelected] = useState(null)
  const [cursor, setCursor] = useState(null)
  const [statusFilter, setStatusFilter] = useState('')
  const [uploading, setUploading] = useState(false)
  const [dragging, setDragging] = useState(false)
  const [downloading, setDownloading] = useState(false)

  const loadSubmissions = useCallback(async (reset = true) => {
    try {
      const params = { limit: 20 }
      if (statusFilter) params.status = statusFilter
      if (!reset && cursor) params.cursor = cursor
      const data = await listSubmissions(params)
      setSubmissions((prev) => reset ? (data.items ?? []) : [...prev, ...(data.items ?? [])])
      setCursor(data.next_cursor ?? null)
    } catch { /* handled in hook */ }
  }, [statusFilter, cursor, listSubmissions])

  useEffect(() => { loadSubmissions(true) }, [statusFilter])

  const handleDrop = (e) => {
    e.preventDefault()
    setDragging(false)
    const dropped = Array.from(e.dataTransfer.files).filter((f) => f.type === 'application/pdf')
    addFiles(dropped)
  }

  const addFiles = (newFiles) => {
    const combined = [...files, ...newFiles].slice(0, 20)
    setFiles(combined)
  }

  const removeFile = (file) => setFiles((prev) => prev.filter((f) => f !== file))

  const handleUpload = async () => {
    if (!files.length) return
    setUploading(true)
    try {
      const results = await submitBatch(files)
      const map = {}
      results.forEach((sub, i) => { if (files[i]) map[files[i].name] = sub })
      setFileMap(map)
      setFiles([])
      await loadSubmissions(true)
      show(`${results.length} CV${results.length > 1 ? 's' : ''} submitted for parsing`)
    } catch {
      show('Upload failed', 'error')
    } finally {
      setUploading(false)
    }
  }

  const handlePoll = useCallback(async (id) => {
    try {
      const updated = await pollSubmission(id)
      setFileMap((prev) => {
        const key = Object.keys(prev).find((k) => prev[k]?.id === id)
        if (!key) return prev
        return { ...prev, [key]: updated }
      })
      setSubmissions((prev) => prev.map((s) => s.id === id ? updated : s))
      if (selected?.id === id) setSelected(updated)
    } catch { /* silent */ }
  }, [selected])

  const handleDiscard = () => setSelected(null)

  const handleDownload = async (id) => {
    setDownloading(true)
    try {
      const url = await downloadCV(id)
      window.open(url, '_blank', 'noopener,noreferrer')
    } catch {
      show('Failed to generate download link', 'error')
    } finally {
      setDownloading(false)
    }
  }

  return (
    <div className="space-y-6">
      <ToastContainer />
      <div>
        <h1 className="text-2xl font-bold text-text">CV Parser</h1>
        <p className="text-sm text-text-muted mt-1">Upload CVs to extract candidate data automatically.</p>
      </div>

      {/* Upload zone */}
      <div
        ref={dropRef}
        onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        className={`rounded-xl border-2 border-dashed p-8 text-center transition-colors ${
          dragging ? 'border-brand-blue bg-brand-blue/5' : 'border-border bg-white'
        }`}
      >
        <Upload size={32} className="mx-auto mb-3 text-text-muted" />
        <p className="text-sm text-text-muted mb-3">
          Drag and drop PDFs here, or{' '}
          <label className="text-brand-blue cursor-pointer hover:underline">
            browse
            <input
              type="file"
              accept="application/pdf"
              multiple
              className="sr-only"
              onChange={(e) => addFiles(Array.from(e.target.files))}
            />
          </label>
        </p>
        <p className="text-xs text-text-muted">PDF only · Max 20 files per batch</p>
      </div>

      {/* Staged files */}
      {files.length > 0 && (
        <div className="space-y-2">
          {files.map((f) => (
            <FileCard
              key={f.name}
              file={f}
              submission={fileMap[f.name]}
              onRemove={removeFile}
              onPoll={handlePoll}
            />
          ))}
          <button
            onClick={handleUpload}
            disabled={uploading}
            className="mt-2 px-5 py-2 rounded-lg bg-brand-blue text-white text-sm hover:bg-brand-blue/90 disabled:opacity-50 transition-colors"
          >
            {uploading ? 'Uploading…' : `Upload ${files.length} CV${files.length > 1 ? 's' : ''}`}
          </button>
        </div>
      )}

      {/* Result panel */}
      {selected && (
        <div>
          <div className="flex items-center justify-between mb-2">
            <h2 className="font-semibold text-text">{selected.filename}</h2>
            <button onClick={() => setSelected(null)} className="text-text-muted hover:text-text">
              <X size={16} />
            </button>
          </div>
          <ResultPanel
            submission={selected}
            onDownload={handleDownload}
            onDiscard={handleDiscard}
            downloading={downloading}
          />
        </div>
      )}

      {/* Submissions list */}
      <div className="flex items-center justify-between mb-3">
        <h2 className="font-semibold text-text">Submissions</h2>
        <div className="flex items-center gap-2">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="text-sm rounded-lg border border-border px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-brand-blue"
            aria-label="Filter by status"
          >
            {STATUSES.map((s) => <option key={s} value={s}>{s || 'All statuses'}</option>)}
          </select>
          <button onClick={() => loadSubmissions(true)} aria-label="Refresh"
            className="p-1.5 rounded-lg border border-border text-text-muted hover:bg-surface-muted transition-colors">
            <RefreshCw size={14} />
          </button>
        </div>
      </div>

      <AdminTable isEmpty={!loading && submissions.length === 0} empty="No submissions yet.">
        <thead>
          <tr>
            <Th>Filename</Th>
            <Th>Status</Th>
            <Th>Date</Th>
            <Th>Actions</Th>
          </tr>
        </thead>
        <tbody>
          {submissions.map((s) => (
            <tr key={s.id} className="hover:bg-surface-muted/50 cursor-pointer"
              onClick={() => setSelected(s)}>
              <Td className="font-medium text-text">{s.filename}</Td>
              <Td><CVParseStatusBadge status={s.parse_status} /></Td>
              <Td className="text-text-muted text-xs">
                {new Date(s.created_at).toLocaleDateString()}
              </Td>
              <Td>
                <div className="flex items-center gap-3">
                  <button
                    onClick={(e) => { e.stopPropagation(); setSelected(s) }}
                    className="text-xs text-brand-blue hover:underline flex items-center gap-1"
                  >
                    View <ExternalLink size={10} />
                  </button>
                  <button
                    onClick={(e) => { e.stopPropagation(); handleDownload(s.id) }}
                    disabled={downloading}
                    className="text-xs text-text-muted hover:text-brand-blue flex items-center gap-1 disabled:opacity-40"
                  >
                    <Download size={10} /> Download
                  </button>
                </div>
              </Td>
            </tr>
          ))}
        </tbody>
      </AdminTable>

      <Pagination cursor={cursor} onLoadMore={() => loadSubmissions(false)} loading={loading} />
    </div>
  )
}

// Default export acts as the page wrapper for the direct route
export default function EmployerCVParserPage() {
  return (
    <div className="min-h-screen flex flex-col bg-surface-muted">
      <Navbar />
      <main className="flex-1 pt-16">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 py-10">
          <EmployerCVParser />
        </div>
      </main>
      <Footer />
    </div>
  )
}
