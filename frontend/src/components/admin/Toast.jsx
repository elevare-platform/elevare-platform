import React, { useEffect, useState } from 'react'
import { CheckCircle, XCircle, X } from 'lucide-react'

export function Toast({ message, type = 'success', onDone }) {
  const [visible, setVisible] = useState(true)

  useEffect(() => {
    const t = setTimeout(() => { setVisible(false); setTimeout(onDone, 300) }, 3000)
    return () => clearTimeout(t)
  }, [onDone])

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
      {message}
      <button onClick={() => { setVisible(false); setTimeout(onDone, 300) }} aria-label="Dismiss">
        <X size={14} className="text-text-muted hover:text-text" />
      </button>
    </div>
  )
}

export function useToast() {
  const [toasts, setToasts] = useState([])

  const show = (message, type = 'success') => {
    const id = Date.now()
    setToasts((prev) => [...prev, { id, message, type }])
  }

  const remove = (id) => setToasts((prev) => prev.filter((t) => t.id !== id))

  const ToastContainer = () => (
    <>
      {toasts.map((t) => (
        <Toast key={t.id} message={t.message} type={t.type} onDone={() => remove(t.id)} />
      ))}
    </>
  )

  return { show, ToastContainer }
}
