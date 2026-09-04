import { X, Calendar } from 'lucide-react'
import StatusBadge from './StatusBadge'

export default function TestimonialDetailDrawer({ testimonial, onClose, onRequestModerate }) {
  if (!testimonial) return null
  const t = testimonial

  return (
    <div className="fixed inset-0 z-40 flex justify-end">
      <div className="absolute inset-0 bg-black/30" onClick={onClose} />
      <aside
        className="relative z-50 w-full max-w-lg bg-white h-full shadow-xl flex flex-col overflow-y-auto"
        role="dialog"
        aria-label="Testimonial details"
      >
        <div className="flex items-center justify-between px-6 py-4 border-b border-border">
          <h2 className="font-semibold text-text">Testimonial Details</h2>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-surface-muted" aria-label="Close">
            <X size={16} />
          </button>
        </div>

        <div className="flex-1 px-6 py-5 space-y-6">
          {/* Identity */}
          <div className="flex items-center gap-3">
            {t.image_url ? (
              <img src={t.image_url} alt={t.full_name} className="w-12 h-12 rounded-full object-cover flex-shrink-0" />
            ) : (
              <div className="w-12 h-12 rounded-full bg-brand-blue-light text-brand-blue flex items-center justify-center text-lg font-bold flex-shrink-0">
                {t.full_name.charAt(0)}
              </div>
            )}
            <div>
              <h3 className="text-lg font-bold text-text font-sans">{t.full_name}</h3>
              {(t.position || t.company) && (
                <p className="text-sm text-text-muted">
                  {[t.position, t.company].filter(Boolean).join(' · ')}
                </p>
              )}
            </div>
          </div>

          <StatusBadge value={t.status} />

          {/* Testimony */}
          <div>
            <p className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-2">Testimony</p>
            <p className="text-sm text-text leading-relaxed whitespace-pre-line">{t.testimony}</p>
          </div>

          {/* Meta */}
          <div className="grid grid-cols-2 gap-3 text-sm">
            <div className="flex items-center gap-2 text-text-muted">
              <Calendar size={13} />
              <span>Submitted {new Date(t.created_at).toLocaleDateString()}</span>
            </div>
            {t.reviewed_at && (
              <div className="flex items-center gap-2 text-text-muted">
                <Calendar size={13} />
                <span>Reviewed {new Date(t.reviewed_at).toLocaleDateString()}</span>
              </div>
            )}
          </div>

          {/* Moderation actions */}
          <div className="space-y-2 pt-2 border-t border-border">
            <p className="text-xs font-semibold text-text-muted uppercase tracking-wider">Moderation</p>
            <div className="flex flex-wrap gap-2">
              {t.status !== 'approved' && (
                <button
                  onClick={() => onRequestModerate(t, 'approved')}
                  className="px-4 py-2 text-sm rounded-lg bg-green-100 text-green-700 hover:bg-green-200 font-medium transition-colors"
                >
                  Approve
                </button>
              )}
              {t.status !== 'rejected' && (
                <button
                  onClick={() => onRequestModerate(t, 'rejected')}
                  className="px-4 py-2 text-sm rounded-lg bg-red-100 text-red-700 hover:bg-red-200 font-medium transition-colors"
                >
                  Reject
                </button>
              )}
              {t.status !== 'pending' && (
                <button
                  onClick={() => onRequestModerate(t, 'pending')}
                  className="px-4 py-2 text-sm rounded-lg border border-border text-text-muted hover:bg-surface-muted font-medium transition-colors"
                >
                  Reset to Pending
                </button>
              )}
            </div>
          </div>
        </div>
      </aside>
    </div>
  )
}
