import React from 'react'
import { Loader2, Sparkles, X, RotateCcw, Check } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { wordDiff } from '@/lib/wordDiff'
import { useJobDescriptionAI } from '@/hooks/useJobDescriptionAI'
import {
  AI_MODES,
  AI_MODE_LABELS,
  MODES_REQUIRING_TEXT,
  MODES_REQUIRING_NO_TEXT,
} from '@/services/aiJobDescription'

/**
 * AiAssistModal — mode picker + preview/apply flow for AI-assisted
 * job description writing. Opened from a per-field "AI Assist" button
 * in JobForm. Does not mutate form state itself — calls onApply(text)
 * only when the user explicitly applies a suggestion.
 */
export function AiAssistModal({ isOpen, onClose, fieldLabel, fieldKey, currentText, jobContext, onApply }) {
  const { loading, error, suggestion, generate } = useJobDescriptionAI()
  const [selectedMode, setSelectedMode] = React.useState(null)

  const hasText = currentText.trim().length > 0

  const availableModes = React.useMemo(() => {
    return Object.values(AI_MODES).filter((mode) => {
      if (MODES_REQUIRING_NO_TEXT.has(mode)) return true // generate is always offered
      if (MODES_REQUIRING_TEXT.has(mode)) return hasText
      return true
    })
  }, [hasText])

  React.useEffect(() => {
    if (!isOpen) return
    const onKeyDown = (e) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [isOpen, onClose])

  if (!isOpen) return null

  const runMode = async (mode) => {
    setSelectedMode(mode)
    await generate({ mode, field: fieldKey, currentText, jobContext })
  }

  const handleApply = () => {
    if (suggestion) onApply(suggestion)
    onClose()
  }

  const diffOps = suggestion ? wordDiff(currentText, suggestion) : []

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40" role="dialog" aria-modal="true">
      <div className="w-full max-w-2xl max-h-[85vh] flex flex-col rounded-lg bg-surface shadow-xl border border-border">

        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-border">
          <div className="flex items-center gap-2">
            <Sparkles size={18} className="text-brand-blue" />
            <h2 className="text-sm font-semibold">AI Assist — {fieldLabel}</h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="text-text-muted hover:text-text transition-colors"
          >
            <X size={18} />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">

          {/* Mode picker */}
          <div>
            <p className="text-xs font-medium text-text-muted mb-2">Choose an action</p>
            <div className="flex flex-wrap gap-2">
              {availableModes.map((mode) => (
                <Button
                  key={mode}
                  type="button"
                  size="sm"
                  variant={selectedMode === mode ? 'default' : 'outline'}
                  onClick={() => runMode(mode)}
                  disabled={loading}
                >
                  {AI_MODE_LABELS[mode]}
                </Button>
              ))}
            </div>
            {!hasText && (
              <p className="text-xs text-text-muted mt-2">
                This field is empty — only "Generate from scratch" is available. Fill in the job title
                and required skills above for a better result.
              </p>
            )}
          </div>

          {/* Loading */}
          {loading && (
            <div className="flex items-center gap-2 text-sm text-text-muted py-6 justify-center">
              <Loader2 size={16} className="animate-spin" />
              Generating suggestion…
            </div>
          )}

          {/* Error + retry */}
          {error && !loading && (
            <div className="rounded-md bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700 flex items-center justify-between gap-3">
              <span>{error}</span>
              <Button type="button" size="sm" variant="outline" onClick={() => selectedMode && runMode(selectedMode)}>
                <RotateCcw size={14} className="mr-1.5" />
                Retry
              </Button>
            </div>
          )}

          {/* Suggestion preview */}
          {suggestion && !loading && (
            <div className="space-y-2">
              <p className="text-xs font-medium text-text-muted">
                Preview {hasText && <span className="text-text-muted/70">— additions in green, removals struck through</span>}
              </p>
              <div className="rounded-md border border-border bg-background px-3 py-2.5 text-sm leading-relaxed whitespace-pre-wrap max-h-64 overflow-y-auto">
                {hasText ? (
                  diffOps.map((op, idx) => {
                    if (op.type === 'same') return <span key={idx}>{op.value}</span>
                    if (op.type === 'added') {
                      return (
                        <span key={idx} className="bg-green-100 text-green-800 rounded-sm">
                          {op.value}
                        </span>
                      )
                    }
                    return (
                      <span key={idx} className="bg-red-100 text-red-700 line-through rounded-sm">
                        {op.value}
                      </span>
                    )
                  })
                ) : (
                  suggestion
                )}
              </div>
              <p className="text-xs text-text-muted">{suggestion.length} characters</p>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-2 px-5 py-4 border-t border-border">
          <Button type="button" variant="ghost" onClick={onClose}>Cancel</Button>
          {suggestion && !loading && (
            <>
              <Button
                type="button"
                variant="outline"
                onClick={() => selectedMode && runMode(selectedMode)}
              >
                <RotateCcw size={14} className="mr-1.5" />
                Regenerate
              </Button>
              <Button type="button" onClick={handleApply}>
                <Check size={14} className="mr-1.5" />
                Apply suggestion
              </Button>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

export function AiAssistButton({ onClick, className }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'inline-flex items-center gap-1 text-xs font-medium text-brand-blue hover:text-brand-blue-dark transition-colors',
        className
      )}
    >
      <Sparkles size={13} />
      AI Assist
    </button>
  )
}
