import { useState, useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import { Link } from 'react-router-dom'
import { X, UploadCloud, FileText, ChevronDown } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { validateCvFile } from '@/lib/uploadValidation'
import api from '@/lib/api'

/**
 * ApplyModal — lets a candidate apply to a job.
 * Rendered via React Portal so it sits outside any parent <Link> or card
 * element, preventing accidental navigation when interacting with the modal.
 *
 * Props:
 *   jobId      — string, the job being applied to
 *   onClose    — () => void
 *   onSuccess  — () => void, called after a successful application
 */
export default function ApplyModal({ jobId, onClose, onSuccess }) {
  const [cvs, setCvs] = useState([])
  const [cvsLoading, setCvsLoading] = useState(true)
  const [selectedCvId, setSelectedCvId] = useState('')
  const [coverLetter, setCoverLetter] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)

  // Upload panel state
  const [uploadOpen, setUploadOpen] = useState(false)
  const [uploadFile, setUploadFile] = useState(null)
  const [uploadError, setUploadError] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [saveAsDefault, setSaveAsDefault] = useState(false)
  const fileInputRef = useRef(null)

  // Fetch candidate CVs on open
  useEffect(() => {
    let cancelled = false
    const fetchCvs = async () => {
      setCvsLoading(true)
      try {
        const { data } = await api.get('/api/v1/candidates/me/cvs')
        if (cancelled) return
        setCvs(data)
        const defaultCv = data.find((cv) => cv.is_default)
        setSelectedCvId(defaultCv?.id ?? data[0]?.id ?? '')
        // Auto-open upload panel if no CVs exist
        if (data.length === 0) setUploadOpen(true)
      } catch {
        if (!cancelled) setError('Failed to load your CVs. Please try again.')
      } finally {
        if (!cancelled) setCvsLoading(false)
      }
    }
    fetchCvs()
    return () => { cancelled = true }
  }, [])

  // Close on Escape
  useEffect(() => {
    const handler = (e) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [onClose])

  // ── Inline CV upload ────────────────────────────────────────────────────

  const handleFileChange = (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    const err = validateCvFile(file)
    if (err) { setUploadError(err); return }
    setUploadError(null)
    setUploadFile(file)
  }

  const clearUpload = () => {
    setUploadFile(null)
    setUploadError(null)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  const handleUploadCv = async () => {
    if (!uploadFile) return
    setUploading(true)
    setUploadError(null)
    try {
      const formData = new FormData()
      formData.append('file', uploadFile)
      const { data: newCv } = await api.post('/api/v1/candidates/me/cv', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })

      // Optionally set as default
      if (saveAsDefault) {
        await api.put(`/api/v1/candidates/me/cv/${newCv.id}/default`)
        // Mark all others as non-default in local state
        setCvs((prev) => [
          ...prev.map((cv) => ({ ...cv, is_default: false })),
          { ...newCv, is_default: true },
        ])
      } else {
        setCvs((prev) => [...prev, newCv])
      }

      setSelectedCvId(newCv.id)
      clearUpload()
      setUploadOpen(false)
    } catch (err) {
      const msg = err.response?.data?.detail ?? 'Upload failed. Please try again.'
      setUploadError(typeof msg === 'string' ? msg : 'Upload failed. Please try again.')
    } finally {
      setUploading(false)
    }
  }

  // ── Application submit ──────────────────────────────────────────────────

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      await api.post('/api/v1/applications', {
        job_id: jobId,
        cv_id: selectedCvId || null,
        cover_letter: coverLetter.trim() || null,
      })
      onSuccess()
    } catch (err) {
      const status = err.response?.status
      const detail = err.response?.data?.detail

      if (status === 409) {
        setError({ message: 'You have already applied for this job.' })
      } else if (status === 403 && err.response?.data?.code === 'PROFILE_INCOMPLETE') {
        setError({ message: typeof detail === 'string' ? detail : 'Your profile is incomplete.', profileLink: true })
      } else {
        const msg = typeof detail === 'string' ? detail : 'Something went wrong. Please try again.'
        setError({ message: msg })
      }
    } finally {
      setSubmitting(false)
    }
  }

  const noCvs = !cvsLoading && cvs.length === 0

  const modal = (
    <div
      className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/50 px-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="apply-modal-title"
      onClick={(e) => e.stopPropagation()}
      onMouseDown={(e) => e.stopPropagation()}
    >
      <div className="relative w-full max-w-lg rounded-xl border border-border bg-surface shadow-lg max-h-[90vh] overflow-y-auto">

        {/* Header */}
        <div className="flex items-center justify-between border-b border-border px-6 py-4 sticky top-0 bg-surface z-10">
          <h2 id="apply-modal-title" className="text-base font-semibold text-text">
            Apply for this job
          </h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close modal"
            className="rounded-md p-1 text-text-muted hover:text-text hover:bg-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-blue"
          >
            <X size={18} />
          </button>
        </div>

        {/* Body */}
        <form onSubmit={handleSubmit} className="px-6 py-5 space-y-5">

          {/* ── CV selector ── */}
          <div className="space-y-2">
            <label className="block text-sm font-medium text-text">CV / Resume</label>

            {cvsLoading ? (
              <div className="h-10 animate-pulse rounded-md bg-gray-200" />
            ) : cvs.length > 0 ? (
              <select
                id="cv-select"
                value={selectedCvId}
                onChange={(e) => setSelectedCvId(e.target.value)}
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-text focus:outline-none focus:ring-2 focus:ring-brand-blue"
              >
                {cvs.map((cv) => (
                  <option key={cv.id} value={cv.id}>
                    {cv.filename}{cv.is_default ? ' (Default)' : ''}
                  </option>
                ))}
              </select>
            ) : (
              <p className="text-sm text-text-muted">
                No CVs on file. Upload one below to continue.
              </p>
            )}

            {/* Upload toggle — always available */}
            {!noCvs && (
              <button
                type="button"
                onClick={() => { setUploadOpen((v) => !v); clearUpload() }}
                className="flex items-center gap-1.5 text-xs text-brand-blue hover:underline focus-visible:outline-none mt-1"
              >
                <UploadCloud size={13} />
                Upload a different CV
                <ChevronDown
                  size={12}
                  className={`transition-transform duration-200 ${uploadOpen ? 'rotate-180' : ''}`}
                />
              </button>
            )}
          </div>

          {/* ── Upload panel ── */}
          {uploadOpen && (
            <div className="rounded-lg border border-dashed border-border bg-background p-4 space-y-3">
              {/* File picker */}
              {!uploadFile ? (
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  className="flex items-center gap-2 text-sm text-brand-blue hover:underline focus-visible:outline-none"
                >
                  <UploadCloud size={15} />
                  Choose a PDF file (max 5MB)
                </button>
              ) : (
                <div className="flex items-center justify-between gap-3 rounded-md border border-border bg-surface px-3 py-2">
                  <div className="flex items-center gap-2 min-w-0">
                    <FileText size={14} className="text-brand-blue flex-shrink-0" />
                    <span className="text-sm text-text truncate">{uploadFile.name}</span>
                  </div>
                  <button
                    type="button"
                    onClick={clearUpload}
                    className="text-text-muted hover:text-red-600 transition-colors flex-shrink-0"
                    aria-label="Remove file"
                  >
                    <X size={14} />
                  </button>
                </div>
              )}

              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf"
                className="sr-only"
                aria-hidden="true"
                onChange={handleFileChange}
              />

              {uploadError && (
                <p className="text-xs text-red-600" role="alert">{uploadError}</p>
              )}

              {/* Save as default checkbox */}
              {uploadFile && (
                <label className="flex items-center gap-2 cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={saveAsDefault}
                    onChange={(e) => setSaveAsDefault(e.target.checked)}
                    className="rounded border-border text-brand-blue focus:ring-brand-blue"
                  />
                  <span className="text-sm text-text">Save as my default CV</span>
                </label>
              )}

              {uploadFile && (
                <Button
                  type="button"
                  size="sm"
                  onClick={handleUploadCv}
                  disabled={uploading}
                  className="w-full"
                >
                  {uploading ? 'Uploading…' : 'Upload & Use This CV'}
                </Button>
              )}
            </div>
          )}

          {/* ── Cover letter ── */}
          <div className="space-y-1.5">
            <label htmlFor="cover-letter" className="block text-sm font-medium text-text">
              Cover Letter <span className="text-text-muted font-normal">(optional)</span>
            </label>
            <textarea
              id="cover-letter"
              rows={4}
              value={coverLetter}
              onChange={(e) => setCoverLetter(e.target.value)}
              placeholder="Write a brief cover letter (optional)"
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-text placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-brand-blue resize-none"
            />
          </div>

          {error && (
            <div className="rounded-md bg-red-50 border border-red-200 px-4 py-3 space-y-2" role="alert">
              <p className="text-sm text-red-700">{error.message}</p>
              {error.profileLink && (
                <Link
                  to={`/candidate/profile?next=${encodeURIComponent(`/jobs/${jobId}`)}`}
                  onClick={onClose}
                  className="inline-block text-sm font-medium text-brand-blue hover:underline"
                >
                  Complete your profile →
                </Link>
              )}
            </div>
          )}

          <div className="flex justify-end gap-3 pt-1">
            <Button type="button" variant="outline" onClick={onClose} disabled={submitting}>
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={submitting || cvsLoading || noCvs}
              className="min-w-[140px]"
            >
              {submitting ? 'Submitting…' : 'Submit Application'}
            </Button>
          </div>
        </form>
      </div>
    </div>
  )

  return createPortal(modal, document.body)
}
