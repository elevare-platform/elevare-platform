import React, { useCallback, useEffect, useState } from 'react'
import { CheckCircle, XCircle, X } from 'lucide-react'
import PlanUpgradeLink from '@/components/PlanUpgradeLink'
import { isPlanLimitMessage } from '@/lib/planErrors'

export function Toast({ message, type = 'success', onDone }) {
  const [visible, setVisible] = useState(true)
  // A plan/limit error needs long enough on screen to actually read and
  // click the Upgrade link before it disappears — a plain success/error
  // toast doesn't have anything to click, so it can stay quick.
  const showUpgradeCta = type === 'error' && isPlanLimitMessage(message)
  const duration = showUpgradeCta ? 8000 : 3000

  useEffect(() => {
    const t = setTimeout(() => { setVisible(false); setTimeout(onDone, 300) }, duration)
    return () => clearTimeout(t)
  }, [onDone, duration])

  return (
    <div
      className={`fixed bottom-6 right-6 z-50 flex items-center gap-3 px-4 py-3 rounded-xl shadow-lg border text-sm font-medium transition-all duration-300 ${
        visible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-2'
      } ${type === 'success' ? 'bg-white border-green-200 text-green-800' : 'bg-white border-red-200 text-red-700'}`}
      role="status"
      aria-live="polite"
    >
      {type === 'success'
        ? <CheckCircle size={16} className="text-green-600 flex-shrink-0" />
        : <XCircle size={16} className="text-red-500 flex-shrink-0" />}
      <span>
        {message}
        {showUpgradeCta && <PlanUpgradeLink />}
      </span>
      <button onClick={() => { setVisible(false); setTimeout(onDone, 300) }} aria-label="Dismiss">
        <X size={14} className="text-text-muted hover:text-text" />
      </button>
    </div>
  )
}

export function useToast() {
  const [toasts, setToasts] = useState([])

  const show = useCallback((message, type = 'success') => {
    const id = Date.now()
    setToasts((prev) => [...prev, { id, message, type }])
  }, [])

  const remove = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  // `ToastContainer` is defined at module scope (not inside the hook) and
  // wired via a stable useCallback below  -  a function *component* redefined
  // inside a hook/render body gets a new identity every call, which makes
  // React treat it as a different component type and remount it (and every
  // Toast inside it, losing their dismiss timers) on every single re-render
  // of whatever called useToast().
  const ToastContainer = useCallback(
    () => <ToastList toasts={toasts} onRemove={remove} />,
    [toasts, remove]
  )

  return { show, ToastContainer }
}

function ToastList({ toasts, onRemove }) {
  return (
    <>
      {toasts.map((t) => (
        <Toast key={t.id} message={t.message} type={t.type} onDone={() => onRemove(t.id)} />
      ))}
    </>
  )
}
