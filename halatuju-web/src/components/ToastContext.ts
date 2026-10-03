'use client'

/**
 * The toast CONTEXT and its hook, apart from the provider that draws the toasts (TD-289,
 * 2026-10-03).
 *
 * Every page that only RAISES a toast (`useToast().showToast`) needs the context object and
 * nothing else; the provider, its state and the toast markup belong to the layout, which mounts
 * `ToastProvider` once (`src/app/providers.tsx`). While both lived in `Toast.tsx`, the language
 * picker's `useToast` pulled the whole provider module into `/`'s page chunk. Import `useToast`
 * from here; import `ToastProvider` from `Toast.tsx`.
 */
import { createContext, useContext } from 'react'

export interface ToastContextValue {
  showToast: (message: string, type: 'success' | 'error') => void
}

export const ToastContext = createContext<ToastContextValue>({ showToast: () => {} })

export function useToast() {
  return useContext(ToastContext)
}
