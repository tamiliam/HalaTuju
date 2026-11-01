'use client'

import { useState, useCallback, useEffect, type ReactNode } from 'react'
import { useT } from '@/lib/i18n'
import { ToastContext } from '@/components/ToastContext'

interface ToastState {
  message: string
  type: 'success' | 'error'
  id: number
}

// The context and `useToast` live in `ToastContext.ts` (TD-289) — import the hook from there.

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastState[]>([])

  const showToast = useCallback((message: string, type: 'success' | 'error') => {
    const id = Date.now()
    setToasts(prev => [...prev, { message, type, id }])
  }, [])

  const removeToast = useCallback((id: number) => {
    setToasts(prev => prev.filter(t => t.id !== id))
  }, [])

  return (
    <ToastContext.Provider value={{ showToast }}>
      {children}
      {/* Toast container — bottom-right on a desktop; on a phone, full width less 16 px gutters and above the home bar (Mobile M1a),
          and above a page's sticky bottom bar when it has one (`--bottom-bar`, lib/bottomBarInset.ts, Mobile M3) */}
      <div className="fixed inset-x-4 bottom-[calc(max(1rem,env(safe-area-inset-bottom))+var(--bottom-bar,0px))] z-50 flex flex-col gap-2 sm:left-auto sm:right-[max(1rem,env(safe-area-inset-right))]">
        {toasts.map(toast => (
          <ToastItem key={toast.id} toast={toast} onDismiss={removeToast} />
        ))}
      </div>
    </ToastContext.Provider>
  )
}

function ToastItem({ toast, onDismiss }: { toast: ToastState; onDismiss: (id: number) => void }) {
  const { t } = useT()
  useEffect(() => {
    const timer = setTimeout(() => onDismiss(toast.id), 3000)
    return () => clearTimeout(timer)
  }, [toast.id, onDismiss])

  const styles = toast.type === 'success'
    ? 'bg-positive-fill text-positive-fill-ink'
    : 'bg-critical-fill text-critical-fill-ink'

  return (
    <div className={`${styles} px-4 py-3 rounded-lg shadow-lg text-sm font-medium animate-slide-in flex items-center gap-2 sm:max-w-sm`}>
      {toast.type === 'success' ? (
        <svg className="w-4 h-4 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
        </svg>
      ) : (
        <svg className="w-4 h-4 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
        </svg>
      )}
      {toast.message}
      <button
        onClick={() => onDismiss(toast.id)}
        className="ml-auto opacity-70 hover:opacity-100"
        aria-label={t('common.dismiss')}
      >
        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>
  )
}
