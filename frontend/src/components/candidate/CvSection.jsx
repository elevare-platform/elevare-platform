import { Download, Star, Trash2, Upload } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

/**
 * Formats an ISO8601 date string as "Added DD MMM YYYY".
 * e.g. "2024-03-15T10:00:00Z" → "Added 15 Mar 2024"
 */
function formatAddedDate(isoString) {
  if (!isoString) return ''
  const date = new Date(isoString)
  return `Added ${date.toLocaleDateString('en-GB', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  })}`
}

/**
 * CvSection — renders the candidate's CV list with download, set-default,
 * and delete actions, plus an "Upload New CV" CTA that scrolls to the
 * upload zone.
 *
 * Props:
 *   cvs          — CandidateCvsResponse[]
 *   onDownload   — (id: string) => void
 *   onSetDefault — (id: string) => void
 *   onDelete     — (id: string) => void
 *   uploadRef    — React ref pointing to the CV upload component
 *
 * Requirements: 4.1, 4.2, 4.3, 4.4, 4.5
 */
export function CvSection({ cvs = [], onDownload, onSetDefault, onDelete, uploadRef }) {
  // Requirement 4.5 — scroll to the upload zone
  function handleUploadClick() {
    if (uploadRef?.current) {
      uploadRef.current.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
  }

  return (
    <section aria-labelledby="cv-section-heading">
      {/* Section header */}
      <div className="flex items-center justify-between mb-4">
        <h2
          id="cv-section-heading"
          className="text-lg font-semibold text-text"
        >
          Your CVs
        </h2>

        {/* Requirement 4.5 — Upload New CV CTA */}
        <Button
          variant="outline"
          size="sm"
          onClick={handleUploadClick}
          className="flex items-center gap-1.5"
        >
          <Upload size={14} aria-hidden="true" />
          Upload New CV
        </Button>
      </div>

      {/* CV list — Requirement 4.1 */}
      {cvs.length === 0 ? (
        <p className="text-sm text-text-muted py-4">
          No CVs uploaded yet.
        </p>
      ) : (
        <ul className="space-y-3" role="list">
          {cvs.map((cv) => (
            <li
              key={cv.id}
              className={cn(
                'flex items-center justify-between gap-4 rounded-lg border border-border bg-surface p-4',
                cv.is_default && 'border-brand-blue/40 bg-brand-blue/5',
              )}
            >
              {/* Left: filename + date + default badge */}
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-sm font-medium text-text truncate max-w-[260px]">
                    {cv.filename}
                  </span>

                  {/* Requirement 4.1 — "Default" badge */}
                  {cv.is_default && (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-brand-blue text-white">
                      <Star size={10} aria-hidden="true" />
                      Default
                    </span>
                  )}
                </div>

                {/* Requirement 4.1 — formatted created_at date */}
                <p className="text-xs text-text-muted mt-0.5">
                  {formatAddedDate(cv.created_at)}
                </p>
              </div>

              {/* Right: action buttons */}
              <div className="flex items-center gap-2 flex-shrink-0">
                {/* Requirement 4.2 — Download */}
                <button
                  type="button"
                  onClick={() => onDownload?.(cv.id)}
                  aria-label={`Download ${cv.filename}`}
                  className="p-1.5 rounded-md text-text-muted hover:text-brand-blue hover:bg-brand-blue/10 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-blue"
                >
                  <Download size={15} aria-hidden="true" />
                </button>

                {/* Requirement 4.3 — Set as Default (hidden if already default) */}
                {!cv.is_default && (
                  <button
                    type="button"
                    onClick={() => onSetDefault?.(cv.id)}
                    aria-label={`Set ${cv.filename} as default CV`}
                    className="p-1.5 rounded-md text-text-muted hover:text-brand-amber hover:bg-brand-amber/10 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-amber"
                    title="Set as default"
                  >
                    <Star size={15} aria-hidden="true" />
                  </button>
                )}

                {/* Requirement 4.4 — Delete */}
                <button
                  type="button"
                  onClick={() => onDelete?.(cv.id)}
                  aria-label={`Delete ${cv.filename}`}
                  className="p-1.5 rounded-md text-text-muted hover:text-red-600 hover:bg-red-50 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-500"
                >
                  <Trash2 size={15} aria-hidden="true" />
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
