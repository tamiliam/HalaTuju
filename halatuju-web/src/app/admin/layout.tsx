'use client'

// TD-360: the admin console's words (the `admin.*` slice) — for its side effect, BEFORE anything
// renders, so the server render and the first paint have them. Only this layout and the sandbox's
// load it; see the module's header.
import '@/lib/messagesAdmin'
import { AdminAuthProvider, useAdminAuth } from '@/lib/admin-auth-context'
import { useRouter, usePathname } from 'next/navigation'
import { useEffect } from 'react'
import { adminLanding, mustCompleteProfile, outsiderMustLeave } from '@/lib/adminLanding'
import { useT } from '@/lib/i18n'
import { CHROMELESS } from '@/lib/navigation'
import { AppShell } from '@/components/admin/AppShell'

/**
 * The admin layout is now only a GUARD — it decides whether you may be here at all.
 *
 * What the console LOOKS like lives in `components/admin/AppShell`; who sees WHAT lives in
 * `lib/navigation.ts`. This file went from 220 lines holding a role ternary, a hand-written
 * active-route rule, a badge fetch and two copies of the nav markup, to this.
 */
function AdminLayoutInner({ children }: { children: React.ReactNode }) {
  const { isAdminAuthenticated, isLoading, role } = useAdminAuth()
  const router = useRouter()
  const pathname = usePathname()
  const { t } = useT()

  // Login / OAuth callback / set-password render without chrome and without this guard.
  const chromeless = CHROMELESS.some((c) => pathname === c || pathname.startsWith(c))
  // A source user or a mentor on a staff page leaves before that page mounts (review M3, S7a) — see
  // `outsiderMustLeave`.
  const misplaced = !chromeless && !isLoading && isAdminAuthenticated && outsiderMustLeave(role, pathname)

  useEffect(() => {
    if (chromeless) return
    if (!isLoading && !isAdminAuthenticated) {
      router.replace('/admin/login')
      return
    }
    // Hold a newly-invited reviewer on /admin/profile until their compulsory fields are filled
    // (first-login onboarding). mustCompleteProfile is reviewer-only and exempts the profile /
    // set-password / auth pages, so it cannot loop.
    if (!isLoading && isAdminAuthenticated && mustCompleteProfile(role, pathname)) {
      router.replace('/admin/profile')
    }
    if (misplaced && role) router.replace(adminLanding(role))
  }, [isAdminAuthenticated, isLoading, router, pathname, role, chromeless, misplaced])

  if (chromeless) return <>{children}</>

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center">{t('common.loading')}</div>
    )
  }

  if (!isAdminAuthenticated) return null
  // Not the page, and not the shell either: nothing that could fetch mounts on the way out.
  if (misplaced) {
    return <div className="flex min-h-screen items-center justify-center">{t('common.loading')}</div>
  }

  return <AppShell>{children}</AppShell>
}

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return (
    <AdminAuthProvider>
      <AdminLayoutInner>{children}</AdminLayoutInner>
    </AdminAuthProvider>
  )
}
