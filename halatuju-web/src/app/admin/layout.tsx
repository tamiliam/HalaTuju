'use client'

import { AdminAuthProvider, useAdminAuth } from '@/lib/admin-auth-context'
import { useRouter, usePathname } from 'next/navigation'
import { useEffect, useState } from 'react'
import Link from 'next/link'
import { adminSignOut } from '@/lib/admin-supabase'
import { mustCompleteProfile } from '@/lib/adminLanding'
import { getPendingSponsorCount } from '@/lib/admin-api'
import { useT } from '@/lib/i18n'

function AdminLayoutInner({ children }: { children: React.ReactNode }) {
  const { isAdminAuthenticated, isLoading, role, token } = useAdminAuth()
  const router = useRouter()
  const pathname = usePathname()
  const [mobileOpen, setMobileOpen] = useState(false)
  const [pendingSponsors, setPendingSponsors] = useState(0)
  const { t } = useT()

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

  // Pending-sponsor count for the Administration badge — only the roles that can see Sponsors
  // (super / org_admin / Admin-General). Refetched on navigation so it stays fresh after vetting.
  useEffect(() => {
    const canSee = !!(role?.is_super_admin || role?.role === 'admin' || role?.role === 'org_admin')
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

  // Payments + Contracts + Sponsors are sub-pages of Administration (no top-level nav entry), so
  // their pages highlight the Administration link as active (owner, 2026-07-16/18/21).
  const isActive = (href: string) =>
    pathname === href || (href === '/admin/administration'
      && (pathname.startsWith('/admin/payments') || pathname.startsWith('/admin/contracts')
          || pathname.startsWith('/admin/sponsors')))

  // Role-driven menu (2026-06): super/admin see everything; partner sees only
  // Dashboard + Students (own org) — no Guide/FAQ; reviewer + qc see only B40 Applications
  // (qc lands on the awaiting-QC queue).
  const r = role?.is_super_admin ? 'super' : (role?.role || 'reviewer')
  // Header identity suffix: only a genuine super sees "(Super admin)". Org members show their
  // org; everyone else shows their real role label (a reviewer/qc must NOT read "Super Admin"
  // just because they have no org).
  const roleLabel = role?.is_super_admin
    ? t('admin.role.super')
    : role?.org_name
      ? role.org_name
      : t(`admin.role.${r}`)
  const dashboard = { href: '/admin', label: t('common.dashboard') }
  const students = { href: '/admin/students', label: t('admin.students') }
  const scholarship = { href: '/admin/scholarship', label: t('admin.scholarship.nav') }
  const courseData = { href: '/admin/course-data', label: t('admin.courseData.nav') }
  const administration = { href: '/admin/administration', label: t('admin.administration.nav') }
  const profile = { href: '/admin/profile', label: t('admin.profile') }
  const guide = { href: '/admin/guide', label: t('admin.guideNav') }
  const faq = { href: '/admin/faq', label: t('admin.faqNav') }
  const navLinks =
    // BrightPath (bursary) roles — admin + qc + reviewer + org_admin — see the scholarship
    // side, NOT the HalaTuju course-selector pages (Dashboard/Students/Course Data), which
    // only super retains. Per the role matrix (2026-07-15): QC has NO Sponsors; Admin-General
    // and org_admin get the Administration panel (org_admin manages staff, Admin-General views it
    // read-only); super gets it as the platform console. Sponsors is NO LONGER a top-level entry
    // (owner 2026-07-21) — it lives inside Administration as a card, with the pending-approval badge.
    r === 'partner' ? [dashboard, students, profile]        // HalaTuju org rep
    : r === 'reviewer' ? [scholarship, profile, guide, faq]
    : r === 'qc' ? [scholarship, profile, guide, faq]        // QC: no Sponsors (matrix)
    : r === 'admin' ? [scholarship, administration, profile, guide, faq]
    : r === 'org_admin' ? [scholarship, administration, profile, guide, faq]
    // Finance has NO B40 scope, so NO Scholarship link -- it would 403. It reaches Payments
    // through the Administration card, exactly as admin/org_admin do.
    : r === 'finance' ? [administration, profile, guide, faq]
    : [dashboard, students, scholarship, courseData, administration, profile, guide, faq]  // super

  // A small red count on the Administration entry when sponsor accounts await vetting.
  const navBadge = (href: string) =>
    href === '/admin/administration' && pendingSponsors > 0 ? (
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
            {navLinks.map(link => (
              <Link
                key={link.href}
                href={link.href}
                className={`text-sm font-medium ${isActive(link.href) ? 'text-blue-600' : 'text-gray-600 hover:text-blue-600'}`}
              >
                {link.label}{navBadge(link.href)}
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
            {navLinks.map(link => (
              <Link
                key={link.href}
                href={link.href}
                className={`block px-3 py-2.5 rounded-lg text-sm font-medium ${isActive(link.href) ? 'text-blue-600 bg-blue-50' : 'text-gray-600 hover:bg-gray-50'}`}
              >
                {link.label}{navBadge(link.href)}
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
