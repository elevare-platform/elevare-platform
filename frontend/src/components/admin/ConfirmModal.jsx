import { useState } from 'react'
import { AlertTriangle } from 'lucide-react'

export default function ConfirmModal({ title, description, confirmLabel = 'Confirm', danger = false, onConfirm, onCancel, requireReason = false }) {
  const [reason, setReason] = useState('')

  const handleConfirm = () => {
    onConfirm(reason || undefined)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center px-4">
      <div className="absolute inset-0 bg-black/40" onClick={onCancel} />
      <div className="relative bg-white rounded-xl shadow-xl max-w-md w-full p-6 space-y-4">
        <div className="flex items-start gap-3">
          {danger && (
            <div className="w-9 h-9 rounded-full bg-red-100 flex items-center justify-center flex-shrink-0">
              <AlertTriangle size={16} className="text-red-600" />
            </div>
          )}
          <div>
            <h2 className="text-base font-semibold text-text">{title}</h2>
            {description && <p className="text-sm text-text-muted mt-1">{description}</p>}
          </div>
        </div>

        {requireReason && (
          <div>
            <label className="text-xs font-medium text-text-muted block mb-1">
              Reason <span className="text-text-muted">(optional)</span>
            </label>
            <textarea
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              rows={2}
              placeholder="Add a reason for the audit log…"
              className="w-full text-sm rounded-lg border border-border px-3 py-2 focus:outline-none focus:ring-2 focus:ring-brand-blue resize-none"
            />
          </div>
        )}

        <div className="flex gap-3 justify-end">
          <button
            onClick={onCancel}
            className="px-4 py-2 text-sm rounded-lg border border-border hover:bg-surface-muted transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleConfirm}
            className={`px-4 py-2 text-sm rounded-lg font-medium transition-colors ${
              danger
                ? 'bg-red-600 text-white hover:bg-red-700'
                : 'bg-brand-blue text-white hover:opacity-90'
            }`}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  )
}
