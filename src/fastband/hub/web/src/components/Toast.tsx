/**
 * Toast Notification Components.
 */

import { useEffect, useState } from 'react'
import { clsx } from 'clsx'
import { X, CheckCircle, AlertCircle, AlertTriangle, Info } from 'lucide-react'
import { useToastStore, type Toast, type ToastType } from '../stores/toast'

const iconMap: Record<ToastType, React.ReactNode> = {
  success: <CheckCircle className="w-5 h-5" />,
  error: <AlertCircle className="w-5 h-5" />,
  warning: <AlertTriangle className="w-5 h-5" />,
  info: <Info className="w-5 h-5" />,
}

const colorMap: Record<ToastType, string> = {
  success: 'border-success/50 bg-success/10 text-success shadow-[0_0_20px_rgba(16,185,129,0.15)]',
  error: 'border-error/50 bg-error/10 text-error shadow-[0_0_20px_rgba(239,68,68,0.15)]',
  warning: 'border-warning/50 bg-warning/10 text-warning shadow-[0_0_20px_rgba(245,158,11,0.15)]',
  info: 'border-cyan/50 bg-cyan/10 text-cyan shadow-[0_0_20px_rgba(0,212,255,0.15)]',
}

const iconColorMap: Record<ToastType, string> = {
  success: 'text-success',
  error: 'text-error',
  warning: 'text-warning',
  info: 'text-cyan',
}

function ToastItem({ toast, onDismiss }: { toast: Toast; onDismiss: () => void }) {
  const [isVisible, setIsVisible] = useState(false)
  const [isLeaving, setIsLeaving] = useState(false)

  useEffect(() => {
    // Trigger enter animation
    requestAnimationFrame(() => setIsVisible(true))
  }, [])

  const handleDismiss = () => {
    setIsLeaving(true)
    setTimeout(onDismiss, 200)
  }

  return (
    <div
      className={clsx(
        'relative flex items-start gap-3 px-4 py-3 rounded-lg border backdrop-blur-md',
        'transition-all duration-200',
        colorMap[toast.type],
        isVisible && !isLeaving ? 'toast-enter' : 'opacity-0 translate-x-8'
      )}
      role="alert"
    >
      {/* Icon */}
      <span className={clsx('flex-shrink-0 mt-0.5', iconColorMap[toast.type])}>
        {iconMap[toast.type]}
      </span>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <p className="font-medium text-sm text-slate-100">{toast.title}</p>
        {toast.message && (
          <p className="mt-0.5 text-sm text-slate-400">{toast.message}</p>
        )}
      </div>

      {/* Dismiss button */}
      <button
        onClick={handleDismiss}
        className="flex-shrink-0 p-1 rounded hover:bg-void-700 transition-colors"
        aria-label="Dismiss"
      >
        <X className="w-4 h-4 text-slate-500" />
      </button>
    </div>
  )
}

export function ToastContainer() {
  const { toasts, removeToast } = useToastStore()

  if (toasts.length === 0) return null

  return (
    <div
      className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 max-w-sm w-full pointer-events-none"
      aria-live="polite"
    >
      {toasts.map((toast) => (
        <div key={toast.id} className="pointer-events-auto">
          <ToastItem toast={toast} onDismiss={() => removeToast(toast.id)} />
        </div>
      ))}
    </div>
  )
}
