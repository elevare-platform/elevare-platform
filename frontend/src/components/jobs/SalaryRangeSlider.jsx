import { useRef, useCallback, useEffect, useState } from 'react'
import { cn } from '@/lib/utils'

// Salary range constants (NGN)
export const SALARY_MIN = 0
export const SALARY_MAX = 5_000_000
const STEP = 50_000

/**
 * Snap a raw value to the nearest step within [SALARY_MIN, SALARY_MAX].
 */
function snap(value) {
  const clamped = Math.max(SALARY_MIN, Math.min(SALARY_MAX, value))
  return Math.round(clamped / STEP) * STEP
}

/**
 * Format a salary value for display in the slider label.
 * 0 → "₦0", 500000 → "₦500k", 1200000 → "₦1.2M"
 */
function fmt(value) {
  if (value >= 1_000_000) {
    const m = value / 1_000_000
    return `₦${Number.isInteger(m) ? m : parseFloat(m.toFixed(1))}M`
  }
  if (value >= 1_000) {
    const k = value / 1_000
    return `₦${Number.isInteger(k) ? k : parseFloat(k.toFixed(1))}k`
  }
  return `₦${value}`
}

/**
 * SalaryRangeSlider — dual-handle range slider for salary filtering.
 *
 * @param {Object}   props
 * @param {number}   props.min        - Current lower bound (controlled)
 * @param {number}   props.max        - Current upper bound (controlled)
 * @param {Function} props.onChange   - Called with { min, max } on every change
 */
export function SalaryRangeSlider({ min, max, onChange }) {
  const trackRef = useRef(null)
  // Which handle is being dragged: 'min' | 'max' | null
  const dragging = useRef(null)

  // Convert a clientX position to a salary value
  const clientXToValue = useCallback((clientX) => {
    const rect = trackRef.current.getBoundingClientRect()
    const ratio = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width))
    return snap(SALARY_MIN + ratio * (SALARY_MAX - SALARY_MIN))
  }, [])

  const onPointerMove = useCallback((e) => {
    if (!dragging.current) return
    const val = clientXToValue(e.clientX)
    if (dragging.current === 'min') {
      onChange({ min: Math.min(val, max - STEP), max })
    } else {
      onChange({ min, max: Math.max(val, min + STEP) })
    }
  }, [clientXToValue, min, max, onChange])

  const onPointerUp = useCallback(() => {
    dragging.current = null
    window.removeEventListener('pointermove', onPointerMove)
    window.removeEventListener('pointerup', onPointerUp)
  }, [onPointerMove])

  const startDrag = useCallback((handle) => (e) => {
    e.preventDefault()
    dragging.current = handle
    window.addEventListener('pointermove', onPointerMove)
    window.addEventListener('pointerup', onPointerUp)
  }, [onPointerMove, onPointerUp])

  // Clean up listeners if component unmounts mid-drag
  useEffect(() => () => {
    window.removeEventListener('pointermove', onPointerMove)
    window.removeEventListener('pointerup', onPointerUp)
  }, [onPointerMove, onPointerUp])

  // Track click — jump the nearest handle to the clicked position
  const onTrackClick = useCallback((e) => {
    if (dragging.current) return
    const val = clientXToValue(e.clientX)
    const distMin = Math.abs(val - min)
    const distMax = Math.abs(val - max)
    if (distMin <= distMax) {
      onChange({ min: Math.min(val, max - STEP), max })
    } else {
      onChange({ min, max: Math.max(val, min + STEP) })
    }
  }, [clientXToValue, min, max, onChange])

  // Percentage positions for CSS
  const range = SALARY_MAX - SALARY_MIN
  const minPct = ((min - SALARY_MIN) / range) * 100
  const maxPct = ((max - SALARY_MIN) / range) * 100

  return (
    <div className="w-full select-none">
      {/* Value labels */}
      <div className="flex justify-between text-xs font-medium text-text mb-3">
        <span>{fmt(min)}</span>
        <span>{fmt(max)}</span>
      </div>

      {/* Track */}
      <div
        ref={trackRef}
        className="relative h-1.5 rounded-full bg-border cursor-pointer"
        onClick={onTrackClick}
      >
        {/* Active range fill */}
        <div
          className="absolute h-full rounded-full bg-brand-blue pointer-events-none"
          style={{ left: `${minPct}%`, width: `${maxPct - minPct}%` }}
        />

        {/* Min handle */}
        <Handle
          pct={minPct}
          label={fmt(min)}
          onPointerDown={startDrag('min')}
        />

        {/* Max handle */}
        <Handle
          pct={maxPct}
          label={fmt(max)}
          onPointerDown={startDrag('max')}
        />
      </div>

      {/* Axis labels */}
      <div className="flex justify-between text-xs text-text-muted mt-2">
        <span>{fmt(SALARY_MIN)}</span>
        <span>{fmt(SALARY_MAX)}+</span>
      </div>
    </div>
  )
}

function Handle({ pct, label, onPointerDown }) {
  return (
    <button
      type="button"
      aria-label={`Salary handle: ${label}`}
      onPointerDown={onPointerDown}
      className={cn(
        'absolute top-1/2 -translate-y-1/2 -translate-x-1/2',
        'w-4 h-4 rounded-full bg-white border-2 border-brand-blue shadow-sm',
        'cursor-grab active:cursor-grabbing',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-blue focus-visible:ring-offset-1',
        'transition-transform hover:scale-110'
      )}
      style={{ left: `${pct}%` }}
    />
  )
}
