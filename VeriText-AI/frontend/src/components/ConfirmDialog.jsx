import { useEffect } from 'react'
import { Spinner } from './Primitives'

export default function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  tone = 'danger',
  busy = false,
  onConfirm,
  onCancel,
}) {
  useEffect(() => {
    if (!open) return undefined
    const onKey = (event) => {
      if (event.key === 'Escape') onCancel?.()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onCancel])

  if (!open) return null

  const confirmClass =
    tone === 'danger'
      ? 'bg-red-600 text-white hover:bg-red-700'
      : 'bg-navy-900 text-white hover:bg-navy-800'

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center p-4">
      <button
        type="button"
        aria-label="Close dialog"
        className="absolute inset-0 bg-navy-950/40 backdrop-blur-[1px]"
        onClick={onCancel}
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="confirm-title"
        className="relative w-full max-w-md animate-fade-up rounded-xl border border-navy-100 bg-white p-5 shadow-pop"
      >
        <h3 id="confirm-title" className="text-[15px] font-semibold text-navy-900">
          {title}
        </h3>
        {description && (
          <p className="mt-1.5 text-[13px] leading-relaxed text-navy-600">{description}</p>
        )}
        <div className="mt-5 flex justify-end gap-2">
          <button type="button" className="btn btn-ghost btn-md" onClick={onCancel} disabled={busy}>
            {cancelLabel}
          </button>
          <button type="button" className={`btn btn-md ${confirmClass}`} onClick={onConfirm} disabled={busy}>
            {busy && <Spinner className="h-3.5 w-3.5" />}
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  )
}
