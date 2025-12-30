/**
 * Reusable Modal Component for Control Plane.
 */

import { useEffect, useCallback, ReactNode } from 'react'
import { clsx } from 'clsx'
import { X } from 'lucide-react'

interface ModalProps {
  isOpen: boolean
  onClose: () => void
  title: string
  children: ReactNode
  footer?: ReactNode
  size?: 'sm' | 'md' | 'lg'
}

export function Modal({
  isOpen,
  onClose,
  title,
  children,
  footer,
  size = 'md',
}: ModalProps) {
  // Close on escape key
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose()
      }
    },
    [onClose]
  )

  useEffect(() => {
    if (isOpen) {
      document.addEventListener('keydown', handleKeyDown)
      document.body.style.overflow = 'hidden'
    }

    return () => {
      document.removeEventListener('keydown', handleKeyDown)
      document.body.style.overflow = 'unset'
    }
  }, [isOpen, handleKeyDown])

  if (!isOpen) return null

  const sizeClasses = {
    sm: 'max-w-md',
    md: 'max-w-lg',
    lg: 'max-w-2xl',
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop with grid pattern */}
      <div
        className="absolute inset-0 modal-backdrop-grid backdrop-blur-sm animate-in"
        onClick={onClose}
      />

      {/* Modal with enhanced styling */}
      <div
        className={clsx(
          'relative w-full mx-4',
          sizeClasses[size],
          'bg-void-800/95 backdrop-blur-md border border-void-600 rounded-xl',
          'shadow-[0_0_80px_rgba(0,0,0,0.8),0_0_40px_rgba(0,212,255,0.05)]',
          'animate-in'
        )}
        style={{
          animation: 'modalSlideIn 0.2s ease-out',
        }}
      >
        {/* Glow line at top */}
        <div className="absolute top-0 left-1/4 right-1/4 h-px bg-gradient-to-r from-transparent via-cyan/50 to-transparent" />

        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-void-600/80">
          <h2 className="text-lg font-display font-semibold text-slate-100">
            {title}
          </h2>
          <button
            onClick={onClose}
            className="btn-icon text-slate-400 hover:text-slate-200 hover:bg-void-600"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="px-6 py-4">{children}</div>

        {/* Footer */}
        {footer && (
          <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-void-600 bg-void-900/50 rounded-b-xl">
            {footer}
          </div>
        )}
      </div>

      <style>{`
        @keyframes modalSlideIn {
          from {
            opacity: 0;
            transform: translateY(-20px) scale(0.95);
          }
          to {
            opacity: 1;
            transform: translateY(0) scale(1);
          }
        }
      `}</style>
    </div>
  )
}
