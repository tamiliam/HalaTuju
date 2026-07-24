'use client'

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useState } from 'react'
import { I18nProvider } from '@/lib/i18n'
import { BrandingProvider } from '@/lib/branding-context'
import { AuthProvider } from '@/lib/auth-context'
import AuthGateModal from '@/components/AuthGateModal'
import { ToastProvider } from '@/components/Toast'

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 60 * 1000, // 1 minute
            refetchOnWindowFocus: false,
          },
        },
      })
  )

  return (
    <QueryClientProvider client={queryClient}>
      {/* BrandingProvider is OUTSIDE I18nProvider so t() can read the branding (auto-injecting
          the AUTO_TOKENS). Platform mode never fetches — zero flash for BrightPath. */}
      <BrandingProvider>
        <I18nProvider>
          <AuthProvider>
            <ToastProvider>
              {children}
              <AuthGateModal />
            </ToastProvider>
          </AuthProvider>
        </I18nProvider>
      </BrandingProvider>
    </QueryClientProvider>
  )
}
