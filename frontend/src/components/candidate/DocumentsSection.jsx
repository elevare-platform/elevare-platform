import { Download, FileText, Trash2 } from 'lucide-react'

/**
 * Known document_type values and their human-readable labels.
 * Requirement 5.4 — display known types as styled badges.
 * Requirement 5.5 — fall back to "Document" for null / unrecognised values.
 */
const DOCUMENT_TYPE_LABELS = {
  Certificate: 'Certificate',
  'Cover Letter': 'Cover Letter',
  Portfolio: 'Portfolio',
  Other: 'Other',
}

/**
 * Returns the badge label for a document_type value.
 * Falls back to "Document" for null or unrecognised values (Requirement 5.5).
 */
function getDocumentTypeLabel(documentType) {
  if (!documentType) return 'Document'
  return DOCUMENT_TYPE_LABELS[documentType] ?? 'Document'
}

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
 * DocumentsSection — renders the candidate's career documents list with
 * download and delete actions.
 *
 * Props:
 *   documents  — CandidateDocumentsResponse[]
 *   onDownload — (id: string) => void   (Requirement 5.2)
 *   onDelete   — (id: string) => void   (Requirement 5.3)
 *
 * Requirements: 5.1, 5.2, 5.3, 5.4, 5.5
 */
export function DocumentsSection({ documents = [], onDownload, onDelete }) {
  return (
    <section aria-labelledby="documents-section-heading">
      {/* Section header */}
      <h2
        id="documents-section-heading"
        className="text-lg font-semibold text-text mb-4"
      >
        Career Documents
      </h2>

      {/* Document list — Requirement 5.1 */}
      {documents.length === 0 ? (
        <p className="text-sm text-text-muted py-4">
          No documents uploaded yet.
        </p>
      ) : (
        <ul className="space-y-3" role="list">
          {documents.map((doc) => (
            <li
              key={doc.id}
              className="flex items-center justify-between gap-4 rounded-lg border border-border bg-surface p-4"
            >
              {/* Left: icon + filename + type badge + date */}
              <div className="min-w-0 flex-1 flex items-start gap-3">
                <FileText
                  size={18}
                  className="text-text-muted flex-shrink-0 mt-0.5"
                  aria-hidden="true"
                />

                <div className="min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-medium text-text truncate max-w-[260px]">
                      {doc.filename}
                    </span>

                    {/* Requirement 5.4 / 5.5 — document_type badge */}
                    <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold bg-surface-alt text-text-muted border border-border">
                      {getDocumentTypeLabel(doc.document_type)}
                    </span>
                  </div>

                  {/* Requirement 5.1 — formatted created_at date */}
                  <p className="text-xs text-text-muted mt-0.5">
                    {formatAddedDate(doc.created_at)}
                  </p>
                </div>
              </div>

              {/* Right: action buttons */}
              <div className="flex items-center gap-2 flex-shrink-0">
                {/* Requirement 5.2 — Download */}
                <button
                  type="button"
                  onClick={() => onDownload?.(doc.id)}
                  aria-label={`Download ${doc.filename}`}
                  className="p-1.5 rounded-md text-text-muted hover:text-brand-blue hover:bg-brand-blue/10 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-blue"
                >
                  <Download size={15} aria-hidden="true" />
                </button>

                {/* Requirement 5.3 — Delete */}
                <button
                  type="button"
                  onClick={() => onDelete?.(doc.id)}
                  aria-label={`Delete ${doc.filename}`}
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
