import { useRef, useState } from 'react'
import { UploadCloud, FileText, X } from 'lucide-react'
import { validateCvFile } from '@/lib/uploadValidation'
import api from '@/lib/api'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { trackEvent } from '@/lib/analytics'

/**
 * Formats bytes into a human-readable string (e.g. "1.2 MB").
 */
function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1_048_576) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1_048_576).toFixed(1)} MB`
}

/**
 * CvUpload — drag-and-drop CV upload component.
 *
 * Props:
 *   onUploadSuccess — (newCv: CandidateCvsResponse) => void   called after 201
 *
 * Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6
 */
export function CvUpload({ onUploadSuccess }) {
  const inputRef = useRef(null)
  const [isDragging, setIsDragging] = useState(false)
  const [selectedFile, setSelectedFile] = useState(null)
  const [validationError, setValidationError] = useState(null)
  const [uploadError, setUploadError] = useState(null)
  const [uploading, setUploading] = useState(false)

  // ── file selection helpers ──────────────────────────────────────────────

  function handleFile(file) {
    setUploadError(null)
    const error = validateCvFile(file)
    if (error) {
      setValidationError(error)
      setSelectedFile(null)
      return
    }
    setValidationError(null)
    setSelectedFile(file)
  }

  function clearSelection() {
    setSelectedFile(null)
    setValidationError(null)
    setUploadError(null)
    if (inputRef.current) inputRef.current.value = ''
  }

  // ── drag events ─────────────────────────────────────────────────────────

  function onDragOver(e) {
    e.preventDefault()
    setIsDragging(true)
  }

  function onDragLeave(e) {
    e.preventDefault()
    setIsDragging(false)
  }

  function onDrop(e) {
    e.preventDefault()
    setIsDragging(false)
    const file = e.dataTransfer.files?.[0]
    if (file) handleFile(file)
  }

  // ── click-to-browse ──────────────────────────────────────────────────────

  function onInputChange(e) {
    const file = e.target.files?.[0]
    if (file) handleFile(file)
  }

  // ── upload ───────────────────────────────────────────────────────────────

  async function handleUpload() {
    if (!selectedFile) return
    setUploading(true)
    setUploadError(null)

    try {
      const formData = new FormData()
      formData.append('file', selectedFile)

      const { data } = await api.post('/api/v1/candidates/me/cv', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })

      clearSelection()
      trackEvent('Profile', 'cv_upload')
      onUploadSuccess?.(data)
    } catch (err) {
      const msg = err.response?.data?.detail ?? err.message ?? 'Upload failed.'
      setUploadError(typeof msg === 'string' ? msg : JSON.stringify(msg))
      setSelectedFile(null)
      if (inputRef.current) inputRef.current.value = ''
    } finally {
      setUploading(false)
    }
  }

  // ── render ───────────────────────────────────────────────────────────────

  return (
    <div className="space-y-3">
      {/* Requirement 6.1 — drag-and-drop zone */}
      <div
        role="button"
        tabIndex={0}
        aria-label="CV upload zone. Drag your CV here or press Enter to browse."
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onDrop={onDrop}
        onClick={() => inputRef.current?.click()}
        onKeyDown={(e) => e.key === 'Enter' && inputRef.current?.click()}
        className={cn(
          'flex flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed px-6 py-10 cursor-pointer transition-colors',
          isDragging
            ? 'border-brand-blue bg-brand-blue/5'
            : 'border-border bg-surface hover:border-brand-blue/50 hover:bg-brand-blue/5',
        )}
      >
        <UploadCloud
          size={32}
          className={cn('transition-colors', isDragging ? 'text-brand-blue' : 'text-text-muted')}
          aria-hidden="true"
        />
        <p className="text-sm font-medium text-text">
          Drag your CV here, or{' '}
          <span className="text-brand-blue underline underline-offset-2">click to browse</span>
        </p>
        {/* Requirement 6.1 — subtext */}
        <p className="text-xs text-text-muted">PDF only · Max 5MB</p>
      </div>

      {/* Hidden file input — click-to-browse (Requirement 6.1) */}
      <input
        ref={inputRef}
        type="file"
        accept=".pdf"
        className="sr-only"
        aria-hidden="true"
        tabIndex={-1}
        onChange={onInputChange}
      />

      {/* Requirement 6.2 / 6.3 — inline validation error */}
      {validationError && (
        <p role="alert" className="text-sm text-red-600">
          {validationError}
        </p>
      )}

      {/* Requirement 6.4 — filename + size preview */}
      {selectedFile && !validationError && (
        <div className="flex items-center justify-between gap-3 rounded-lg border border-border bg-surface px-4 py-3">
          <div className="flex items-center gap-2 min-w-0">
            <FileText size={16} className="text-brand-blue flex-shrink-0" aria-hidden="true" />
            <span className="text-sm font-medium text-text truncate">{selectedFile.name}</span>
            <span className="text-xs text-text-muted flex-shrink-0">
              {formatBytes(selectedFile.size)}
            </span>
          </div>
          <button
            type="button"
            onClick={clearSelection}
            aria-label="Remove selected file"
            className="p-1 rounded text-text-muted hover:text-red-600 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-500"
          >
            <X size={14} aria-hidden="true" />
          </button>
        </div>
      )}

      {/* Requirement 6.6 — upload error */}
      {uploadError && (
        <p role="alert" className="text-sm text-red-600">
          {uploadError}
        </p>
      )}

      {/* Requirement 6.5 — confirm upload button */}
      {selectedFile && !validationError && (
        <Button
          onClick={handleUpload}
          disabled={uploading}
          className="w-full"
        >
          {uploading ? 'Uploading…' : 'Upload CV'}
        </Button>
      )}
    </div>
  )
}
