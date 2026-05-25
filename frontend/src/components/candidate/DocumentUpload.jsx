import { useRef, useState } from 'react'
import { UploadCloud, FileText, X } from 'lucide-react'
import { validateDocumentFile } from '@/lib/uploadValidation'
import api from '@/lib/api'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'

const DOCUMENT_TYPES = ['Certificate', 'Cover Letter', 'Portfolio', 'Other']

/**
 * Formats bytes into a human-readable string (e.g. "1.2 MB").
 */
function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1_048_576) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1_048_576).toFixed(1)} MB`
}

/**
 * DocumentUpload — drag-and-drop career document upload component.
 *
 * Props:
 *   onUploadSuccess — (newDoc: CandidateDocumentsResponse) => void   called after 201
 *
 * Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6
 */
export function DocumentUpload({ onUploadSuccess }) {
  const inputRef = useRef(null)
  const [isDragging, setIsDragging] = useState(false)
  const [selectedFile, setSelectedFile] = useState(null)
  const [documentType, setDocumentType] = useState(DOCUMENT_TYPES[0])
  const [validationError, setValidationError] = useState(null)
  const [uploadError, setUploadError] = useState(null)
  const [uploading, setUploading] = useState(false)

  // ── file selection helpers ──────────────────────────────────────────────

  function handleFile(file) {
    setUploadError(null)
    const error = validateDocumentFile(file)
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
      formData.append('document_type', documentType)

      const { data } = await api.post('/api/v1/candidates/me/documents', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })

      clearSelection()
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
      {/* Requirement 7.4 — document type selector */}
      <div className="flex flex-col gap-1">
        <label htmlFor="document-type" className="text-sm font-medium text-text">
          Document Type
        </label>
        <select
          id="document-type"
          value={documentType}
          onChange={(e) => setDocumentType(e.target.value)}
          className="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text focus:outline-none focus:ring-2 focus:ring-brand-blue"
        >
          {DOCUMENT_TYPES.map((type) => (
            <option key={type} value={type}>
              {type}
            </option>
          ))}
        </select>
      </div>

      {/* Requirement 7.1 — drag-and-drop zone */}
      <div
        role="button"
        tabIndex={0}
        aria-label="Document upload zone. Drag your document here or press Enter to browse."
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
          Drag your document here, or{' '}
          <span className="text-brand-blue underline underline-offset-2">click to browse</span>
        </p>
        {/* Requirement 7.1 — accepted formats subtext */}
        <p className="text-xs text-text-muted">PDF, Word, PNG, JPG · Max 5MB</p>
      </div>

      {/* Hidden file input — click-to-browse */}
      <input
        ref={inputRef}
        type="file"
        accept=".pdf,.docx,.png,.jpg,.jpeg"
        className="sr-only"
        aria-hidden="true"
        tabIndex={-1}
        onChange={onInputChange}
      />

      {/* Requirement 7.2 / 7.3 — inline validation error */}
      {validationError && (
        <p role="alert" className="text-sm text-red-600">
          {validationError}
        </p>
      )}

      {/* File preview */}
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

      {/* Requirement 7.6 — upload error */}
      {uploadError && (
        <p role="alert" className="text-sm text-red-600">
          {uploadError}
        </p>
      )}

      {/* Requirement 7.5 — confirm upload button */}
      {selectedFile && !validationError && (
        <Button
          onClick={handleUpload}
          disabled={uploading}
          className="w-full"
        >
          {uploading ? 'Uploading…' : 'Upload Document'}
        </Button>
      )}
    </div>
  )
}
