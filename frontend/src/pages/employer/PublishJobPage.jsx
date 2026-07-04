import { useEffect, useRef, useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { CheckCircle2, XCircle, Loader2, Upload, FileText, X, Zap } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import api from '@/lib/api'
import ehsLogo from '@/assets/ehs-logo.png'

// ─── Inline CV upload panel shown after publish ───────────────────────────────

function CVUploadPanel({ jobId }) {
  const fileInputRef = useRef(null)
  const [files, setFiles] = useState([])
  const [dragging, setDragging] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [results, setResults] = useState([])
  const [error, setError] = useState(null)

  const addFiles = (incoming) => {
    const pdfs = incoming.filter((f) => f.type === 'application/pdf')
    setFiles((prev) => [...prev, ...pdfs].slice(0, 20))
  }

  const handleDrop = (e) => {
    e.preventDefault()
    setDragging(false)
    addFiles(Array.from(e.dataTransfer.files))
  }

  const handleUpload = async () => {
    if (!files.length) return
    setUploading(true)
    setError(null)
    try {
      const form = new FormData()
      files.forEach((f) => form.append('files', f))
      form.append('source', 'other')
      form.append('sourced_for_job_id', jobId)
      const { data } = await api.post('/api/v1/talent-pool/submit-batch', form)
      setResults(data.results ?? [])
      setFiles([])
    } catch (err) {
      setError(err.response?.data?.message ?? 'Upload failed. Please try again.')
    } finally {
      setUploading(false)
    }
  }

  if (results.length > 0) {
    return (
      <div className="mt-4 rounded-xl border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-800 text-left">
        <p className="font-semibold mb-1">CVs queued for scoring</p>
        <ul className="space-y-0.5">
          {results.map((r, i) => (
            <li key={i} className="flex items-center gap-1.5">
              {r.status === 'queued'
                ? <CheckCircle2 size={12} className="text-green-600 flex-shrink-0" />
                : <XCircle size={12} className="text-red-500 flex-shrink-0" />}
              <span className="truncate">{r.filename}</span>
            </li>
          ))}
        </ul>
        <p className="text-xs text-green-700 mt-2">
          Results will appear in your talent pool once parsing completes.
        </p>
      </div>
    )
  }

  return (
    <div className="mt-4 text-left space-y-3">
      <p className="text-sm text-text-muted">
        Have external CVs to score against this job? Upload them now.
      </p>

      {/* Drop zone */}
      <div
        onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        className={cn(
          'rounded-xl border-2 border-dashed p-5 text-center cursor-pointer transition-all',
          dragging
            ? 'border-brand-blue bg-brand-blue/5'
            : 'border-border hover:border-brand-blue/50 hover:bg-surface-muted'
        )}
      >
        <Upload size={18} className="mx-auto mb-1.5 text-text-muted" />
        <p className="text-xs text-text-muted">
          {files.length > 0
            ? `${files.length} PDF${files.length > 1 ? 's' : ''} selected`
            : 'Drop PDFs here or click to browse'}
        </p>
        <input
          ref={fileInputRef}
          type="file"
          accept="application/pdf"
          multiple
          className="sr-only"
          onChange={(e) => addFiles(Array.from(e.target.files))}
        />
      </div>

      {/* File list */}
      {files.length > 0 && (
        <div className="space-y-1 max-h-32 overflow-y-auto">
          {files.map((f, i) => (
            <div key={i} className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-border bg-white text-xs">
              <FileText size={12} className="text-brand-blue flex-shrink-0" />
              <span className="flex-1 truncate">{f.name}</span>
              <button
                type="button"
                onClick={(e) => { e.stopPropagation(); setFiles((prev) => prev.filter((_, j) => j !== i)) }}
                className="text-text-muted hover:text-red-500 transition-colors"
              >
                <X size={11} />
              </button>
            </div>
          ))}
        </div>
      )}

      {error && (
        <p className="text-xs text-red-600">{error}</p>
      )}

      <div className="flex gap-2">
        <Button
          onClick={handleUpload}
          disabled={!files.length || uploading}
          size="sm"
          className="flex items-center gap-1.5"
        >
          {uploading
            ? <><Loader2 size={13} className="animate-spin" /> Uploading…</>
            : <><Zap size={13} /> Score CVs</>}
        </Button>
      </div>
    </div>
  )
}

// ─── Main page ────────────────────────────────────────────────────────────────

export default function PublishJobPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [status, setStatus] = useState('loading') // loading | success | error
  const [errorMsg, setErrorMsg] = useState(null)
  const [jobTitle, setJobTitle] = useState(null)
  const [showCVUpload, setShowCVUpload] = useState(false)

  useEffect(() => {
    let cancelled = false

    const publish = async () => {
      try {
        const { data } = await api.post(`/api/v1/jobs/${id}/publish`)
        if (cancelled) return
        setJobTitle(data.title)
        setStatus('success')
      } catch (err) {
        if (cancelled) return
        const body = err.response?.data
        const msg = body?.message ?? body?.detail ?? ''
        // Already active means employer clicked the link again — treat as success
        if (typeof msg === 'string' && msg.toLowerCase().includes('active')) {
          setStatus('success')
        } else {
          setErrorMsg(typeof msg === 'string' ? msg : 'Something went wrong. Please try again.')
          setStatus('error')
        }
      }
    }

    publish()
    return () => { cancelled = true }
  }, [id])

  return (
    <div className="min-h-screen bg-surface-muted flex flex-col items-center justify-center px-4 py-12">
      <div className="w-full max-w-md">
        <div className="mb-8 flex justify-center">
          <img src={ehsLogo} alt="Elevare" className="h-9 w-auto" />
        </div>

        <div className="bg-white rounded-2xl border border-border p-8 shadow-sm text-center space-y-4">
          {status === 'loading' && (
            <>
              <Loader2 size={40} className="mx-auto text-brand-blue animate-spin" />
              <p className="text-text font-medium">Publishing your job…</p>
            </>
          )}

          {status === 'success' && (
            <>
              <CheckCircle2 size={40} className="mx-auto text-green-500" />
              <h1 className="text-xl font-bold text-text">Job published!</h1>
              {jobTitle && (
                <p className="text-sm text-text-muted">
                  <strong>{jobTitle}</strong> is now live and accepting applications.
                </p>
              )}

              {/* CV upload prompt */}
              {!showCVUpload ? (
                <div className="rounded-xl border border-brand-blue/20 bg-brand-blue/5 px-4 py-3 text-left space-y-2">
                  <p className="text-sm font-medium text-text">
                    Have external CVs to score against this job?
                  </p>
                  <p className="text-xs text-text-muted">
                    Upload CVs you've received outside of Elevare — they'll be parsed and ranked against this listing.
                  </p>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => setShowCVUpload(true)}
                    className="flex items-center gap-1.5"
                  >
                    <Upload size={13} /> Upload CVs
                  </Button>
                </div>
              ) : (
                <CVUploadPanel jobId={id} />
              )}

              <div className="flex flex-col gap-2 pt-2 border-t border-border">
                <Button onClick={() => navigate('/employer/jobs')} className="w-full">
                  View my jobs
                </Button>
                <Link to={`/jobs/${id}`} className="text-sm text-brand-blue hover:underline">
                  See public listing →
                </Link>
              </div>
            </>
          )}

          {status === 'error' && (
            <>
              <XCircle size={40} className="mx-auto text-red-500" />
              <h1 className="text-xl font-bold text-text">Couldn't publish</h1>
              <p className="text-sm text-text-muted">{errorMsg}</p>
              <div className="flex flex-col gap-2 pt-2">
                <Button onClick={() => navigate(`/employer/jobs/${id}/edit`)} className="w-full">
                  Edit job
                </Button>
                <Button variant="outline" onClick={() => navigate('/employer/jobs')} className="w-full">
                  Back to jobs
                </Button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
