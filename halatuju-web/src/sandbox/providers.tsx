'use client'

/**
 * The provider stack the real screens expect, with the network stubbed and no identity.
 *
 * This mirrors `src/app/providers.tsx` deliberately rather than reusing it. Two things must differ
 * and both matter: `AuthProvider` mints an anonymous Supabase user on mount, which a sandbox must
 * never do (it would create real auth rows for a design review), and `AuthGateModal` would open
 * over the screens a designer came to look at. Everything else — QueryClient, BrandingProvider
 * outside I18nProvider so `t()` can read the branding tokens, ToastProvider — is the same stack in
 * the same order.
 *
 * ⚠ IF `src/app/providers.tsx` GAINS A PROVIDER, THIS FILE NEEDS IT TOO. That is a real drift risk
 * and the compiler cannot catch it, so `sandbox-safety.test.ts` compares the two files' provider
 * lists and fails when they diverge.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useState, type ReactNode } from 'react'
import { I18nProvider } from '@/lib/i18n'
import { BrandingProvider } from '@/lib/branding-context'
import { ToastProvider } from '@/components/Toast'
import { installStubFetch } from './stubFetch'

export function SandboxProviders({ children }: { children: ReactNode }) {
  // Installed during render, not in an effect: the components below fetch on mount, and an effect
  // in this component runs AFTER its children's effects. Installing later would let the first real
  // request escape to a network that is not there.
  const [queryClient] = useState(() => {
    installStubFetch()
    return new QueryClient({
      defaultOptions: { queries: { staleTime: 60 * 1000, refetchOnWindowFocus: false, retry: false } },
    })
  })

  return (
    <QueryClientProvider client={queryClient}>
      <BrandingProvider>
        <I18nProvider>
          <ToastProvider>{children}</ToastProvider>
        </I18nProvider>
      </BrandingProvider>
    </QueryClientProvider>
  )
}
