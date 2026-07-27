'use client'

import { AdminAuthProvider, useAdminAuth } from '@/lib/admin-auth-context'
import { useRouter, usePathname } from 'next/navigation'
import { useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import { adminSignOut } from '@/lib/admin-supabase'
import { mustCompleteProfile } from '@/lib/adminLanding'
import { getPendingSponsorCount } from '@/lib/admin-api'
import { useT } from '@/lib/i18n'
import {
  effectiveRole, legacyBarItems, legacyBarActiveId, NO_PROBES,
} from '@/lib/navigation'

function AdminLayoutInner({ children }: { children: React.ReactNode }) {
  const { isAdminAuthenticated, isLoading, role, token } = useAdminAuth()
  const router = useRouter()
  const pathname = usePathname()
  const [mobileOpen, setMobileOpen] = useState(false)
  const [pendingSponsors, setPendingSponsors] = useState(0)
  const { t } = useT()

  // The menu now comes from the route registry (lib/navigation.ts), not a chain of role checks.
  // NO_PROBES is correct here: the two dark-shipped routes (Requests, Billing) are reached from
  // the Administration hub, never the bar, so nothing on this surface depends on a probe. The
  // shell that probes for real arrives with the sidebar.
  const r = effectiveRole(role)
  const navItems = useMemo(
    () => legacyBarItems({ role: r, probes: NO_PROBES }),
    [r],
  )

  useEffect(() => {
    // Don't redirect if on login or callback pages
    if (pathname === '/admin/login' || pathname.startsWith('/admin/auth/')) return
    if (!isLoading && !isAdminAuthenticated) {
      router.replace('/admin/login')
      return
    }
    // Hold a newly-invited reviewer on /admin/profile until their compulsory fields are filled
    // (first-login onboarding). mustCompleteProfile is reviewer-only + exempts the profile /
    // set-password / auth pages, so it can't loop.
    if (!isLoading && isAdminAuthenticated && mustCompleteProfile(role, pathname)) {
      router.replace('/admin/profile')
    }
  }, [isAdminAuthenticated, isLoading, router, pathname, role])

  // Close mobile menu on navigation
  useEffect(() => {
    setMobileOpen(false)
  }, [pathname])

  // Pending-sponsor count for the Administration badge. Who may see it is no longer re-derived
  // here: the registry says which items carry the badge and which roles reach them, so this
  // fetch fires iff a badged item is actually on this person's bar. Refetched on navigation so
  // it stays fresh after vetting. A badge is a hint — a refusal is swallowed, never surfaced.
  useEffect(() => {
    const canSee = navItems.some((i) => i.badge === 'pendingSponsors')
    if (!isAdminAuthenticated || !token || !canSee) { setPendingSponsors(0); return }
    getPendingSponsorCount({ token })
      .then((d) => setPendingSponsors(d.count))
      .catch(() => { /* a badge is a hint; never block the shell on it */ })
  }, [isAdminAuthenticated, token, role, pathname])

  // Login and callback pages render without nav
  if (pathname === '/admin/login' || pathname.startsWith('/admin/auth/')) {
    return <>{children}</>
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        {t('common.loading')}
      </div>
    )
  }

  if (!isAdminAuthenticated) {
    return null
  }

  const handleSignOut = async () => {
    await adminSignOut()
    router.replace('/admin/login')
  }

  // Which bar entry is highlighted. Payments / Contracts / Sponsors / Sources / Billing /
  // Requests have no entry of their own and light up the Administration hub they live under —
  // the registry says so per item, so the three that used to highlight NOTHING (requests,
  // sources, billing) now work without another special case here.
  const activeId = legacyBarActiveId(pathname)

  // Header identity suffix: only a genuine super sees "(Super admin)". Org members show their
  // org; everyone else shows their real role label (a reviewer/qc must NOT read "Super Admin"
  // just because they have no org).
  const roleLabel = role?.is_super_admin
    ? t('admin.role.super')
    : role?.org_name
      ? role.org_name
      : t(`admin.role.${r}`)

  // A small red count on the Administration entry when sponsor accounts await vetting.
  const navBadge = (badge?: string) =>
    badge === 'pendingSponsors' && pendingSponsors > 0 ? (
      <span
        className="ml-1.5 inline-flex items-center justify-center min-w-[18px] h-[18px] px-1 rounded-full bg-red-600 text-white text-[10px] font-bold leading-none align-middle"
        title={t('admin.administration.pendingApproval', { count: String(pendingSponsors) })}
        aria-label={t('admin.administration.pendingApproval', { count: String(pendingSponsors) })}
      >
        {pendingSponsors}
      </span>
    ) : null

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white border-b">
        <div className="px-4 py-3 flex items-center justify-between">
          <Link href="/admin" className="font-bold text-blue-600 shrink-0">HalaTuju Admin</Link>

          {/* Desktop nav */}
          <div className="hidden md:flex items-center gap-4 ml-6">
            {navItems.map(item => (
              <Link
                key={item.id}
                href={item.href}
                className={`text-sm font-medium ${activeId === item.id ? 'text-blue-600' : 'text-gray-600 hover:text-blue-600'}`}
              >
                {t(item.labelKey)}{navBadge(item.badge)}
              </Link>
            ))}
          </div>

          <div className="flex-1" />

          {/* Desktop user info */}
          <div className="hidden md:flex items-center gap-3">
            <span className="text-sm text-gray-500">
              {role?.admin_name}
              {` (${roleLabel})`}
            </span>
            <button onClick={handleSignOut} className="text-sm text-red-600 hover:text-red-800">
              {t('header.logout')}
            </button>
          </div>

          {/* Mobile hamburger */}
          <button
            className="md:hidden p-2 rounded-lg hover:bg-gray-50"
            onClick={() => setMobileOpen(!mobileOpen)}
            aria-label={t('common.menu')}
          >
            {mobileOpen ? (
              <svg className="w-5 h-5 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            ) : (
              <svg className="w-5 h-5 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            )}
          </button>
        </div>

        {/* Mobile menu */}
        {mobileOpen && (
          <div className="md:hidden border-t bg-white px-4 py-3 space-y-1">
            {navItems.map(item => (
              <Link
                key={item.id}
                href={item.href}
                className={`block px-3 py-2.5 rounded-lg text-sm font-medium ${activeId === item.id ? 'text-blue-600 bg-blue-50' : 'text-gray-600 hover:bg-gray-50'}`}
              >
                {t(item.labelKey)}{navBadge(item.badge)}
              </Link>
            ))}
            <div className="border-t border-gray-100 pt-2 mt-2">
              <p className="px-3 py-1 text-xs text-gray-400">
                {role?.admin_name}
                {` (${roleLabel})`}
              </p>
              <button
                onClick={handleSignOut}
                className="block w-full text-left px-3 py-2.5 rounded-lg text-sm text-red-600 hover:bg-red-50"
              >
                {t('header.logout')}
              </button>
            </div>
          </div>
        )}
      </nav>
      <main className="max-w-6xl mx-auto p-4 md:p-6">{children}</main>
    </div>
  )
}

export default function AdminLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <AdminAuthProvider>
      <AdminLayoutInner>{children}</AdminLayoutInner>
    </AdminAuthProvider>
  )
}
