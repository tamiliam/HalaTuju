'use client'

import { AdminAuthProvider, useAdminAuth } from '@/lib/admin-auth-context'
import { useRouter, usePathname } from 'next/navigation'
import { useEffect, useState } from 'react'
import Link from 'next/link'
import { adminSignOut } from '@/lib/admin-supabase'
import { useT } from '@/lib/i18n'

function AdminLayoutInner({ children }: { children: React.ReactNode }) {
  const { isAdminAuthenticated, isLoading, role } = useAdminAuth()
  const router = useRouter()
  const pathname = usePathname()
  const [mobileOpen, setMobileOpen] = useState(false)
  const { t } = useT()

  useEffect(() => {
    // Don't redirect if on login or callback pages
    if (pathname === '/admin/login' || pathname.startsWith('/admin/auth/')) return
    if (!isLoading && !isAdminAuthenticated) {
      router.replace('/admin/login')
    }
  }, [isAdminAuthenticated, isLoading, router, pathname])

  // Close mobile menu on navigation
  useEffect(() => {
    setMobileOpen(false)
  }, [pathname])

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

  const navLinks = [
    { href: '/admin', label: t('common.dashboard') },
    { href: '/admin/students', label: t('admin.students') },
    ...(role?.is_super_admin ? [{ href: '/admin/invite', label: t('admin.invite') }] : []),
    { href: '/admin/profile', label: t('admin.profile') },
  ]

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
                className={`text-sm font-medium ${pathname === link.href ? 'text-blue-600' : 'text-gray-600 hover:text-blue-600'}`}
              >
                {link.label}
              </Link>
            ))}
          </div>

          <div className="flex-1" />

          {/* Desktop user info */}
          <div className="hidden md:flex items-center gap-3">
            <span className="text-sm text-gray-500">
              {role?.admin_name}
              {role?.org_name ? ` (${role.org_name})` : ` (${t('admin.superAdmin')})`}
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
                className={`block px-3 py-2.5 rounded-lg text-sm font-medium ${pathname === link.href ? 'text-blue-600 bg-blue-50' : 'text-gray-600 hover:bg-gray-50'}`}
              >
                {link.label}
              </Link>
            ))}
            <div className="border-t border-gray-100 pt-2 mt-2">
              <p className="px-3 py-1 text-xs text-gray-400">
                {role?.admin_name}
                {role?.org_name ? ` (${role.org_name})` : ` (${t('admin.superAdmin')})`}
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
