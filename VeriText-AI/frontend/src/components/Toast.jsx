import { createContext, useCallback, useContext, useMemo, useState } from 'react'
import { AlertCircle, CheckCircle2, Info, X } from 'lucide-react'

const ToastContext = createContext(null)

const TONES = {
  success: { Icon: CheckCircle2, className: 'border-emerald-200 bg-white text-emerald-700' },
  error: { Icon: AlertCircle, className: 'border-red-200 bg-white text-red-700' },
  info: { Icon: Info, className: 'border-navy-200 bg-white text-navy-700' },
}

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])

  const dismiss = useCallback((id) => {
    setToasts((current) => current.filter((toast) => toast.id !== id))
  }, [])

  const push = useCallback(
    (message, { tone = 'info', detail = '', duration = 5000 } = {}) => {
      const id = `${Date.now()}-${Math.random().toString(16).slice(2, 8)}`
      setToasts((current) => [...current.slice(-2), { id, message, detail, tone }])
      if (duration) window.setTimeout(() => dismiss(id), duration)
      return id
    },
    [dismiss],
  )

  const value = useMemo(
    () => ({
      push,
      success: (message, options) => push(message, { ...options, tone: 'success' }),
      error: (message, options) => push(message, { ...options, tone: 'error' }),
      info: (message, options) => push(message, { ...options, tone: 'info' }),
    }),
    [push],
  )

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div
        className="pointer-events-none fixed bottom-4 right-4 z-50 flex w-[min(92vw,22rem)] flex-col gap-2"
        role="region"
        aria-label="Notifications"
      >
        {toasts.map((toast) => {
          const { Icon, className } = TONES[toast.tone] || TONES.info
          return (
            <div
              key={toast.id}
              className={`pointer-events-auto flex animate-fade-up items-start gap-2.5 rounded-lg border px-3.5 py-3 shadow-pop ${className}`}
              role="status"
            >
              <Icon className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
              <div className="min-w-0 flex-1">
                <p className="text-[12.5px] font-semibold">{toast.message}</p>
                {toast.detail && (
                  <p className="mt-0.5 text-[11.5px] font-normal text-navy-500">{toast.detail}</p>
                )}
              </div>
              <button
                type="button"
                onClick={() => dismiss(toast.id)}
                className="rounded p-0.5 text-navy-400 hover:bg-navy-50 hover:text-navy-700"
                aria-label="Dismiss notification"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
          )
        })}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast() {
  const context = useContext(ToastContext)
  if (!context) throw new Error('useToast must be used inside <ToastProvider>')
  return context
}
